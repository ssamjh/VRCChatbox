import asyncio
import sys
import threading

HR_SERVICE_UUID = "0000180d-0000-1000-8000-00805f9b34fb"
HR_MEASUREMENT_UUID = "00002a37-0000-1000-8000-00805f9b34fb"

MAX_CONNECT_ATTEMPTS = 5

try:
    from bleak import BleakScanner, BleakClient
    BLEAK_AVAILABLE = True
except ImportError:
    BLEAK_AVAILABLE = False


class BPMMonitor:
    def __init__(self):
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()
        self._client = None
        self._bpm = 0
        self._connected = False
        self._status = "Not connected"
        self._lock = threading.Lock()
        self._on_update = None        # called (no args) whenever the BPM value changes
        # Auto-reconnect state
        self._target = None          # address we want to stay connected to
        self._reconnect = False      # keep trying to (re)connect while True
        self._manager_running = False

    def set_on_update(self, callback):
        """Register a callback fired whenever the BPM value changes."""
        self._on_update = callback

    def get_bpm(self):
        with self._lock:
            return self._bpm

    def get_status(self):
        return self._status

    def is_connected(self):
        return self._connected

    def scan(self, callback):
        """Scan for BLE HR devices. callback(list[(name, address)]) called on completion."""
        if not BLEAK_AVAILABLE:
            callback([])
            return
        asyncio.run_coroutine_threadsafe(self._do_scan(callback), self._loop)

    def connect(self, address):
        if not BLEAK_AVAILABLE:
            self._status = "bleak not installed (pip install bleak)"
            return
        # Set the desired target and (re)start the reconnect manager. The
        # manager keeps retrying until connected and reconnects on drops.
        self._target = address
        self._reconnect = True
        if not self._manager_running:
            asyncio.run_coroutine_threadsafe(self._manager(), self._loop)

    def disconnect(self):
        """User-initiated disconnect — stops auto-reconnect."""
        self._reconnect = False
        self._target = None
        asyncio.run_coroutine_threadsafe(self._do_disconnect(), self._loop)

    def shutdown(self):
        """Clean disconnect on app exit.

        Tearing the GATT link down properly is what frees the sensor for the
        next launch. Without this the device stays bonded to a dead session and
        refuses to reconnect until it is power-cycled.
        """
        self._reconnect = False
        self._target = None
        if not BLEAK_AVAILABLE:
            return
        try:
            fut = asyncio.run_coroutine_threadsafe(self._do_disconnect(), self._loop)
            fut.result(timeout=5)
        except Exception:
            pass
        try:
            self._loop.call_soon_threadsafe(self._loop.stop)
        except Exception:
            pass

    async def _do_scan(self, callback):
        try:
            self._status = "Scanning..."
            devices = await BleakScanner.discover(
                service_uuids=[HR_SERVICE_UUID], timeout=5.0)
            callback([(d.name or "Unknown", d.address) for d in devices])
            self._status = "Scan complete" if devices else "No devices found"
        except Exception as e:
            self._status = f"Scan error: {e}"
            callback([])

    async def _manager(self):
        """Background loop: keep the target connected, reconnect on drop.

        Gives up after MAX_CONNECT_ATTEMPTS consecutive failures. A successful
        connection resets the counter, so a later drop gets a fresh budget of
        retries. Pressing Connect (or relaunching while enabled) calls
        connect() again, which restarts this loop.
        """
        self._manager_running = True
        attempt = 0
        try:
            while self._reconnect and self._target:
                if self._connected and self._client and self._client.is_connected:
                    attempt = 0
                    await asyncio.sleep(2.0)
                    continue
                attempt += 1
                ok = await self._try_connect(self._target, attempt)
                if ok:
                    continue
                if attempt >= MAX_CONNECT_ATTEMPTS:
                    self._reconnect = False
                    self._status = (
                        f"Failed to connect after {MAX_CONNECT_ATTEMPTS} "
                        "attempts — press Connect to retry"
                    )
                    break
                if self._reconnect:
                    delay = min(2 + attempt * 2, 15)
                    self._status = (
                        f"Reconnecting in {delay}s "
                        f"(attempt {attempt}/{MAX_CONNECT_ATTEMPTS})…"
                    )
                    await asyncio.sleep(delay)
        finally:
            self._manager_running = False

    async def _try_connect(self, address, attempt):
        try:
            # Drop any stale client object before retrying.
            if self._client:
                try:
                    await self._client.disconnect()
                except Exception:
                    pass
                self._client = None

            self._status = f"Connecting… (attempt {attempt}/{MAX_CONNECT_ATTEMPTS})"
            kwargs = {"disconnected_callback": self._on_disconnect}
            # On Windows, skip the cached GATT services so a fresh discovery is
            # done — stale cache entries are a common reconnect failure cause.
            if sys.platform == "win32":
                kwargs["winrt"] = {"use_cached_services": False}

            self._client = BleakClient(address, **kwargs)
            await self._client.connect()
            await self._client.start_notify(HR_MEASUREMENT_UUID, self._hr_handler)
            self._connected = True
            self._status = "Connected"
            return True
        except Exception as e:
            self._connected = False
            self._status = f"Connect failed (attempt {attempt}): {e}"
            return False

    async def _do_disconnect(self):
        try:
            if self._client and self._client.is_connected:
                await self._client.disconnect()
        except Exception:
            pass
        self._client = None
        self._connected = False
        with self._lock:
            self._bpm = 0
        self._status = "Disconnected"

    def _on_disconnect(self, client):
        self._connected = False
        with self._lock:
            self._bpm = 0
        # If we still want this device, the manager loop will reconnect.
        if self._reconnect and self._target:
            self._status = "Disconnected — reconnecting…"
        else:
            self._status = "Disconnected"

    def _hr_handler(self, sender, data: bytearray):
        flags = data[0]
        if flags & 0x01:
            bpm = int.from_bytes(data[1:3], byteorder='little')
        else:
            bpm = data[1]
        with self._lock:
            changed = bpm != self._bpm
            self._bpm = bpm
        if changed and self._on_update:
            try:
                self._on_update()
            except Exception:
                pass


bpm_monitor = BPMMonitor()
