import asyncio
import threading

HR_SERVICE_UUID = "0000180d-0000-1000-8000-00805f9b34fb"
HR_MEASUREMENT_UUID = "00002a37-0000-1000-8000-00805f9b34fb"

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
        asyncio.run_coroutine_threadsafe(self._do_connect(address), self._loop)

    def disconnect(self):
        asyncio.run_coroutine_threadsafe(self._do_disconnect(), self._loop)

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

    async def _do_connect(self, address):
        try:
            if self._client and self._client.is_connected:
                await self._client.disconnect()
            self._status = "Connecting..."
            self._client = BleakClient(address,
                                       disconnected_callback=self._on_disconnect)
            await self._client.connect()
            self._connected = True
            self._status = "Connected"
            await self._client.start_notify(HR_MEASUREMENT_UUID, self._hr_handler)
        except Exception as e:
            self._connected = False
            self._status = f"Failed: {e}"

    async def _do_disconnect(self):
        try:
            if self._client and self._client.is_connected:
                await self._client.disconnect()
        except Exception:
            pass
        self._connected = False
        with self._lock:
            self._bpm = 0
        self._status = "Disconnected"

    def _on_disconnect(self, client):
        self._connected = False
        with self._lock:
            self._bpm = 0
        self._status = "Disconnected"

    def _hr_handler(self, sender, data: bytearray):
        flags = data[0]
        if flags & 0x01:
            bpm = int.from_bytes(data[1:3], byteorder='little')
        else:
            bpm = data[1]
        with self._lock:
            self._bpm = bpm


bpm_monitor = BPMMonitor()
