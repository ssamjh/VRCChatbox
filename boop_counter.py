import json
import os
import datetime
from pathlib import Path


class BoopCounter:
    def __init__(self, filename="boops.json"):
        self.filename = filename
        self.total_boops = 0
        self.daily_boops = 0
        self.counter_enabled = False
        self.last_date = self._get_current_date()
        self._load_data()

    def _get_current_date(self):
        """Get current date as a string in YYYY-MM-DD format"""
        return datetime.datetime.now().strftime("%Y-%m-%d")

    def _load_data(self):
        """Load boop data from file if it exists"""
        try:
            if os.path.exists(self.filename):
                with open(self.filename, "r") as f:
                    data = json.load(f)
                    self.total_boops = data.get("total_boops", 0)
                    self.daily_boops = data.get("daily_boops", 0)
                    self.last_date = data.get("last_date", self._get_current_date())

                # Reset daily count if it's a new day
                current_date = self._get_current_date()
                if current_date != self.last_date:
                    self.daily_boops = 0
                    self.last_date = current_date
                    self._save_data()
        except Exception as e:
            print(f"Error loading boop data: {e}")
            # Create the file if it doesn't exist
            self._save_data()

    def _save_data(self):
        """Save boop data to file"""
        try:
            data = {
                "total_boops": self.total_boops,
                "daily_boops": self.daily_boops,
                "last_date": self.last_date,
            }
            # Ensure directory exists
            Path(self.filename).parent.mkdir(parents=True, exist_ok=True)
            with open(self.filename, "w") as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Error saving boop data: {e}")

    def increment_boops(self):
        """Increment the boop counters if counter is enabled"""
        if not self.counter_enabled:
            return False

        # Check if we need to reset daily count
        current_date = self._get_current_date()
        if current_date != self.last_date:
            self.daily_boops = 0
            self.last_date = current_date

        # Increment counters
        self.total_boops += 1
        self.daily_boops += 1
        self._save_data()
        return True

    def set_counter_enabled(self, enabled):
        """Set whether the counter is enabled"""
        self.counter_enabled = enabled
        return self.counter_enabled

    def get_boops_data(self):
        """Get current boop counts"""
        return {
            "total_boops": self.total_boops,
            "daily_boops": self.daily_boops,
            "counter_enabled": self.counter_enabled,
        }
