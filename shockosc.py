import random
import threading
import time
import requests
import asyncio
import json
import websockets
import requests
from urllib.parse import urlencode
from pythonosc import udp_client


class ShockOSCController:
    def __init__(self, ip="127.0.0.1", port=9000, shock_callback=None):
        """Initialize ShockOSC controller"""
        self.client = udp_client.SimpleUDPClient(ip, port)
        self.config = {
            "enabled": False,
            "mode": "static",
            "static_intensity": 50,
            "random_min": 20,
            "random_max": 80,
            "duration": 1.0,
            "groups": ["leftleg", "rightleg"],
            "show_shock_info": True,
            "cooldown_delay": 5.0,
            "hold_time": 0.5,
            "openshock_token": "",
            "shockers": {},
            "openshock_url": "https://api.openshock.app",
            "show_internet_shocks": True
        }
        self.active_shocks = {}  # Track active shock timers
        self.cooldown_timers = {}  # Track cooldown timers per group
        self.cooldown_states = {}  # Track which groups are on cooldown
        self.shock_callback = shock_callback  # Callback to notify about shocks

        # SignalR connection properties
        self.websocket = None
        self.signalr_thread = None
        self.signalr_loop = None
        self.signalr_connected = False
        self.internet_shock_callback = None
        
    def update_config(self, new_config):
        """Update ShockOSC configuration"""
        old_token = self.config.get("openshock_token", "").strip()
        new_token = new_config.get("openshock_token", "").strip()

        self.config.update(new_config)
        print(f"ShockOSC config updated: {self.config}")

        # Start or restart SignalR connection only if token changed
        if new_token and new_token != old_token:
            self.start_signalr_connection()

    def set_internet_shock_callback(self, callback):
        """Set callback function for internet shock events"""
        self.internet_shock_callback = callback
        
    def get_shock_intensity(self):
        """Get shock intensity based on current mode"""
        if self.config["mode"] == "static":
            return self.config["static_intensity"]
        else:  # random mode
            min_val = self.config["random_min"]
            max_val = self.config["random_max"]
            return random.randint(min_val, max_val)
    
    def send_openshock_command(self, shocker_ids, intensity, duration, action_type=1):
        """Send command to OpenShock API using v2 endpoint
        action_type: 0=stop, 1=shock, 2=vibrate, 3=sound
        """
        token = self.config.get("openshock_token", "").strip()
        if not token:
            print("No OpenShock API token configured")
            return False
        
        if not shocker_ids:
            print("No shocker IDs provided")
            return False
        
        # Prepare the command data for v2 API format
        shocks = []
        for shocker_id in shocker_ids:
            shocks.append({
                "id": shocker_id,
                "type": action_type,
                "intensity": min(100, max(0, int(intensity))),  # Clamp to 0-100
                "duration": max(300, min(65535, int(duration * 1000)))  # V2 API requires 300-65535ms
            })
        
        data = {
            "shocks": shocks,
            "customName": "VRCChatbox"
        }
        
        headers = {
            "Open-Shock-Token": token,
            "User-Agent": "VRCChatbox-ShockOSC/1.0",
            "Content-Type": "application/json"
        }
        
        try:
            url = f"{self.config.get('openshock_url', 'https://api.openshock.app')}/2/shockers/control"
            
            response = requests.post(url, json=data, headers=headers, timeout=5)
            
            if response.status_code == 200:
                print(f"OpenShock command sent successfully: {len(shocker_ids)} shocker(s), {intensity}%, {duration}s")
                return True
            else:
                print(f"OpenShock API error {response.status_code}: {response.text}")
                return False
                
        except requests.RequestException as e:
            print(f"Failed to send OpenShock command: {e}")
            return False

    def is_group_on_cooldown(self, group):
        """Check if a group is currently on cooldown"""
        return self.cooldown_states.get(group, False)

    def start_cooldown(self, group):
        """Start cooldown for a group"""
        cooldown_delay = self.config.get("cooldown_delay", 5.0)
        
        # Skip cooldown if delay is 0
        if cooldown_delay <= 0:
            return
        
        print(f"Starting {cooldown_delay}s cooldown for group: {group}")
        
        # Set cooldown state
        self.cooldown_states[group] = True
        
        # Send OSC parameter to indicate cooldown started
        cooldown_address = f"/avatar/parameters/ShockOsc/{group}_Cooldown"
        self.client.send_message(cooldown_address, True)
        print(f"Sent cooldown start: {cooldown_address} = True")
        
        # Cancel any existing cooldown timer for this group
        if group in self.cooldown_timers:
            self.cooldown_timers[group].cancel()
        
        # Start new cooldown timer
        timer = threading.Timer(cooldown_delay, self._end_cooldown, [group])
        self.cooldown_timers[group] = timer
        timer.start()

    def _end_cooldown(self, group):
        """End cooldown for a group"""
        print(f"Cooldown ended for group: {group}")
        
        # Clear cooldown state
        self.cooldown_states[group] = False
        
        # Send OSC parameter to indicate cooldown ended
        cooldown_address = f"/avatar/parameters/ShockOsc/{group}_Cooldown"
        self.client.send_message(cooldown_address, False)
        print(f"Sent cooldown end: {cooldown_address} = False")
        
        # Clean up timer
        if group in self.cooldown_timers:
            del self.cooldown_timers[group]
    
    def send_shock(self, groups=None):
        """Send shock command to specified groups"""
        if not self.config["enabled"]:
            print("ShockOSC is disabled")
            return
            
        if groups is None:
            groups = self.config["groups"]
        
        # Filter out groups that are on cooldown
        available_groups = [group for group in groups if not self.is_group_on_cooldown(group)]
        
        if not available_groups:
            print(f"All groups are on cooldown: {groups}")
            return
        
        if len(available_groups) < len(groups):
            on_cooldown = [group for group in groups if self.is_group_on_cooldown(group)]
            print(f"Some groups on cooldown, skipping: {on_cooldown}")
        
        intensity = self.get_shock_intensity()
        duration = self.config["duration"]
        
        print(f"Sending shock - Groups: {available_groups}, Intensity: {intensity}%, Duration: {duration}s")
        
        # Check if we have OpenShock integration configured
        token = self.config.get("openshock_token", "").strip()
        shockers_config = self.config.get("shockers", {})
        
        openshock_sent = False
        if token and shockers_config:
            # Get shocker IDs for the available groups
            shocker_ids = []
            for group in available_groups:
                for shocker_id, assignment_info in shockers_config.items():
                    # Handle both old format (string) and new format (dict)
                    if isinstance(assignment_info, dict):
                        assigned_group = assignment_info.get("group", "")
                    else:
                        assigned_group = assignment_info
                    
                    if assigned_group == group:
                        shocker_ids.append(shocker_id)
            
            if shocker_ids:
                print(f"Using OpenShock API for shockers: {shocker_ids}")
                openshock_sent = self.send_openshock_command(shocker_ids, intensity, duration, action_type=1)
            else:
                print(f"No shockers assigned to groups: {available_groups}")
        
        # If OpenShock wasn't used or failed, fall back to OSC
        if not openshock_sent:
            print("Using OSC fallback method")
            # Convert intensity from 0-100 to 0.0-1.0 for OSC
            osc_intensity = intensity / 100.0
            
            for group in available_groups:
                # Use continuous shock parameter for duration control
                osc_address = f"/avatar/parameters/ShockOsc/{group}_CShock"
                
                # Send shock command
                self.client.send_message(osc_address, osc_intensity)
                print(f"Sent: {osc_address} = {osc_intensity}")
                
                # Schedule stop command after duration
                self._schedule_shock_stop(group, duration)

        # Handle cooldown and callbacks for all groups
        for group in available_groups:
            # Start cooldown for this group
            self.start_cooldown(group)

            # Notify callback about the shock
            if self.shock_callback:
                self.shock_callback(intensity, group, duration)
    
    def send_immediate_shock(self, groups=None):
        """Send immediate shock (ignores hold time)"""
        if not self.config["enabled"]:
            print("ShockOSC is disabled")
            return
            
        if groups is None:
            groups = self.config["groups"]
        
        # Filter out groups that are on cooldown
        available_groups = [group for group in groups if not self.is_group_on_cooldown(group)]
        
        if not available_groups:
            print(f"All groups are on cooldown: {groups}")
            return
        
        if len(available_groups) < len(groups):
            on_cooldown = [group for group in groups if self.is_group_on_cooldown(group)]
            print(f"Some groups on cooldown, skipping: {on_cooldown}")
        
        intensity = self.get_shock_intensity()
        duration = self.config["duration"]
        print(f"Sending immediate shock - Groups: {available_groups}, Intensity: {intensity}%")
        
        # Check if we have OpenShock integration configured
        token = self.config.get("openshock_token", "").strip()
        shockers_config = self.config.get("shockers", {})
        
        openshock_sent = False
        if token and shockers_config:
            # Get shocker IDs for the available groups
            shocker_ids = []
            for group in available_groups:
                for shocker_id, assignment_info in shockers_config.items():
                    # Handle both old format (string) and new format (dict)
                    if isinstance(assignment_info, dict):
                        assigned_group = assignment_info.get("group", "")
                    else:
                        assigned_group = assignment_info
                    
                    if assigned_group == group:
                        shocker_ids.append(shocker_id)
            
            if shocker_ids:
                print(f"Using OpenShock API for immediate shock: {shocker_ids}")
                openshock_sent = self.send_openshock_command(shocker_ids, intensity, duration, action_type=1)
        
        # If OpenShock wasn't used or failed, fall back to OSC
        if not openshock_sent:
            print("Using OSC fallback for immediate shock")
            for group in available_groups:
                # Use immediate shock parameter
                osc_address = f"/avatar/parameters/ShockOsc/{group}_IShock"
                self.client.send_message(osc_address, True)
                print(f"Sent: {osc_address} = True")

        # Handle cooldown and callbacks for all groups
        for group in available_groups:
            # Start cooldown for this group
            self.start_cooldown(group)

            # Notify callback about the shock
            if self.shock_callback:
                self.shock_callback(intensity, group, duration)
    
    def send_vibrate(self, groups=None):
        """Send vibration command"""
        if not self.config["enabled"]:
            print("ShockOSC is disabled")
            return
            
        if groups is None:
            groups = self.config["groups"]
        
        intensity = self.get_shock_intensity()
        duration = self.config["duration"]
        
        print(f"Sending vibration - Groups: {groups}, Intensity: {intensity}%, Duration: {duration}s")
        
        # Check if we have OpenShock integration configured
        token = self.config.get("openshock_token", "").strip()
        shockers_config = self.config.get("shockers", {})
        
        openshock_sent = False
        if token and shockers_config:
            # Get shocker IDs for the groups
            shocker_ids = []
            for group in groups:
                for shocker_id, assignment_info in shockers_config.items():
                    # Handle both old format (string) and new format (dict)
                    if isinstance(assignment_info, dict):
                        assigned_group = assignment_info.get("group", "")
                    else:
                        assigned_group = assignment_info
                    
                    if assigned_group == group:
                        shocker_ids.append(shocker_id)
            
            if shocker_ids:
                print(f"Using OpenShock API for vibration: {shocker_ids}")
                openshock_sent = self.send_openshock_command(shocker_ids, intensity, duration, action_type=2)
        
        # If OpenShock wasn't used or failed, fall back to OSC
        if not openshock_sent:
            print("Using OSC fallback for vibration")
            osc_intensity = intensity / 100.0
            
            for group in groups:
                osc_address = f"/avatar/parameters/ShockOsc/{group}_CVibrate"
                self.client.send_message(osc_address, osc_intensity)
                print(f"Sent: {osc_address} = {osc_intensity}")
                
                # Schedule stop command after duration
                self._schedule_vibrate_stop(group, duration)
    
    def stop_shock(self, groups=None):
        """Stop shock for specified groups"""
        if groups is None:
            groups = self.config["groups"]
            
        for group in groups:
            osc_address = f"/avatar/parameters/ShockOsc/{group}_CShock"
            self.client.send_message(osc_address, 0.0)
            print(f"Stopped shock: {osc_address} = 0.0")
            
            # Cancel any pending stop timer
            if group in self.active_shocks:
                self.active_shocks[group].cancel()
                del self.active_shocks[group]
    
    def stop_vibrate(self, groups=None):
        """Stop vibration for specified groups"""
        if groups is None:
            groups = self.config["groups"]
            
        for group in groups:
            osc_address = f"/avatar/parameters/ShockOsc/{group}_CVibrate"
            self.client.send_message(osc_address, 0.0)
            print(f"Stopped vibration: {osc_address} = 0.0")
    
    def _schedule_shock_stop(self, group, duration):
        """Schedule a shock stop after specified duration"""
        # Cancel any existing timer for this group
        if group in self.active_shocks:
            self.active_shocks[group].cancel()
        
        # Create new timer
        timer = threading.Timer(duration, self._stop_shock_timer, [group])
        self.active_shocks[group] = timer
        timer.start()
    
    def _schedule_vibrate_stop(self, group, duration):
        """Schedule a vibrate stop after specified duration"""
        timer = threading.Timer(duration, self._stop_vibrate_timer, [group])
        timer.start()
    
    def _stop_shock_timer(self, group):
        """Timer callback to stop shock"""
        osc_address = f"/avatar/parameters/ShockOsc/{group}_CShock"
        self.client.send_message(osc_address, 0.0)
        print(f"Timer stopped shock: {osc_address} = 0.0")
        
        if group in self.active_shocks:
            del self.active_shocks[group]
    
    def _stop_vibrate_timer(self, group):
        """Timer callback to stop vibration"""
        osc_address = f"/avatar/parameters/ShockOsc/{group}_CVibrate"
        self.client.send_message(osc_address, 0.0)
        print(f"Timer stopped vibration: {osc_address} = 0.0")
    
    def clear_cooldown(self, group):
        """Manually clear cooldown for a group"""
        if group in self.cooldown_timers:
            self.cooldown_timers[group].cancel()
            del self.cooldown_timers[group]
        
        self.cooldown_states[group] = False
        
        # Send OSC parameter to indicate cooldown ended
        cooldown_address = f"/avatar/parameters/ShockOsc/{group}_Cooldown"
        self.client.send_message(cooldown_address, False)
        print(f"Manually cleared cooldown for {group}")

    def clear_all_cooldowns(self):
        """Clear all cooldowns"""
        for group in list(self.cooldown_timers.keys()):
            self.clear_cooldown(group)
        print("All cooldowns cleared")

    def get_cooldown_status(self):
        """Get current cooldown status for all groups"""
        status = {}
        for group in self.config["groups"]:
            status[group] = self.is_group_on_cooldown(group)
        return status

    def start_signalr_connection(self):
        """Start SignalR connection to receive real-time shock events"""
        token = self.config.get("openshock_token", "").strip()
        if not token:
            print("No OpenShock token configured, skipping SignalR connection")
            return

        # Stop existing connection if running
        self.stop_signalr_connection()

        print("Starting OpenShock SignalR connection...")
        self.signalr_thread = threading.Thread(target=self._run_signalr_connection, daemon=True)
        self.signalr_thread.start()

    def stop_signalr_connection(self):
        """Stop SignalR connection"""
        if self.signalr_connected or self.websocket or self.signalr_thread:
            print("Stopping OpenShock SignalR connection...")

            # Mark as disconnected first to prevent new operations
            self.signalr_connected = False

            try:
                # Close the websocket if it exists
                if self.websocket and self.signalr_loop and not self.signalr_loop.is_closed():
                    asyncio.run_coroutine_threadsafe(
                        self.websocket.close(), self.signalr_loop
                    )

                # Wait for thread to finish (with timeout to prevent hanging)
                if self.signalr_thread and self.signalr_thread.is_alive():
                    self.signalr_thread.join(timeout=5.0)
                    if self.signalr_thread.is_alive():
                        print("Warning: SignalR thread did not stop within timeout")

            except Exception as e:
                print(f"Error stopping SignalR connection: {e}")

        # Clear all references
        self.websocket = None
        self.signalr_loop = None
        self.signalr_thread = None

    def _run_signalr_connection(self):
        """Run SignalR connection in a separate thread"""
        try:
            # Check if there's already a running loop in this thread
            try:
                existing_loop = asyncio.get_running_loop()
                if existing_loop:
                    print("Existing event loop detected, stopping it first...")
                    existing_loop.close()
            except RuntimeError:
                # No running loop, which is what we want
                pass

            # Create new event loop for this thread
            self.signalr_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.signalr_loop)

            # Run the async connection
            self.signalr_loop.run_until_complete(self._async_signalr_connection())
        except asyncio.CancelledError:
            print("SignalR connection was cancelled")
        except Exception as e:
            print(f"SignalR connection error: {e}")
        finally:
            # Properly close the event loop
            if self.signalr_loop and not self.signalr_loop.is_closed():
                try:
                    # Cancel all pending tasks
                    pending = asyncio.all_tasks(self.signalr_loop)
                    for task in pending:
                        task.cancel()

                    # Wait for tasks to finish cancellation with timeout
                    if pending:
                        try:
                            self.signalr_loop.run_until_complete(
                                asyncio.wait_for(
                                    asyncio.gather(*pending, return_exceptions=True),
                                    timeout=5.0
                                )
                            )
                        except asyncio.TimeoutError:
                            print("Timeout waiting for tasks to cancel")

                    # Now close the loop
                    self.signalr_loop.close()
                except Exception as e:
                    print(f"Error closing SignalR loop: {e}")

            # Clear the loop reference
            self.signalr_loop = None
            # Reset the thread-local event loop
            asyncio.set_event_loop(None)

    async def _async_signalr_connection(self):
        """Async SignalR connection method - based on test_openshock_signalr_fixed.py"""
        try:
            api_url = self.config.get('openshock_url', 'https://api.openshock.app')
            token = self.config.get("openshock_token", "").strip()

            # First, let's try to negotiate with SignalR
            await self.signalr_negotiate(api_url, token)

            # Build the SignalR connection URL - use API endpoint for SignalR
            # Convert https://api.shock.sjh.at to wss://api.shock.sjh.at
            ws_url = api_url.replace('https://', 'wss://').replace('http://', 'ws://')
            hub_url = f"{ws_url}/1/hubs/user"

            print(f"Connecting to OpenShock SignalR at: {hub_url}")

            # Connect using websockets with authentication header
            headers = {
                'User-Agent': 'VRCChatbox-ShockOSC/1.0',
                'Open-Shock-Token': token
            }

            # Add token as query parameter as well
            params = {'access_token': token}
            full_url = f"{hub_url}?{urlencode(params)}"

            print(f"Full WebSocket URL: {full_url}")

            self.websocket = await websockets.connect(
                full_url,
                additional_headers=headers,
                ping_interval=30,
                ping_timeout=10
            )

            self.signalr_connected = True
            print("✅ Connected to OpenShock SignalR!")
            print("🎯 Listening for real-time shock events...")

            # Send SignalR handshake
            await self.send_signalr_handshake()

            # Listen for messages
            await self.listen_for_messages()

        except Exception as e:
            print(f"❌ SignalR connection error: {e}")
            self.signalr_connected = False

    async def signalr_negotiate(self, api_url, token):
        """Negotiate SignalR connection"""
        try:
            negotiate_url = f"{api_url}/1/hubs/user/negotiate"
            headers = {
                'Open-Shock-Token': token,
                'User-Agent': 'VRCChatbox-ShockOSC/1.0',
                'Content-Type': 'application/json'
            }

            print(f"Negotiating SignalR connection: {negotiate_url}")

            response = requests.post(negotiate_url, headers=headers, timeout=10)

            if response.status_code == 200:
                negotiate_data = response.json()
                print(f"✅ SignalR negotiation successful!")
                print(f"📊 Negotiate response: {json.dumps(negotiate_data, indent=2)}")
                return negotiate_data
            else:
                print(f"❌ SignalR negotiation failed: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            print(f"❌ SignalR negotiation error: {e}")
            return None

    async def send_signalr_handshake(self):
        """Send SignalR handshake message"""
        try:
            handshake_message = {
                "protocol": "json",
                "version": 1
            }

            # SignalR handshake format: message + 0x1E delimiter
            handshake = json.dumps(handshake_message) + "\x1e"

            print(f"Sending SignalR handshake: {handshake}")
            await self.websocket.send(handshake)

        except Exception as e:
            print(f"❌ Error sending handshake: {e}")

    async def listen_for_messages(self):
        """Listen for incoming SignalR messages"""
        try:
            async for message in self.websocket:
                await self.handle_signalr_message(message)
        except websockets.exceptions.ConnectionClosed:
            print("❌ WebSocket connection closed")
            self.signalr_connected = False
        except Exception as e:
            print(f"❌ Error listening for messages: {e}")
            self.signalr_connected = False

    async def handle_signalr_message(self, message):
        """Handle incoming SignalR messages"""
        try:
            # SignalR messages are delimited by 0x1E
            if isinstance(message, str):
                messages = message.split('\x1e')
                for msg in messages:
                    if msg.strip():
                        await self.parse_signalr_message(msg.strip())
            else:
                print(f"📝 Binary message: {message}")

        except Exception as e:
            print(f"❌ Error handling message: {e}")

    async def parse_signalr_message(self, message):
        """Parse individual SignalR message"""
        try:
            # Try to parse as JSON
            try:
                data = json.loads(message)

                # Handle different SignalR message types
                if isinstance(data, dict):
                    if 'target' in data and 'arguments' in data:
                        target = data.get('target')
                        args = data.get('arguments', [])

                        if target == 'Log':
                            await self.handle_log_event(args)
                        elif target == 'Welcome':
                            print(f"🔍 SignalR Welcome: {args}")
                        elif target == 'DeviceStatus':
                            print(f"🔍 SignalR DeviceStatus: {args}")
                        else:
                            print(f"🔍 SignalR event - Target: {target}, Args: {args}")

                    elif 'type' in data:
                        msg_type = data.get('type')
                        if msg_type == 6:  # Ping message
                            print(f"🏓 SignalR ping")
                        else:
                            print(f"📝 Other SignalR message: {data}")

            except json.JSONDecodeError:
                print(f"📝 Non-JSON message: {message}")

        except Exception as e:
            print(f"❌ Error parsing message: {e}")

    async def handle_log_event(self, args):
        """Handle 'Log' events from SignalR - these contain shock events from internet users"""
        try:
            if not args or len(args) < 2:
                return

            # Log events have two arguments: user info and shock data array
            user_info = args[0] if args[0] else {}
            shock_events = args[1] if len(args) > 1 and args[1] else []

            # Process each shock event in the array
            for shock_event in shock_events:
                if not isinstance(shock_event, dict):
                    continue

                shocker_info = shock_event.get('shocker', {})
                shock_type = shock_event.get('type', 0)
                intensity = shock_event.get('intensity', 0)
                duration = shock_event.get('duration', 0)
                executed_at = shock_event.get('executedAt', '')

                # Extract user information
                user_name = user_info.get('name', 'Unknown User')
                custom_name = user_info.get('customName')
                connection_id = user_info.get('connectionId', '')
                additional_items = user_info.get('additionalItems', {})
                share_link_id = additional_items.get('shareLinkId') if additional_items else None

                # Use custom name if available, otherwise use regular name
                display_name = custom_name if custom_name else user_name

                # Extract shocker information
                shocker_name = shocker_info.get('name', 'Unknown Shocker')
                shocker_id = shocker_info.get('id', 'Unknown')

                # Map shock types (1=shock, 2=vibrate, 3=sound)
                type_names = {1: "shock", 2: "vibrate", 3: "sound"}
                type_name = type_names.get(shock_type, f"type{shock_type}")

                # Only process shock events, ignore vibrate and sound
                if shock_type != 1:  # Only process shocks (type 1)
                    continue

                # Find the group name for this shocker ID
                group_name = None
                shockers_config = self.config.get("shockers", {})
                for stored_shocker_id, assignment_info in shockers_config.items():
                    if stored_shocker_id == shocker_id:
                        if isinstance(assignment_info, dict):
                            group_name = assignment_info.get("group", "")
                        else:
                            group_name = assignment_info
                        break

                # Use group name if found, otherwise fall back to shocker name
                display_shocker_name = group_name if group_name else shocker_name

                print(f"🔥 Internet {type_name} received!")
                print(f"   From: {display_name} ({user_name})")
                print(f"   Shocker: {shocker_name} ({shocker_id})")
                print(f"   Intensity: {intensity}%, Duration: {duration}ms")
                if share_link_id:
                    print(f"   Via share link: {share_link_id}")

                # Call the internet shock callback if available
                if self.internet_shock_callback:
                    self.internet_shock_callback(
                        user_name=display_name,
                        real_name=user_name,
                        shocker_name=display_shocker_name,
                        type_name=type_name,
                        intensity=intensity,
                        duration=duration,
                        is_guest=user_info.get('id') == "00000000-0000-0000-0000-000000000000",
                        share_link_id=share_link_id
                    )

        except Exception as e:
            print(f"Error processing internet shock event: {e}")


    def test_openshock_connection(self):
        """Test OpenShock API connection"""
        token = self.config.get("openshock_token", "").strip()
        if not token:
            print("No OpenShock API token configured")
            return False
        
        headers = {
            "Open-Shock-Token": token,
            "User-Agent": "VRCChatbox-ShockOSC/1.0"
        }
        
        try:
            url = f"{self.config.get('openshock_url', 'https://api.openshock.app')}/1/shockers/own"
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                api_response = response.json()
                
                # Handle v1 shockers/own response format
                shocker_count = 0
                if isinstance(api_response, dict) and 'data' in api_response:
                    data = api_response['data']
                    if isinstance(data, list):
                        # Check if these are direct shockers or devices with shockers
                        if data and isinstance(data[0], dict) and 'shockers' in data[0]:
                            # These are devices containing shockers
                            shocker_count = sum(len(device.get('shockers', [])) for device in data)
                            print(f"OpenShock connection successful. Found {len(data)} device(s) with {shocker_count} shocker(s).")
                        else:
                            # These are direct shockers
                            shocker_count = len(data)
                            print(f"OpenShock connection successful. Found {shocker_count} shocker(s).")
                elif isinstance(api_response, list):
                    # Direct list of items
                    if api_response and isinstance(api_response[0], dict) and 'shockers' in api_response[0]:
                        # These are devices with shockers
                        shocker_count = sum(len(device.get('shockers', [])) for device in api_response)
                        print(f"OpenShock connection successful. Found {len(api_response)} device(s) with {shocker_count} shocker(s).")
                    else:
                        # These are direct shockers
                        shocker_count = len(api_response)
                        print(f"OpenShock connection successful. Found {shocker_count} shocker(s).")
                else:
                    print(f"OpenShock connection successful. Response format: {type(api_response)}")
                    
                return True
            else:
                print(f"OpenShock connection failed: {response.status_code} - {response.text}")
                return False
                
        except requests.RequestException as e:
            print(f"OpenShock connection error: {e}")
            return False

    def cleanup(self):
        """Clean up resources when shutting down"""
        print("Cleaning up ShockOSC controller...")
        self.stop_signalr_connection()

        # Cancel all timers
        for timer in list(self.active_shocks.values()):
            timer.cancel()
        self.active_shocks.clear()

        for timer in list(self.cooldown_timers.values()):
            timer.cancel()
        self.cooldown_timers.clear()

        # Clear shock hide timer
        if hasattr(self, 'shock_hide_timer') and self.shock_hide_timer:
            self.shock_hide_timer.cancel()

    def test_shock(self):
        """Send a test shock"""
        print("Sending test shock...")

        # Test OpenShock connection first if configured
        token = self.config.get("openshock_token", "").strip()
        if token:
            print("Testing OpenShock connection...")
            if self.test_openshock_connection():
                print("OpenShock connection successful, test shock will use OpenShock API")
            else:
                print("OpenShock connection failed, test shock will use OSC fallback")
        else:
            print("No OpenShock token configured, test shock will use OSC only")

        self.send_shock()
    
    def test_leftleg_shock(self):
        """Test function to send shock to leftleg"""
        print("Testing leftleg shock...")
        self.send_shock(groups=["leftleg"])
    
    def test_rightleg_shock(self):
        """Test function to send shock to rightleg"""
        print("Testing rightleg shock...")
        self.send_shock(groups=["rightleg"])