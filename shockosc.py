import random
import threading
import time
import requests
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
            "openshock_url": "https://api.openshock.app"
        }
        self.active_shocks = {}  # Track active shock timers
        self.cooldown_timers = {}  # Track cooldown timers per group
        self.cooldown_states = {}  # Track which groups are on cooldown
        self.shock_callback = shock_callback  # Callback to notify about shocks
        
    def update_config(self, new_config):
        """Update ShockOSC configuration"""
        self.config.update(new_config)
        print(f"ShockOSC config updated: {self.config}")
        
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
                for shocker_id, assigned_group in shockers_config.items():
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
                self.shock_callback(intensity, group)
    
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
                for shocker_id, assigned_group in shockers_config.items():
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
                self.shock_callback(intensity, group)
    
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
                for shocker_id, assigned_group in shockers_config.items():
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