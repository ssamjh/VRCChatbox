from pythonosc import udp_client, osc_server, dispatcher
import time
import threading
from config import message_config, load_app_config, save_app_config, reload_message_config
from placeholders import get_placeholder_value, data_cache
from bpm import bpm_monitor
from boop_counter import BoopCounter
from shockosc import ShockOSCController
from slide import SlideController
from shock_panel import ShockPanelController
from whisper_stt import WhisperSTTController


class VRChatMessenger:
    def __init__(self, ip="127.0.0.1", port=9000, listen_port=9001):
        self.client = udp_client.SimpleUDPClient(ip, port)
        self.active_messages = {}

        # Rate limiting variables
        self.last_message_time = 0
        self.rate_limit = 1.5  # Minimum seconds between messages
        self.update_pending = False
        self.update_needed = False

        # Simple boop display flag
        self.show_boops = False
        self._last_bpm_connected = False

        # Load app configuration
        self.app_config = load_app_config()
        self.show_music = self.app_config.get("show_music", True)
        self.show_time = self.app_config.get("show_time", True)

        # Refresh the chatbox the instant a new heart rate arrives (capped by
        # the 1.5s rate limit) rather than waiting for the 5s poll loop.
        bpm_monitor.set_on_update(self.request_display_update)

        # Add track of current song to detect changes
        self.current_song = None
        self.current_artist = None

        # Initialize ShockOSC controller with callback
        self.shock_controller = ShockOSCController(ip, port, self._on_shock_triggered)
        shock_config = self.app_config.get("shockosc", {})
        self.shock_controller.update_config(shock_config)

        # Set internet shock callback
        self.shock_controller.set_internet_shock_callback(self._on_internet_shock)

        # Start SignalR connection if token is available
        if shock_config.get("openshock_token"):
            print("OpenShock token found, starting SignalR connection for real-time events...")
            self.shock_controller.start_signalr_connection()

        # Shock display state
        self.show_shock_info = False
        self.shock_hide_timer = None

        # Internet shock display state
        self.show_internet_shock_info = False
        self.internet_shock_hide_timer = None

        # Speech-to-text display state (controller is created later, but these
        # must exist before _initialize_messages() runs its first display update)
        self.stt_text = ""
        self.show_stt = False
        self.stt_typing_active = False
        self.stt_final_linger = 4.0  # seconds a finalized line stays before clearing
        self._stt_hide_timer = None
        
        # Contact hold tracking
        self.contact_start_times = {}  # Track when contact started for each group
        self.hold_timers = {}  # Track hold timers for each group

        # Initialize the boop counter and share it with data_cache
        self.boop_counter = BoopCounter()
        data_cache.boop_counter = self.boop_counter  # Share the same instance

        # Start SSE listener for JoinMyMusic
        jmm_config = self.app_config.get("joinmymusic", {})
        sse_url = jmm_config.get("sse_url", "https://joinmymusic.com/api/events")
        data_cache.start_sse(sse_url)

        # Initialize messages AFTER boop_counter is set up
        self._initialize_messages()

        # Setup OSC dispatcher for listening
        self._monitor_callback = None
        self.dispatcher = dispatcher.Dispatcher()
        self.dispatcher.map("*", self._forward_to_monitor)
        self.dispatcher.map("/avatar/parameters/OSCBoop", self._handle_boop)

        # Add ShockOSC parameter listeners
        self.dispatcher.map("/avatar/parameters/ShockOsc/leftleg", self._handle_shock_trigger)
        self.dispatcher.map("/avatar/parameters/ShockOsc/rightleg", self._handle_shock_trigger)

        # Initialize Slide controller (after dispatcher is created)
        self.slide_controller = SlideController(
            dispatcher=self.dispatcher,
            shock_controller=self.shock_controller
        )
        slide_config = self.app_config.get("slide", {})
        self.slide_controller.update_config(slide_config)

        # Initialize Shock Panel controller
        self.shock_panel_controller = ShockPanelController(
            osc_client=self.client,
            shock_controller=self.shock_controller,
            dispatcher=self.dispatcher,
        )
        self.shock_panel_controller.on_state_change = self._on_shock_panel_state_change
        panel_config = self.app_config.get("shock_panel", {})
        self.shock_panel_controller.update_config(panel_config)

        # Speech-to-text controller (display state set up earlier in __init__)
        self.stt_controller = WhisperSTTController(
            on_partial=self._on_stt_partial,
            on_final=self._on_stt_final,
            on_state=self._on_stt_state,
        )
        self.stt_controller.update_config(self.app_config.get("whisper", {}))

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

        # Add a thread for rate-limited updates
        self.update_thread = threading.Thread(
            target=self._rate_limited_updates, daemon=True
        )

        # Start threads
        print(f"Starting OSC listener thread on port {listen_port}...")
        self.server_thread.start()
        self.song_check_thread.start()
        self.update_thread.start()
        print(
            f"OSC listener thread started. Waiting for messages on {ip}:{listen_port}"
        )

    def _forward_to_monitor(self, address, *args):
        if self._monitor_callback:
            self._monitor_callback(address, args)

    def set_monitor_callback(self, cb):
        self._monitor_callback = cb

    def _rate_limited_updates(self):
        """Thread that handles sending updates at a rate-limited pace"""
        while True:
            if self.update_needed and not self.update_pending:
                current_time = time.time()
                time_since_last = current_time - self.last_message_time

                if time_since_last >= self.rate_limit:
                    self.update_pending = True
                    self.update_needed = False
                    self._send_display_update()
                    self.last_message_time = time.time()
                    self.update_pending = False

            time.sleep(0.1)  # Small sleep to avoid CPU spinning

    def _send_display_update(self):
        """Send the actual display update to VRChat"""
        print(f"Display update triggered. Shock info active: {self.show_shock_info}")
        
        # Define the display order
        display_order = [
            "time",
            "bpm",
            "boops",
            "shock_info",  # Local shock info has highest priority
            "internet_shock_info",  # Internet shock info second priority
            "joinmymusic_info",
            "joinmymusic_artist",
            "joinmymusic_song",
        ]

        # Always refresh live-value messages before sending
        if "time" in self.active_messages:
            self.active_messages["time"]["message"] = self._format_message(
                message_config["time"]["messages"][0]
            )
        if "bpm" in self.active_messages:
            self.active_messages["bpm"]["message"] = self._format_message(
                message_config["bpm"]["messages"][0]
            )

        active_lines = []

        # Live speech-to-text sits above everything else as the top line.
        stt_line = self._get_stt_line()
        if stt_line:
            active_lines.append(stt_line)

        for category in display_order:
            if category in self.active_messages:
                message = self.active_messages[category]["message"]
                if self._should_show_message(category, message):
                    active_lines.append(message)

        combined_message = self._clamp_chatbox(active_lines)
        self.client.send_message("/chatbox/input", [combined_message, True, False])
        print(f"Display updated:\n{combined_message}")

    def _get_stt_line(self):
        """Current transcription as a single line, tail-truncated to max_chars.

        Keeping the tail means the most recently spoken words stay visible while
        you talk, which reads more naturally than clipping the start."""
        if not self.show_stt or not self.stt_text:
            return ""
        text = " ".join(self.stt_text.split())  # collapse newlines/whitespace
        max_chars = self.app_config.get("whisper", {}).get("max_chars", 120)
        if len(text) > max_chars:
            tail = text[-max_chars:]
            # Avoid starting mid-word when possible.
            space = tail.find(" ")
            text = "…" + (tail[space + 1:] if 0 <= space < 20 else tail)
        return text

    @staticmethod
    def _clamp_chatbox(lines):
        """Join lines respecting VRChat's 9-line / 144-char chatbox limits.

        Lines are kept in priority order (STT first), trimming from the bottom."""
        lines = lines[:9]
        combined = "\n".join(lines)
        if len(combined) > 144:
            combined = combined[:144]
        return combined

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
        self._send_display_update()
        self.last_message_time = time.time()

    def _check_song_changes(self):
        """Periodically check for song changes and date changes"""
        last_checked_date = self.boop_counter._get_current_date()

        while True:
            # Check for date change
            current_date = self.boop_counter._get_current_date()
            if current_date != last_checked_date:
                print(f"Date changed from {last_checked_date} to {current_date}")
                last_checked_date = current_date

                # Update the boop counter for the new day
                self.boop_counter._load_data()  # This will reset daily boops if needed

                # If we're currently showing boops, update the display with new count
                if self.show_boops:
                    if "boops" in self.active_messages:
                        self.active_messages["boops"]["message"] = self._format_message(
                            message_config["boops"]["messages"][0]
                        )
                    self.request_display_update()

            # Check for song change (existing code)
            if self.check_for_song_change():
                # When song changes, hide the boop counter until next boop
                self.show_boops = False
                # Mark this as a song change update (will be blocked during shock)
                self.request_display_update(from_song_change=True)

            # Refresh display when BPM connection state changes. The live value
            # itself is pushed via bpm_monitor's on_update callback, so no need
            # to poll it here.
            bpm_connected = bpm_monitor.is_connected()
            if bpm_connected != self._last_bpm_connected:
                self._last_bpm_connected = bpm_connected
                self.request_display_update()

            time.sleep(5)  # Check every 5 seconds

    def check_for_song_change(self):
        """Check if song has changed and update display if needed"""
        jmm_data = data_cache.get_jmm_data()
        if not jmm_data.get("metadata"):
            return False

        metadata = jmm_data["metadata"]
        if not metadata.get("playing"):
            # If music stopped playing, update display to remove music info
            if self.current_song is not None or self.current_artist is not None:
                self.current_song = None
                self.current_artist = None
                return True
            return False

        new_song = metadata.get("song")
        new_artist = (
            ", ".join(artist["name"] for artist in metadata["artist"])
            if metadata.get("artist")
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
            # Always increment the counter regardless of whether we're showing it
            self.boop_counter.increment_boops()
            print(
                f"Boop received! Total: {self.boop_counter.total_boops}, Daily: {self.boop_counter.daily_boops}"
            )

            # Show boops and update the message
            self.show_boops = True
            if "boops" in self.active_messages:
                self.active_messages["boops"]["message"] = self._format_message(
                    message_config["boops"]["messages"][0]
                )

            # Request an update - this won't send immediately if rate-limited
            self.request_display_update()
        else:
            print(f"Boop ignored - value was: {args}")

    def _handle_shock_trigger(self, address, *args):
        """Handle ShockOSC trigger from contact receivers with hold time logic"""
        print(f"Shock trigger received: {address} with args: {args}")
        
        # Extract group name from address (e.g., "/avatar/parameters/ShockOsc/leftleg" -> "leftleg")
        group = address.split("/")[-1]
        
        if args and args[0]:  # Contact started/maintained
            current_time = time.time()
            
            # If this is a new contact, start tracking
            if group not in self.contact_start_times:
                self.contact_start_times[group] = current_time
                print(f"Contact started for group: {group}")
                
                # Get hold time from config
                hold_time = self.app_config.get("shockosc", {}).get("hold_time", 0.5)
                
                # If hold time is 0, trigger immediately
                if hold_time <= 0:
                    print(f"No hold time required, triggering shock immediately for group: {group}")
                    self.shock_controller.send_shock([group])
                else:
                    # Schedule shock after hold time
                    print(f"Starting {hold_time}s hold timer for group: {group}")
                    hold_timer = threading.Timer(hold_time, self._trigger_held_shock, [group])
                    self.hold_timers[group] = hold_timer
                    hold_timer.start()
        else:  # Contact ended
            if group in self.contact_start_times:
                contact_duration = time.time() - self.contact_start_times[group]
                print(f"Contact ended for group: {group} after {contact_duration:.2f}s")
                
                # Cancel any pending shock timer
                if group in self.hold_timers:
                    self.hold_timers[group].cancel()
                    del self.hold_timers[group]
                    print(f"Cancelled hold timer for group: {group}")
                
                # Clear contact tracking
                del self.contact_start_times[group]
    
    def _trigger_held_shock(self, group):
        """Trigger shock after hold time has been met"""
        # Check if contact is still active
        if group in self.contact_start_times:
            hold_time = self.app_config.get("shockosc", {}).get("hold_time", 0.5)
            contact_duration = time.time() - self.contact_start_times[group]
            print(f"Hold time met for group: {group} (held for {contact_duration:.2f}s, required {hold_time}s)")
            
            # Send shock to the specific group
            self.shock_controller.send_shock([group])
            
            # Clear the timer reference
            if group in self.hold_timers:
                del self.hold_timers[group]
        else:
            print(f"Contact no longer active for group: {group}, shock cancelled")

    def _on_shock_triggered(self, intensity, group, duration=0):
        """Callback when a shock is triggered"""
        print(f"Shock callback: {intensity}% on {group}")

        # Update shock data in cache
        data_cache.update_shock_data(intensity, group, duration)
        
        # Update shock info message
        if "shock_info" in self.active_messages:
            self.active_messages["shock_info"]["message"] = self._format_message(
                message_config["shock_info"]["messages"][0]
            )
        
        # Show shock info
        self.show_shock_info = True
        
        # Cancel any existing hide timer
        if self.shock_hide_timer:
            self.shock_hide_timer.cancel()
        
        # Set timer to hide shock info after 5 seconds
        self.shock_hide_timer = threading.Timer(5.0, self._hide_shock_info)
        self.shock_hide_timer.start()
        
        # Request display update
        self.request_display_update()
    
    def _hide_shock_info(self):
        """Hide shock info display"""
        self.show_shock_info = False
        self.shock_hide_timer = None
        # Send empty message to clear the chatbox
        self.client.send_message("/chatbox/input", ["", True, False])
        print("Shock info hidden - chatbox cleared")

    def _on_internet_shock(self, user_name, real_name, shocker_name, type_name, intensity, duration, is_guest=False, share_link_id=None):
        """Callback when an internet shock is received"""
        shock_config = self.app_config.get("shockosc", {})
        if not shock_config.get("show_internet_shocks", True):
            print(f"Internet {type_name} from {user_name} ignored - display disabled")
            return

        # Check if user is in ignored list
        ignored_users = shock_config.get("ignored_shock_users", [])
        if user_name in ignored_users:
            print(f"Internet {type_name} from {user_name} ignored - user in ignored list")
            return

        print(f"Internet {type_name} callback: {intensity}% from {user_name} ({real_name})")

        # Update internet shock data in cache
        from placeholders import data_cache
        data_cache.update_internet_shock_data(
            user_name=user_name,
            real_name=real_name,
            shocker_name=shocker_name,
            type_name=type_name,
            intensity=intensity,
            duration=duration,
            is_guest=is_guest,
            share_link_id=share_link_id
        )

        # Update internet shock info message
        if "internet_shock_info" in self.active_messages:
            self.active_messages["internet_shock_info"]["message"] = self._format_message(
                message_config["internet_shock_info"]["messages"][0]
            )

        # Show internet shock info
        self.show_internet_shock_info = True

        # Cancel any existing hide timer
        if self.internet_shock_hide_timer:
            self.internet_shock_hide_timer.cancel()

        # Set timer to hide internet shock info after 10 seconds
        self.internet_shock_hide_timer = threading.Timer(10.0, self._hide_internet_shock_info)
        self.internet_shock_hide_timer.start()

        # Request display update
        self.request_display_update()

    def _hide_internet_shock_info(self):
        """Hide internet shock info display"""
        self.show_internet_shock_info = False
        self.internet_shock_hide_timer = None
        # Send empty message to clear the chatbox (same behavior as OSC shocks)
        self.client.send_message("/chatbox/input", ["", True, False])
        print("Internet shock info hidden - chatbox cleared")

    def _on_stt_partial(self, text):
        """Live partial transcription while the user is speaking."""
        if not text:
            return
        # Still talking — cancel any pending clear from a previous utterance.
        if self._stt_hide_timer:
            self._stt_hide_timer.cancel()
            self._stt_hide_timer = None
        self.stt_text = text
        self.show_stt = True
        self.request_display_update()

    def _on_stt_final(self, text):
        """Finalized transcription once speech stops; lingers, then clears."""
        self.stt_text = text or ""
        self.show_stt = bool(self.stt_text)
        self.request_display_update()
        if self._stt_hide_timer:
            self._stt_hide_timer.cancel()
        if self.show_stt:
            self._stt_hide_timer = threading.Timer(self.stt_final_linger, self._hide_stt)
            self._stt_hide_timer.start()

    def _hide_stt(self):
        self.show_stt = False
        self.stt_text = ""
        self._stt_hide_timer = None
        self.request_display_update()

    def _on_stt_state(self, active):
        """Drive the VRChat typing indicator with speech start/stop."""
        if active == self.stt_typing_active:
            return
        self.stt_typing_active = active
        try:
            self.client.send_message("/chatbox/typing", [active])
        except Exception as e:
            print(f"Failed to send typing indicator: {e}")

    def update_whisper_config(self, whisper_config):
        """Update speech-to-text configuration"""
        self.app_config["whisper"] = whisper_config
        save_app_config(self.app_config)
        if hasattr(self, 'stt_controller'):
            self.stt_controller.update_config(whisper_config)
        # If STT was just turned off, clear any transcription still on screen.
        if not whisper_config.get("enabled") and self.show_stt:
            self._hide_stt()

    def clear_all_hold_timers(self):
        """Clear all active hold timers"""
        for group, timer in list(self.hold_timers.items()):
            timer.cancel()
            print(f"Cleared hold timer for group: {group}")
        self.hold_timers.clear()
        self.contact_start_times.clear()

    def update_shock_config(self, shock_config):
        """Update ShockOSC configuration"""
        self.app_config["shockosc"] = shock_config
        save_app_config(self.app_config)
        self.shock_controller.update_config(shock_config)

    def update_slide_config(self, slide_config):
        """Update Slide configuration"""
        self.app_config["slide"] = slide_config
        save_app_config(self.app_config)
        if hasattr(self, 'slide_controller'):
            self.slide_controller.update_config(slide_config)

    def update_shock_panel_config(self, panel_config):
        """Update Shock Panel configuration"""
        self.app_config["shock_panel"] = panel_config
        save_app_config(self.app_config)
        if hasattr(self, 'shock_panel_controller'):
            self.shock_panel_controller.update_config(panel_config)
            # This path is only hit on explicit UI changes, so it's safe to push
            # our values to the avatar here (startup uses update_config directly).
            self.shock_panel_controller.broadcast_all()

    def _on_shock_panel_state_change(self):
        """Persist shock panel state changed via OSC (global intensities, per-entry enabled)."""
        self.app_config["shock_panel"] = self.shock_panel_controller.config
        save_app_config(self.app_config)

    def update_app_config(self, new_config):
        """Update full app configuration including messages"""
        self.app_config.update(new_config)
        save_app_config(self.app_config)
        reload_message_config()  # Reload message templates from updated config

    def cleanup(self):
        """Clean up resources when shutting down"""
        print("Cleaning up VRChatMessenger...")

        # Cancel internet shock timer
        if hasattr(self, 'internet_shock_hide_timer') and self.internet_shock_hide_timer:
            self.internet_shock_hide_timer.cancel()

        if hasattr(self, 'shock_controller'):
            self.shock_controller.cleanup()

        # Stop slide polling
        if hasattr(self, 'slide_controller'):
            self.slide_controller.stop_polling()

        # Stop shock panel holds
        if hasattr(self, 'shock_panel_controller'):
            self.shock_panel_controller.cleanup()

        # Stop speech-to-text
        if hasattr(self, 'stt_controller'):
            self.stt_controller.cleanup()
        if getattr(self, '_stt_hide_timer', None):
            self._stt_hide_timer.cancel()

        # Stop OSC server
        if hasattr(self, 'server'):
            self.server.shutdown()

        # Cleanly tear down the BLE heart-rate link so the sensor is free to
        # reconnect on the next launch.
        bpm_monitor.shutdown()

    def request_display_update(self, force_for_shock=False, from_song_change=False):
        """Request a display update, respecting rate limits"""
        if self.show_shock_info and from_song_change:
            print("Blocked song change update - shock info is active")
            return
        self.update_needed = True

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
        # For boops, only show if there's been a recent boop
        if category == "boops":
            return self.show_boops

        # For shock info - show when active and enabled, highest priority
        if category == "shock_info":
            shock_config = self.app_config.get("shockosc", {})
            if not shock_config.get("show_shock_info", True):
                return False
            return self.show_shock_info

        # For internet shock info - show when active and enabled, but hide if local shock is active
        if category == "internet_shock_info":
            # Hide internet shock info if local shock info is showing
            if self.show_shock_info:
                shock_config = self.app_config.get("shockosc", {})
                if shock_config.get("show_shock_info", True):
                    return False

            shock_config = self.app_config.get("shockosc", {})
            if not shock_config.get("show_internet_shocks", True):
                return False
            return self.show_internet_shock_info

        # For JoinMyMusic related categories
        if category.startswith("joinmymusic"):
            # Hide music if any shock info is showing (shock overrides music)
            if self.show_internet_shock_info:
                shock_config = self.app_config.get("shockosc", {})
                if shock_config.get("show_internet_shocks", True):
                    return False

            if self.show_shock_info:
                shock_config = self.app_config.get("shockosc", {})
                if shock_config.get("show_shock_info", True):
                    return False
            
            # Check if music display is enabled
            if not self.show_music:
                return False
                
            jmm_data = data_cache.get_jmm_data()
            if not jmm_data.get("metadata"):
                return False
            if not jmm_data["metadata"].get("playing"):
                return False
            if category in ["joinmymusic_artist", "joinmymusic_song"]:
                if not jmm_data["metadata"].get("song"):
                    return False
            return True

        # BPM is shown only when connected AND we have a real numeric reading
        # (get_bpm() is 0 before the first valid measurement / on a dropped read).
        if category == "bpm":
            return bpm_monitor.is_connected() and bpm_monitor.get_bpm() > 0

        # Time is shown only when enabled
        if category == "time":
            return self.show_time

        return True

    def toggle_music_display(self, show_music):
        """Toggle music display and save to config"""
        self.show_music = show_music
        self.app_config["show_music"] = show_music
        save_app_config(self.app_config)
        self.request_display_update()

    def toggle_time_display(self, show_time):
        """Toggle time display and save to config"""
        self.show_time = show_time
        self.app_config["show_time"] = show_time
        save_app_config(self.app_config)
        self.request_display_update()


def main():
    import sys

    gui_mode = "--gui" in sys.argv or getattr(sys, "frozen", False)

    try:
        vrc = VRChatMessenger()
    except OSError as e:
        if e.winerror == 10048 or "address already in use" in str(e).lower():
            msg = "Could not start: OSC port 9001 is already in use.\n\nAnother instance may already be running."
            if gui_mode:
                from PyQt6.QtWidgets import QApplication, QMessageBox
                _app = QApplication.instance() or QApplication(sys.argv)
                QMessageBox.critical(None, "VRCChatbox — Port conflict", msg)
            else:
                print(f"Error: {msg}")
            return
        raise

    if gui_mode:
        try:
            from gui import show_settings_gui
            print("Opening settings GUI...")
            show_settings_gui(vrc)
        except ImportError:
            print("GUI not available (PyQt6 not installed). Run: pip install PyQt6")
        return

    try:
        print("VRChat Dynamic Chat Message Sender running...")
        print("Listening for boops on port 9001...")
        print("Run with --gui to open settings")
        print("Press Ctrl+C to exit")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        vrc.cleanup()


if __name__ == "__main__":
    main()
