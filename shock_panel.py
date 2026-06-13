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
        self._intensity = {}       # entry_id -> float 0-100
        self._duration = {}        # entry_id -> float seconds
        self._hold_active = {}     # entry_id -> bool
        self._warning_active = {}  # entry_id -> bool

        self._dispatcher = dispatcher
        self._registered_paths = set()

        if dispatcher:
            self._register_all(dispatcher)

    def update_config(self, new_config):
        self.config = new_config
        for entry in self.config.get("entries", []):
            eid = entry["id"]
            self._intensity[eid] = float(entry.get("intensity", 50))
            self._duration[eid] = float(entry.get("duration", 1.0))
        if self._dispatcher:
            self._register_all(self._dispatcher)

    def set_dispatcher(self, dispatcher):
        self._dispatcher = dispatcher
        self._register_all(dispatcher)

    def _register_all(self, dispatcher):
        for entry in self.config.get("entries", []):
            eid = entry["id"]
            name = osc_safe_name(entry.get("osc_name") or entry.get("name", ""))
            for suffix, handler in [
                ("Trigger",   self._make_trigger_handler(eid)),
                ("Intensity", self._make_intensity_handler(eid)),
                ("Duration",  self._make_duration_handler(eid)),
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
            mode = entry.get("mode", "trigger")
            if mode == "hold":
                if active:
                    self._start_hold(eid)
                else:
                    self._stop_hold(eid)
            elif mode == "warning":
                if active:
                    self._start_warning(eid)
                else:
                    self._cancel_warning(eid)
            else:  # "trigger" — one-shot on rising edge only
                if active:
                    self._fire(eid)
        return h

    def _make_intensity_handler(self, eid):
        def h(address, *args):
            if not args:
                return
            val = max(0.0, min(1.0, float(args[0])))
            with self._lock:
                self._intensity[eid] = val * 100.0
            self.client.send_message(address, val)
            print(f"ShockPanel intensity [{eid}]: {val*100:.0f}%")
        return h

    def _make_duration_handler(self, eid):
        def h(address, *args):
            if not args:
                return
            val = max(0.0, min(1.0, float(args[0])))
            dur = 0.5 + val * 9.5
            with self._lock:
                self._duration[eid] = dur
            self.client.send_message(address, val)
            print(f"ShockPanel duration [{eid}]: {dur:.2f}s")
        return h

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
            intensity = self._intensity.get(eid, float(entry.get("intensity", 50)))
            duration = self._duration.get(eid, float(entry.get("duration", 1.0)))

        shocker_ids = entry.get("shocker_ids", [])
        if not shocker_ids:
            print(f"ShockPanel: no shockers assigned to '{entry.get('name')}'")
            return

        print(f"ShockPanel: firing '{entry.get('name')}' {intensity:.0f}% {duration:.2f}s")
        self.shock_controller.send_openshock_command(
            shocker_ids, int(intensity), duration, action_type=1
        )
        if self.shock_controller.shock_callback:
            self.shock_controller.shock_callback(int(intensity), entry.get("name", "panel"), duration)

    def _start_hold(self, eid):
        with self._lock:
            if self._hold_active.get(eid):
                return
            self._hold_active[eid] = True
        print(f"ShockPanel: hold start [{eid}]")
        threading.Thread(target=self._hold_loop, args=(eid,), daemon=True).start()

    def _stop_hold(self, eid):
        with self._lock:
            self._hold_active[eid] = False
        print(f"ShockPanel: hold stop [{eid}]")

    def _hold_loop(self, eid):
        while True:
            with self._lock:
                if not self._hold_active.get(eid):
                    break
                duration = self._duration.get(eid, 1.0)

            self._fire(eid)

            deadline = time.time() + duration
            while time.time() < deadline:
                time.sleep(0.05)
                with self._lock:
                    if not self._hold_active.get(eid):
                        return

    def _start_warning(self, eid):
        with self._lock:
            if self._warning_active.get(eid):
                return  # already in progress
            self._warning_active[eid] = True
        print(f"ShockPanel: warning start [{eid}]")
        self._broadcast_warning_state(eid, True)
        threading.Thread(target=self._warning_sequence, args=(eid,), daemon=True).start()

    def _cancel_warning(self, eid):
        with self._lock:
            was_active = self._warning_active.get(eid, False)
            self._warning_active[eid] = False
        if was_active:
            print(f"ShockPanel: warning cancelled [{eid}]")
            # Broadcast false so VRChat state stays in sync
            self._broadcast_warning_state(eid, False)

    def _warning_sequence(self, eid):
        entry = self._get_entry(eid)
        if not entry or not entry.get("enabled", True) or not self.config.get("enabled", False):
            with self._lock:
                self._warning_active[eid] = False
            self._broadcast_warning_state(eid, False)
            return

        with self._lock:
            intensity = self._intensity.get(eid, float(entry.get("intensity", 50)))
            duration = self._duration.get(eid, float(entry.get("duration", 1.0)))

        shocker_ids = entry.get("shocker_ids", [])
        if not shocker_ids:
            print(f"ShockPanel: warning — no shockers for '{entry.get('name')}'")
            with self._lock:
                self._warning_active[eid] = False
            self._broadcast_warning_state(eid, False)
            return

        delay_min = max(0.0, float(entry.get("warning_delay_min", 2.0)))
        delay_max = max(delay_min, float(entry.get("warning_delay_max", 5.0)))
        delay = random.uniform(delay_min, delay_max)

        # Step 1: vibrate as the warning
        print(f"ShockPanel: warning vibrate '{entry.get('name')}' {intensity:.0f}% {duration:.2f}s")
        self.shock_controller.send_openshock_command(
            shocker_ids, int(intensity), duration, action_type=2  # vibrate
        )

        # Step 2: wait the random delay, allow cancellation
        deadline = time.time() + delay
        while time.time() < deadline:
            time.sleep(0.05)
            with self._lock:
                if not self._warning_active.get(eid):
                    self._broadcast_warning_state(eid, False)
                    return

        # Step 3: check still active, then shock
        with self._lock:
            still_active = self._warning_active.get(eid, False)
            self._warning_active[eid] = False

        if still_active:
            print(f"ShockPanel: warning → shock '{entry.get('name')}'")
            self._fire(eid)

        self._broadcast_warning_state(eid, False)

    def _broadcast_warning_state(self, eid, state):
        entry = self._get_entry(eid)
        if not entry:
            return
        name = osc_safe_name(entry.get("osc_name") or entry.get("name", ""))
        self.client.send_message(
            f"/avatar/parameters/ShockPanel/{name}/WarningMode", state)

    # ── broadcast helpers ─────────────────────────────────────────────────────

    def broadcast_state(self, eid):
        """Push current intensity/duration for an entry back to VRChat."""
        entry = self._get_entry(eid)
        if not entry:
            return
        name = osc_safe_name(entry.get("osc_name") or entry.get("name", ""))
        with self._lock:
            intensity = self._intensity.get(eid, float(entry.get("intensity", 50)))
            duration = self._duration.get(eid, float(entry.get("duration", 1.0)))
        self.client.send_message(
            f"/avatar/parameters/ShockPanel/{name}/Intensity", intensity / 100.0)
        dur_norm = max(0.0, min(1.0, (duration - 0.5) / 9.5))
        self.client.send_message(
            f"/avatar/parameters/ShockPanel/{name}/Duration", dur_norm)

    def broadcast_all(self):
        for entry in self.config.get("entries", []):
            self.broadcast_state(entry["id"])

    # ── cleanup ───────────────────────────────────────────────────────────────

    def cleanup(self):
        with self._lock:
            for eid in list(self._hold_active.keys()):
                self._hold_active[eid] = False
            for eid in list(self._warning_active.keys()):
                self._warning_active[eid] = False
