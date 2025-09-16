import requests
import time
from datetime import datetime


class DataCache:
    def __init__(self):
        self.jmm_cache = {}
        self.jmm_last_update = 0
        self.jmm_update_interval = 5
        self.boop_counter = None  # Will be set by VRChatMessenger
        self.shock_data = {"intensity": 0, "group": "none", "duration": 0}  # Current shock info
        self.internet_shock_data = {
            "user_name": "Unknown",
            "real_name": "Unknown",
            "shocker_name": "Unknown",
            "type_name": "shock",
            "intensity": 0,
            "duration": 0,
            "is_guest": False,
            "share_link_id": None
        }  # Current internet shock info

    def get_jmm_data(self):
        if time.time() - self.jmm_last_update > self.jmm_update_interval:
            try:
                metadata = requests.get("https://joinmymusic.com/metadata.php")
                listeners = requests.get("https://joinmymusic.com/listeners.php?stats")

                if metadata.status_code == 200 and listeners.status_code == 200:
                    self.jmm_cache = {
                        "metadata": metadata.json(),
                        "listeners": listeners.json(),
                    }
                    self.jmm_last_update = time.time()
            except Exception as e:
                print(f"Error updating JMM data: {e}")
        return self.jmm_cache

    def get_boop_data(self):
        # Make sure boop_counter has been set
        if self.boop_counter is None:
            return {"total_boops": 0, "daily_boops": 0, "counter_enabled": False}

        # Make sure to reload from file each time to get latest values
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
    # Remove locatesam.com data fetch
    jmm_data = data_cache.get_jmm_data()
    boop_data = data_cache.get_boop_data()

    # Handle only the placeholders we need
    if placeholder in ["total_boops", "daily_boops"]:
        return boop_data.get(placeholder, 0)

    if placeholder == "time":
        return datetime.now().strftime("%I:%M %p")

    if placeholder == "jmm_artist":
        if not jmm_data.get("metadata"):
            return "No data"
        return truncate_text(
            ", ".join(
                artist["name"] for artist in jmm_data["metadata"]["current"]["artist"]
            )
            if jmm_data.get("metadata") and jmm_data["metadata"]["current"]["artist"]
            else "No artist"
        )

    if placeholder == "jmm_song":
        if not jmm_data.get("metadata"):
            return "No data"
        return truncate_text(jmm_data["metadata"]["current"]["song"] or "No song")

    if placeholder == "shock_intensity":
        return str(data_cache.get_shock_data()["intensity"])

    if placeholder == "shock_group":
        return data_cache.get_shock_data()["group"]

    if placeholder == "shock_duration":
        duration = data_cache.get_shock_data()["duration"]
        return f"{duration:.1f}s" if duration else "0s"

    # Internet shock placeholders
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

    # If we get here, it's an unknown placeholder
    return f"Error: {placeholder}"
