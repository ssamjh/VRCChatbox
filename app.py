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
        self.update_thread = threading.Thread(target=self._update_messages, daemon=True)

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

        # Start threads
        self.update_thread.start()
        print(f"Starting OSC listener thread on port {listen_port}...")
        self.server_thread.start()
        print(
            f"OSC listener thread started. Waiting for messages on {ip}:{listen_port}"
        )

    def _handle_boop(self, address, *args):
        print(f"OSC message received: {address} with args: {args}")
        if args and args[0]:  # Check if there's a value and it's truthy
            if self.boop_counter.increment_boops():
                print(
                    f"Boop received! Total: {self.boop_counter.total_boops}, Daily: {self.boop_counter.daily_boops}"
                )

                # Get current boops message and update it immediately
                if "boops" in self.active_messages:
                    current_message = message_config["boops"]["messages"][0]
                    boops_data = self.boop_counter.get_boops_data()

                    # Format the message with updated boop counts
                    formatted_message = current_message.format(
                        daily_boops=boops_data["daily_boops"],
                        total_boops=boops_data["total_boops"],
                    )

                    # Update the active message
                    self.active_messages["boops"]["message"] = formatted_message

                    # Send an immediate display update without changing other messages
                    active_lines = []
                    for category in message_config:
                        if (
                            category != "placeholders"
                            and category in self.active_messages
                        ):
                            message = self.active_messages[category]["message"]
                            if self._should_show_message(category, message):
                                active_lines.append(message)

                    combined_message = "\n".join(active_lines)
                    self.client.send_message(
                        "/chatbox/input", [combined_message, True, True]
                    )
                    print(f"Display updated with new boop count:\n{combined_message}")
            else:
                print(f"Boop ignored - counter disabled")
        else:
            print(f"Boop ignored - value was: {args}")

    def _handle_boop_counter_enabled(self, address, *args):
        print(f"OSC message received: {address} with args: {args}")
        if args:
            enabled = bool(args[0])
            self.boop_counter.set_counter_enabled(enabled)
            print(f"Boop counter {'enabled' if enabled else 'disabled'}")
        else:
            print(f"Boop counter enable message had no arguments")

    def _update_messages(self):
        while True:
            for category, config in message_config.items():
                if category != "placeholders":
                    if category not in self.active_messages:
                        self.active_messages[category] = {
                            "current_index": 0,
                            "message": "Initializing...",
                        }

                    messages = config["messages"]
                    current_index = self.active_messages[category]["current_index"]
                    raw_message = messages[current_index]
                    formatted_message = self._format_message(raw_message)
                    self.active_messages[category]["message"] = formatted_message
                    self.active_messages[category]["current_index"] = (
                        current_index + 1
                    ) % len(messages)

            self.update_display()
            time.sleep(5)

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
