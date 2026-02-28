import json
import threading
import time
from datetime import datetime

import requests


class DataCache:
    def __init__(self):
        self.jmm_cache = {}
        self._jmm_lock = threading.Lock()
        self._sse_thread = None
        self._sse_running = False
        self._sse_url = None
        self.boop_counter = None  # Will be set by VRChatMessenger
        self.shock_data = {"intensity": 0, "group": "none", "duration": 0}
        self.internet_shock_data = {
            "user_name": "Unknown",
            "real_name": "Unknown",
            "shocker_name": "Unknown",
            "type_name": "shock",
            "intensity": 0,
            "duration": 0,
            "is_guest": False,
            "share_link_id": None
        }

    def start_sse(self, url):
        """Start the SSE listener thread."""
        self._sse_url = url
        self._sse_running = True
        self._sse_thread = threading.Thread(target=self._sse_worker, daemon=True)
        self._sse_thread.start()
        print(f"SSE listener started: {url}")

    def _sse_worker(self):
        """Background thread: connect to SSE endpoint and reconnect on failure."""
        while self._sse_running:
            try:
                with requests.get(self._sse_url, stream=True, timeout=(10, None)) as response:
                    response.raise_for_status()
                    print(f"SSE connected to {self._sse_url}")
                    event_type = None
                    for raw_line in response.iter_lines():
                        if not self._sse_running:
                            return
                        line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
                        if line.startswith("event:"):
                            event_type = line[len("event:"):].strip()
                        elif line.startswith("data:"):
                            data_str = line[len("data:"):].strip()
                            try:
                                data = json.loads(data_str)
                                with self._jmm_lock:
                                    if event_type == "metadata":
                                        self.jmm_cache["metadata"] = data
                                    elif event_type == "listeners":
                                        self.jmm_cache["listeners"] = data
                            except json.JSONDecodeError:
                                pass
                        # Lines starting with ':' are SSE comments/keepalives — ignore
            except Exception as e:
                if self._sse_running:
                    print(f"SSE error ({e}), reconnecting in 5s...")
                    time.sleep(5)

    def get_jmm_data(self):
        with self._jmm_lock:
            return dict(self.jmm_cache)

    def get_boop_data(self):
        if self.boop_counter is None:
            return {"total_boops": 0, "daily_boops": 0, "counter_enabled": False}
        self.boop_counter._load_data()
        return self.boop_counter.get_boops_data()

    def update_shock_data(self, intensity, group, duration=0):
        """Update current shock data"""
        self.shock_data = {"intensity": intensity, "group": group, "duration": duration}

    def get_shock_data(self):
        """Get current shock data"""
        return self.shock_data

    def update_internet_shock_data(self, user_name, real_name, shocker_name, type_name, intensity, duration, is_guest=False, share_link_id=None):
        """Update current internet shock data"""
        self.internet_shock_data = {
            "user_name": user_name,
            "real_name": real_name,
            "shocker_name": shocker_name,
            "type_name": type_name,
            "intensity": intensity,
            "duration": duration,
            "is_guest": is_guest,
            "share_link_id": share_link_id
        }

    def get_internet_shock_data(self):
        """Get current internet shock data"""
        return self.internet_shock_data


data_cache = DataCache()


def truncate_text(text, max_length=27):
    if len(text) > max_length:
        return text[:24] + "..."
    return text


def get_placeholder_value(placeholder):
    jmm_data = data_cache.get_jmm_data()
    boop_data = data_cache.get_boop_data()

    if placeholder in ["total_boops", "daily_boops"]:
        return boop_data.get(placeholder, 0)

    if placeholder == "time":
        return datetime.now().strftime("%I:%M %p")

    if placeholder == "jmm_artist":
        metadata = jmm_data.get("metadata")
        if not metadata:
            return "No data"
        artists = metadata.get("artist") or []
        return truncate_text(
            ", ".join(a["name"] for a in artists) if artists else "No artist"
        )

    if placeholder == "jmm_song":
        metadata = jmm_data.get("metadata")
        if not metadata:
            return "No data"
        return truncate_text(metadata.get("song") or "No song")

    if placeholder == "shock_intensity":
        return str(data_cache.get_shock_data()["intensity"])

    if placeholder == "shock_group":
        return data_cache.get_shock_data()["group"]

    if placeholder == "shock_duration":
        duration = data_cache.get_shock_data()["duration"]
        return f"{duration:.1f}s" if duration else "0s"

    if placeholder == "internet_shock_user":
        return data_cache.get_internet_shock_data()["user_name"]

    if placeholder == "internet_shock_type":
        return data_cache.get_internet_shock_data()["type_name"]

    if placeholder == "internet_shock_intensity":
        return str(data_cache.get_internet_shock_data()["intensity"])

    if placeholder == "internet_shock_shocker":
        return data_cache.get_internet_shock_data()["shocker_name"]

    if placeholder == "internet_shock_duration":
        duration_ms = data_cache.get_internet_shock_data()["duration"]
        return f"{duration_ms/1000:.1f}s" if duration_ms else "0s"

    return f"Error: {placeholder}"
