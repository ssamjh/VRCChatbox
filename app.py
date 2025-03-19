import requests
from pythonosc import udp_client, osc_server, dispatcher
import time
import threading
from config import message_config
from placeholders import get_placeholder_value, data_cache
from boop_counter import BoopCounter


class VRChatMessenger:
    def __init__(self, ip="127.0.0.1", port=9000, listen_port=9001):
        self.client = udp_client.SimpleUDPClient(ip, port)
        self.active_messages = {}

        # Initialize messages once
        self._initialize_messages()

        # Add track of current song to detect changes
        self.current_song = None
        self.current_artist = None

        # Initialize the boop counter and share it with data_cache
        self.boop_counter = BoopCounter()
        from placeholders import data_cache

        data_cache.boop_counter = self.boop_counter  # Share the same instance

        # Setup OSC dispatcher for listening
        self.dispatcher = dispatcher.Dispatcher()
        self.dispatcher.map("/avatar/parameters/OSCBoop", self._handle_boop)
        self.dispatcher.map(
            "/avatar/parameters/BoopCounterEnabled", self._handle_boop_counter_enabled
        )

        # Setup OSC server for listening
        self.server = osc_server.ThreadingOSCUDPServer(
            (ip, listen_port), self.dispatcher
        )
        print(f"OSC Server initialized on {ip}:{listen_port}")
        self.server_thread = threading.Thread(
            target=self.server.serve_forever, daemon=True
        )

        # Add a thread just for checking song changes
        self.song_check_thread = threading.Thread(
            target=self._check_song_changes, daemon=True
        )

        # Start threads
        print(f"Starting OSC listener thread on port {listen_port}...")
        self.server_thread.start()
        self.song_check_thread.start()
        print(
            f"OSC listener thread started. Waiting for messages on {ip}:{listen_port}"
        )

    def _initialize_messages(self):
        """Initialize messages once rather than continuously updating them"""
        for category, config in message_config.items():
            if category != "placeholders":
                messages = config["messages"]
                raw_message = messages[0]  # Always use the first message
                formatted_message = self._format_message(raw_message)
                self.active_messages[category] = {
                    "message": formatted_message,
                }
        self.update_display()

    def _check_song_changes(self):
        """Periodically check for song changes"""
        while True:
            if self.check_for_song_change():
                self.update_display()
            time.sleep(5)  # Check every 5 seconds

    def check_for_song_change(self):
        """Check if song has changed and update display if needed"""
        jmm_data = data_cache.get_jmm_data()
        if not jmm_data.get("metadata"):
            return False

        metadata = jmm_data["metadata"]
        if not metadata["current"]["playing"]:
            # If music stopped playing, update display to remove music info
            if self.current_song is not None or self.current_artist is not None:
                self.current_song = None
                self.current_artist = None
                return True
            return False

        new_song = metadata["current"]["song"]
        new_artist = (
            ", ".join(artist["name"] for artist in metadata["current"]["artist"])
            if metadata["current"]["artist"]
            else ""
        )

        if new_song != self.current_song or new_artist != self.current_artist:
            self.current_song = new_song
            self.current_artist = new_artist

            # Update the music-related messages
            if "joinmymusic_song" in self.active_messages:
                self.active_messages["joinmymusic_song"]["message"] = (
                    self._format_message(
                        message_config["joinmymusic_song"]["messages"][0]
                    )
                )

            if "joinmymusic_artist" in self.active_messages:
                self.active_messages["joinmymusic_artist"]["message"] = (
                    self._format_message(
                        message_config["joinmymusic_artist"]["messages"][0]
                    )
                )

            if "joinmymusic_info" in self.active_messages:
                self.active_messages["joinmymusic_info"]["message"] = (
                    self._format_message(
                        message_config["joinmymusic_info"]["messages"][0]
                    )
                )

            return True
        return False

    def _handle_boop(self, address, *args):
        print(f"OSC message received: {address} with args: {args}")
        if args and args[0]:  # Check if there's a value and it's truthy
            if self.boop_counter.increment_boops():
                print(
                    f"Boop received! Total: {self.boop_counter.total_boops}, Daily: {self.boop_counter.daily_boops}"
                )

                # Update the time message
                if "time" in self.active_messages:
                    self.active_messages["time"]["message"] = self._format_message(
                        message_config["time"]["messages"][0]
                    )

                # Update the boops message
                if "boops" in self.active_messages:
                    self.active_messages["boops"]["message"] = self._format_message(
                        message_config["boops"]["messages"][0]
                    )

                # Update display
                self.update_display()
            else:
                print(f"Boop ignored - counter disabled")
        else:
            print(f"Boop ignored - value was: {args}")

    def _handle_boop_counter_enabled(self, address, *args):
        print(f"OSC message received: {address} with args: {args}")
        if args:
            enabled = bool(args[0])
            was_enabled = self.boop_counter.counter_enabled
            self.boop_counter.set_counter_enabled(enabled)
            print(f"Boop counter {'enabled' if enabled else 'disabled'}")

            # Update display if the enabled state changed
            if was_enabled != enabled:
                self.update_display()
        else:
            print(f"Boop counter enable message had no arguments")

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
        # For boops, only show if counter is enabled
        if category == "boops":
            return self.boop_counter.counter_enabled

        # For JoinMyMusic related categories
        if category.startswith("joinmymusic"):
            jmm_data = data_cache.get_jmm_data()
            if not jmm_data.get("metadata"):
                return False
            if not jmm_data["metadata"]["current"]["playing"]:
                return False
            if category in ["joinmymusic_artist", "joinmymusic_song"]:
                if not jmm_data["metadata"]["current"]["song"]:
                    return False
            return True

        # Time is always shown
        if category == "time":
            return True

        return True

    def update_display(self):
        """Update the display with the current active messages"""
        # Always update time message first
        if "time" in self.active_messages:
            self.active_messages["time"]["message"] = self._format_message(
                message_config["time"]["messages"][0]
            )

        # Define the display order
        display_order = [
            "time",
            "boops",
            "joinmymusic_info",
            "joinmymusic_artist",
            "joinmymusic_song",
        ]

        active_lines = []
        for category in display_order:
            if category in self.active_messages:
                message = self.active_messages[category]["message"]
                if self._should_show_message(category, message):
                    active_lines.append(message)

        combined_message = "\n".join(active_lines)
        self.client.send_message("/chatbox/input", [combined_message, True, True])
        print(f"Display updated:\n{combined_message}")


def main():
    vrc = VRChatMessenger()

    # Test that OSC is properly set up by sending a test message
    import time
    from pythonosc import udp_client

    print("Testing OSC with local message...")
    # Wait a moment for server to start
    time.sleep(1)

    # Create a test client that sends to our own server
    test_client = udp_client.SimpleUDPClient("127.0.0.1", 9001)

    # Send test messages
    print("Sending test boop counter enable message...")
    test_client.send_message("/avatar/parameters/BoopCounterEnabled", 1)
    time.sleep(0.5)

    print("Sending test boop message...")
    test_client.send_message("/avatar/parameters/OSCBoop", 1)
    time.sleep(0.5)

    print("OSC test complete")

    try:
        print("VRChat Dynamic Chat Message Sender running...")
        print("Listening for boops on port 9001...")
        print("Press Ctrl+C to exit")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nExiting...")


if __name__ == "__main__":
    main()
