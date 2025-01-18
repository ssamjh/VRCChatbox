import requests
from pythonosc import udp_client
import time
import threading
from config import message_config
from placeholders import get_placeholder_value, data_cache


class VRChatMessenger:
    def __init__(self, ip="127.0.0.1", port=9000):
        self.client = udp_client.SimpleUDPClient(ip, port)
        self.active_messages = {}
        self.initialize_message_threads()

    def initialize_message_threads(self):
        for category, config in message_config.items():
            if category != "placeholders":
                self.active_messages[category] = {
                    "current_index": 0,
                    "message": "Initializing...",
                }
                thread = threading.Thread(
                    target=self._update_category_messages, args=(category,), daemon=True
                )
                thread.start()

    def _update_category_messages(self, category):
        while True:
            config = message_config[category]
            messages = config["messages"]
            current_index = self.active_messages[category]["current_index"]

            raw_message = messages[current_index]
            formatted_message = self._format_message(raw_message)

            self.active_messages[category]["message"] = formatted_message
            self.active_messages[category]["current_index"] = (current_index + 1) % len(
                messages
            )

            self.update_display()
            time.sleep(config["rotation_interval"])

    def _format_message(self, message):
        try:
            placeholders = {
                key: get_placeholder_value(key)
                for key in message_config["placeholders"]
            }
            return message.format(**placeholders)
        except KeyError as e:
            return f"Error: Missing placeholder {e}"

    def _should_show_message(self, category, message):
        if category in ["joinmymusic_info", "joinmymusic_np1", "joinmymusic_np2"]:
            jmm_data = data_cache.get_jmm_data()
            if not jmm_data.get("metadata"):
                return False
            if not jmm_data["metadata"]["current"]["playing"]:
                return False
            if not jmm_data["metadata"]["current"]["song"]:
                return False
            return True
        return True

    def update_display(self):
        active_lines = []
        for category in message_config:
            if category != "placeholders" and category in self.active_messages:
                message = self.active_messages[category]["message"]
                if self._should_show_message(category, message):
                    active_lines.append(message)

        combined_message = "\n".join(active_lines)
        self.client.send_message("/chatbox/input", [combined_message, True, True])
        print(f"Display updated:\n{combined_message}")


def main():
    vrc = VRChatMessenger()
    try:
        print("VRChat Dynamic Chat Message Sender running...")
        print("Press Ctrl+C to exit")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nExiting...")


if __name__ == "__main__":
    main()
