import requests
import time
from datetime import datetime


class DataCache:
    def __init__(self):
        self.jmm_cache = {}
        self.jmm_last_update = 0
        self.jmm_update_interval = 5
        self.boop_counter = None  # Will be set by VRChatMessenger
        self.shock_data = {"intensity": 0, "group": "none"}  # Current shock info

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

    def update_shock_data(self, intensity, group):
        """Update current shock data"""
        self.shock_data = {"intensity": intensity, "group": group}

    def get_shock_data(self):
        """Get current shock data"""
        return self.shock_data


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

    # If we get here, it's an unknown placeholder
    return f"Error: {placeholder}"
