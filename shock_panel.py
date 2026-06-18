import random
import re
import threading
import time


def osc_safe_name(name):
    safe = re.sub(r'[^a-zA-Z0-9_]', '', name.replace(' ', '_'))
    return safe or 'Entry'


class ShockPanelController:
    def __init__(self, osc_client, shock_controller, dispatcher=None):
        self.client = osc_client
        self.shock_controller = shock_controller
        self.config = {"enabled": False, "entries": []}

        self._lock = threading.Lock()
        # Global intensity/duration — shared by every entry, set via OSC or the UI.
        self._intensity_min = 20.0   # 0-100
        self._intensity_max = 80.0   # 0-100
        self._duration = 1.0         # seconds
        self._hold_active = {}    # entry_id -> bool
        self._hold_timers = {}    # entry_id -> failsafe threading.Timer

        # Called after state changes via OSC so the host app can persist config.
        self.on_state_change = None

        self._dispatcher = dispatcher
        self._registered_paths = set()

        if dispatcher:
            self._register_all(dispatcher)

    def update_config(self, new_config):
        self.config = new_config
        with self._lock:
            self._intensity_min = float(new_config.get("intensity_min", 20.0))
            self._intensity_max = float(new_config.get("intensity_max", 80.0))
            self._duration = float(new_config.get("duration", 1.0))
        if self._dispatcher:
            self._register_all(self._dispatcher)
        # NOTE: we deliberately do NOT broadcast here. Pushing our stored values
        # onto the avatar on load fights the avatar's own slider/puppet state and
        # causes an oscillation loop. Broadcasting only happens on explicit UI
        # changes (see broadcast_all callers).

    def set_dispatcher(self, dispatcher):
        self._dispatcher = dispatcher
        self._register_all(dispatcher)

    def _register_all(self, dispatcher):
        # Global parameters (shared by all entries)
        for suffix, handler in [
            ("IntensityMin", self._make_global_intensity_min_handler()),
            ("IntensityMax", self._make_global_intensity_max_handler()),
            ("Duration",     self._make_global_duration_handler()),
        ]:
            path = f"/avatar/parameters/ShockPanel/{suffix}"
            if path not in self._registered_paths:
                dispatcher.map(path, handler)
                self._registered_paths.add(path)

        # Per-entry parameters
        for entry in self.config.get("entries", []):
            eid = entry["id"]
            name = osc_safe_name(entry.get("osc_name") or entry.get("name", ""))
            for suffix, handler in [
                ("Trigger", self._make_trigger_handler(eid)),
                ("Enabled", self._make_enabled_handler(eid)),
            ]:
                path = f"/avatar/parameters/ShockPanel/{name}/{suffix}"
                if path not in self._registered_paths:
                    dispatcher.map(path, handler)
                    self._registered_paths.add(path)

    # ── handler factories ─────────────────────────────────────────────────────

    def _make_trigger_handler(self, eid):
        def h(address, *args):
            active = bool(args[0]) if args else False
            entry = self._get_entry(eid)
            if not entry:
                return
            if entry.get("mode", "trigger") == "hold":
                if active:
                    self._start_hold(eid)
                else:
                    self._stop_hold(eid)
            else:  # one-shot: fire on rising edge only
                if active:
                    self._fire(eid)
        return h

    def _make_global_intensity_min_handler(self):
        def h(address, *args):
            if not args:
                return
            val = max(0.0, min(1.0, float(args[0])))
            new = val * 100.0
            with self._lock:
                if abs(new - self._intensity_min) < 0.5:
                    return
                self._intensity_min = new
            self._persist_globals()
            print(f"ShockPanel IntensityMin: {new:.0f}%")
        return h

    def _make_global_intensity_max_handler(self):
        def h(address, *args):
            if not args:
                return
            val = max(0.0, min(1.0, float(args[0])))
            new = val * 100.0
            with self._lock:
                if abs(new - self._intensity_max) < 0.5:
                    return
                self._intensity_max = new
            self._persist_globals()
            print(f"ShockPanel IntensityMax: {new:.0f}%")
        return h

    def _make_global_duration_handler(self):
        def h(address, *args):
            if not args:
                return
            val = max(0.0, min(1.0, float(args[0])))
            dur = 0.5 + val * 9.5
            with self._lock:
                if abs(dur - self._duration) < 0.05:
                    return
                self._duration = dur
            self._persist_globals()
            print(f"ShockPanel Duration: {dur:.2f}s")
        return h

    def _make_enabled_handler(self, eid):
        def h(address, *args):
            if not args:
                return
            val = bool(args[0])
            entry = self._get_entry(eid)
            if entry is None:
                return
            entry["enabled"] = val
            if self.on_state_change:
                self.on_state_change()
            print(f"ShockPanel Enabled [{entry.get('name')}]: {val}")
        return h

    def _persist_globals(self):
        """Write live global values back into config and notify the host app."""
        with self._lock:
            self.config["intensity_min"] = self._intensity_min
            self.config["intensity_max"] = self._intensity_max
            self.config["duration"] = self._duration
        if self.on_state_change:
            self.on_state_change()

    # ── shock logic ───────────────────────────────────────────────────────────

    def _get_entry(self, eid):
        for e in self.config.get("entries", []):
            if e["id"] == eid:
                return e
        return None

    def _fire(self, eid):
        if not self.config.get("enabled", False):
            return
        entry = self._get_entry(eid)
        if not entry or not entry.get("enabled", True):
            return

        with self._lock:
            imin = self._intensity_min
            imax = self._intensity_max
            duration = self._duration

        intensity = random.randint(int(min(imin, imax)), int(max(imin, imax)))

        shocker_ids = entry.get("shocker_ids", [])
        if not shocker_ids:
            print(f"ShockPanel: no shockers assigned to '{entry.get('name')}'")
            return

        print(f"ShockPanel: firing '{entry.get('name')}' {intensity}% {duration:.2f}s")
        self.shock_controller.send_openshock_command(
            shocker_ids, intensity, duration, action_type=1
        )
        if self.shock_controller.shock_callback:
            self.shock_controller.shock_callback(intensity, entry.get("name", "panel"), duration)

    def _start_hold(self, eid):
        with self._lock:
            if self._hold_active.get(eid):
                return
            self._hold_active[eid] = True
            duration = self._duration
        print(f"ShockPanel: hold start [{eid}]")

        if self._fire_live(eid, duration):
            # Live gateway sent — set failsafe timer to clean up state after duration
            failsafe = threading.Timer(min(duration, 11.0), self._hold_timeout, args=(eid,))
            with self._lock:
                self._hold_timers[eid] = failsafe
            failsafe.start()
        else:
            # SignalR not connected — fall back to REST-based polling loop
            threading.Thread(target=self._hold_loop, args=(eid,), daemon=True).start()

    def _stop_hold(self, eid):
        with self._lock:
            self._hold_active[eid] = False
            timer = self._hold_timers.pop(eid, None)
        if timer:
            timer.cancel()
        self._stop_live(eid)
        print(f"ShockPanel: hold stop [{eid}]")

    def _hold_timeout(self, eid):
        """Failsafe: clean up hold state after duration elapses."""
        with self._lock:
            self._hold_active[eid] = False
            self._hold_timers.pop(eid, None)
        print(f"ShockPanel: hold ended — duration limit reached [{eid}]")

    def _hold_loop(self, eid):
        """Fallback hold loop used when SignalR is not connected."""
        with self._lock:
            if not self._hold_active.get(eid):
                return
            duration = self._duration

        self._fire(eid)

        deadline = time.time() + min(duration, 11.0)
        while time.time() < deadline:
            time.sleep(0.05)
            with self._lock:
                if not self._hold_active.get(eid):
                    return

        with self._lock:
            self._hold_active[eid] = False
        print(f"ShockPanel: hold ended — duration limit reached [{eid}]")

    def _fire_live(self, eid, duration):
        """Send shock via SignalR live gateway. Returns True if sent."""
        if not self.config.get("enabled", False):
            return False
        entry = self._get_entry(eid)
        if not entry or not entry.get("enabled", True):
            return False
        shocker_ids = entry.get("shocker_ids", [])
        if not shocker_ids:
            return False

        with self._lock:
            imin = self._intensity_min
            imax = self._intensity_max

        intensity = random.randint(int(min(imin, imax)), int(max(imin, imax)))
        duration_ms = int(min(duration, 10.0) * 1000)

        sent = self.shock_controller.send_signalr_control(shocker_ids, intensity, duration_ms, action_type=1)
        if sent:
            print(f"ShockPanel: live hold fire '{entry.get('name')}' {intensity}% {duration:.2f}s")
            if self.shock_controller.shock_callback:
                self.shock_controller.shock_callback(intensity, entry.get("name", "panel"), duration)
        return sent

    def _stop_live(self, eid):
        """Send stop command via SignalR live gateway."""
        entry = self._get_entry(eid)
        if not entry:
            return
        shocker_ids = entry.get("shocker_ids", [])
        if shocker_ids:
            self.shock_controller.send_signalr_control(shocker_ids, 0, 300, action_type=0)

    # ── state / broadcast helpers ──────────────────────────────────────────────

    def get_global_state(self):
        """Return the current global intensity/duration values for the UI."""
        with self._lock:
            return {
                "intensity_min": self._intensity_min,
                "intensity_max": self._intensity_max,
                "duration": self._duration,
            }

    def broadcast_globals(self):
        """Push the current global IntensityMin/IntensityMax/Duration to VRChat."""
        base = "/avatar/parameters/ShockPanel"
        with self._lock:
            imin = self._intensity_min
            imax = self._intensity_max
            duration = self._duration
        self.client.send_message(f"{base}/IntensityMin", imin / 100.0)
        self.client.send_message(f"{base}/IntensityMax", imax / 100.0)
        dur_norm = max(0.0, min(1.0, (duration - 0.5) / 9.5))
        self.client.send_message(f"{base}/Duration", dur_norm)

    def broadcast_entry_enabled(self, entry):
        """Push an entry's Enabled bool to VRChat."""
        name = osc_safe_name(entry.get("osc_name") or entry.get("name", ""))
        path = f"/avatar/parameters/ShockPanel/{name}/Enabled"
        self.client.send_message(path, bool(entry.get("enabled", True)))

    def broadcast_all(self):
        self.broadcast_globals()
        for entry in self.config.get("entries", []):
            self.broadcast_entry_enabled(entry)

    # ── cleanup ───────────────────────────────────────────────────────────────

    def cleanup(self):
        with self._lock:
            for eid in list(self._hold_active.keys()):
                self._hold_active[eid] = False
            for timer in self._hold_timers.values():
                timer.cancel()
            self._hold_timers.clear()
