import requests
import time
from datetime import datetime
from boop_counter import BoopCounter


class DataCache:
    def __init__(self):
        self.cache = {}
        self.last_update = 0
        self.update_interval = 5
        self.jmm_cache = {}
        self.jmm_last_update = 0
        self.jmm_update_interval = 5
        self.boop_counter = BoopCounter()

    def get_data(self):
        if time.time() - self.last_update > self.update_interval:
            try:
                response = requests.get("https://locatesam.com/data.php")
                if response.status_code == 200:
                    self.cache = response.json()
                    self.last_update = time.time()
            except Exception as e:
                print(f"Error updating data: {e}")
        return self.cache

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
        # Make sure to reload from file each time to get latest values
        self.boop_counter._load_data()
        return self.boop_counter.get_boops_data()


data_cache = DataCache()


def truncate_text(text, max_length=27):
    if len(text) > max_length:
        return text[:24] + "..."
    return text


def get_placeholder_value(placeholder):
    data = data_cache.get_data()
    jmm_data = data_cache.get_jmm_data()
    boop_data = data_cache.get_boop_data()

    if not data:
        return "No data"

    def format_listeners(count):
        if count == 1:
            return "1 other"
        return f"{count} others"

    mappings = {
        "watch_battery": lambda: data["watch"]["battery_level"],
        "phone_battery": lambda: data["phone"]["battery_level"],
        "room_temp": lambda: round(float(data["bedroom"]["temperature"])),
        "room_temp_f": lambda: round(
            (float(data["bedroom"]["temperature"]) * 9 / 5) + 32
        ),
        "room_humid": lambda: round(float(data["bedroom"]["humidity"])),
        "room_light": lambda: round(float(data["bedroom"]["light_level"])),
        "gpu_temp": lambda: round(float(data["computer"]["gpu_temp"])),
        "heart_rate": lambda: data["watch"]["heart_rate"],
        "time": lambda: datetime.now().strftime("%I:%M %p"),
        "jmm_artist": lambda: truncate_text(
            ", ".join(
                artist["name"] for artist in jmm_data["metadata"]["current"]["artist"]
            )
            if jmm_data.get("metadata")
            else "No data"
        ),
        "jmm_song": lambda: truncate_text(
            jmm_data["metadata"]["current"]["song"]
            if jmm_data.get("metadata")
            else "No data"
        ),
        "jmm_listeners": lambda: (
            format_listeners(jmm_data["listeners"]["listeners"])
            if jmm_data.get("listeners")
            else "0 others"
        ),
        "steps": lambda: data["watch"]["daily_steps"],
        "location": lambda: data["location"]["state"],
        "total_boops": lambda: boop_data["total_boops"],
        "daily_boops": lambda: boop_data["daily_boops"],
    }

    try:
        return mappings[placeholder]()
    except (KeyError, TypeError):
        return f"Error: {placeholder}"
