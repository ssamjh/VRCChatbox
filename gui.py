import tkinter as tk
from tkinter import ttk, messagebox
from config import load_app_config, save_app_config
import requests
import threading


class VRCChatboxGUI:
    def __init__(self, messenger=None):
        self.messenger = messenger
        self.config = load_app_config()
        
        # Create main window
        self.root = tk.Tk()
        self.root.title("VRC Chatbox Settings")
        self.root.geometry("600x750")
        self.root.resizable(False, False)
        
        # Center the window
        self.center_window()
        
        self.setup_ui()
        
    def center_window(self):
        """Center the window on screen"""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
        
    def setup_ui(self):
        """Setup the UI elements"""
        # Create notebook for tabs
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # General settings tab
        general_frame = ttk.Frame(notebook, padding="10")
        notebook.add(general_frame, text="General")
        
        # Music toggle
        self.show_music_var = tk.BooleanVar(value=self.config.get("show_music", True))
        music_checkbox = ttk.Checkbutton(
            general_frame,
            text="Show Music Info",
            variable=self.show_music_var,
            command=self.on_music_toggle
        )
        music_checkbox.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        # ShockOSC tab
        shock_frame = ttk.Frame(notebook, padding="10")
        notebook.add(shock_frame, text="ShockOSC")
        self.setup_shockosc_ui(shock_frame)
        
        # Status label (bottom of main window)
        self.status_label = ttk.Label(self.root, text="", foreground="green")
        self.status_label.pack(pady=5)
        
        # Close button
        close_button = ttk.Button(self.root, text="Close", command=self.root.destroy)
        close_button.pack(pady=10)
        
    def setup_shockosc_ui(self, parent):
        """Setup ShockOSC settings UI"""
        shock_config = self.config.get("shockosc", {})
        
        # Enable/Disable checkbox
        self.shock_enabled_var = tk.BooleanVar(value=shock_config.get("enabled", False))
        enabled_checkbox = ttk.Checkbutton(
            parent,
            text="Enable ShockOSC",
            variable=self.shock_enabled_var,
            command=self.on_shock_settings_change
        )
        enabled_checkbox.grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 10))
        
        # Show shock info toggle
        self.shock_show_info_var = tk.BooleanVar(value=shock_config.get("show_shock_info", True))
        show_info_checkbox = ttk.Checkbutton(
            parent,
            text="Show shock info in chatbox",
            variable=self.shock_show_info_var,
            command=self.on_shock_settings_change
        )
        show_info_checkbox.grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=(0, 10))
        
        # Mode selection
        ttk.Label(parent, text="Mode:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.shock_mode_var = tk.StringVar(value=shock_config.get("mode", "static"))
        mode_frame = ttk.Frame(parent)
        mode_frame.grid(row=2, column=1, columnspan=2, sticky=tk.W, pady=5)
        
        static_radio = ttk.Radiobutton(mode_frame, text="Static", variable=self.shock_mode_var, 
                                     value="static", command=self.on_mode_change)
        static_radio.grid(row=0, column=0, padx=(0, 10))
        
        random_radio = ttk.Radiobutton(mode_frame, text="Random", variable=self.shock_mode_var,
                                     value="random", command=self.on_mode_change)
        random_radio.grid(row=0, column=1)
        
        # Static intensity slider
        self.static_frame = ttk.LabelFrame(parent, text="Static Settings", padding="10")
        self.static_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        
        ttk.Label(self.static_frame, text="Intensity:").grid(row=0, column=0, sticky=tk.W)
        self.static_intensity_var = tk.IntVar(value=shock_config.get("static_intensity", 50))
        static_scale = ttk.Scale(self.static_frame, from_=0, to=100, orient=tk.HORIZONTAL,
                               variable=self.static_intensity_var, command=self.on_shock_settings_change)
        static_scale.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0))
        
        self.static_intensity_label = ttk.Label(self.static_frame, text="50%")
        self.static_intensity_label.grid(row=0, column=2, padx=(10, 0))
        
        # Random intensity sliders
        self.random_frame = ttk.LabelFrame(parent, text="Random Settings", padding="10")
        self.random_frame.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        
        ttk.Label(self.random_frame, text="Min:").grid(row=0, column=0, sticky=tk.W)
        self.random_min_var = tk.IntVar(value=shock_config.get("random_min", 20))
        min_scale = ttk.Scale(self.random_frame, from_=0, to=100, orient=tk.HORIZONTAL,
                            variable=self.random_min_var, command=self.on_shock_settings_change)
        min_scale.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0))
        
        self.random_min_label = ttk.Label(self.random_frame, text="20%")
        self.random_min_label.grid(row=0, column=2, padx=(10, 0))
        
        ttk.Label(self.random_frame, text="Max:").grid(row=1, column=0, sticky=tk.W)
        self.random_max_var = tk.IntVar(value=shock_config.get("random_max", 80))
        max_scale = ttk.Scale(self.random_frame, from_=0, to=100, orient=tk.HORIZONTAL,
                            variable=self.random_max_var, command=self.on_shock_settings_change)
        max_scale.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(10, 0))
        
        self.random_max_label = ttk.Label(self.random_frame, text="80%")
        self.random_max_label.grid(row=1, column=2, padx=(10, 0))
        
        # Duration setting
        duration_frame = ttk.LabelFrame(parent, text="Duration & Cooldown", padding="10")
        duration_frame.grid(row=5, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        
        ttk.Label(duration_frame, text="Shock Length:").grid(row=0, column=0, sticky=tk.W)
        self.duration_var = tk.DoubleVar(value=shock_config.get("duration", 1.0))
        duration_scale = ttk.Scale(duration_frame, from_=0.3, to=30.0, orient=tk.HORIZONTAL,
                                 variable=self.duration_var, command=self.on_shock_settings_change)
        duration_scale.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0))
        
        self.duration_label = ttk.Label(duration_frame, text="1.0s")
        self.duration_label.grid(row=0, column=2, padx=(10, 0))
        
        ttk.Label(duration_frame, text="Cooldown:").grid(row=1, column=0, sticky=tk.W)
        self.cooldown_var = tk.DoubleVar(value=shock_config.get("cooldown_delay", 5.0))
        cooldown_scale = ttk.Scale(duration_frame, from_=0.0, to=60.0, orient=tk.HORIZONTAL,
                                 variable=self.cooldown_var, command=self.on_shock_settings_change)
        cooldown_scale.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(10, 0))
        
        self.cooldown_label = ttk.Label(duration_frame, text="5.0s")
        self.cooldown_label.grid(row=1, column=2, padx=(10, 0))
        
        ttk.Label(duration_frame, text="Hold Time:").grid(row=2, column=0, sticky=tk.W)
        self.hold_time_var = tk.DoubleVar(value=shock_config.get("hold_time", 0.5))
        hold_time_scale = ttk.Scale(duration_frame, from_=0.0, to=5.0, orient=tk.HORIZONTAL,
                                  variable=self.hold_time_var, command=self.on_shock_settings_change)
        hold_time_scale.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(10, 0))
        
        self.hold_time_label = ttk.Label(duration_frame, text="500ms")
        self.hold_time_label.grid(row=2, column=2, padx=(10, 0))
        
        # OpenShock settings
        openshock_frame = ttk.LabelFrame(parent, text="OpenShock Integration", padding="10")
        openshock_frame.grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        
        # API Token
        ttk.Label(openshock_frame, text="API Token:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.token_var = tk.StringVar(value=shock_config.get("openshock_token", ""))
        token_entry = ttk.Entry(openshock_frame, textvariable=self.token_var, show="*", width=40)
        token_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)
        token_entry.bind('<KeyRelease>', self.on_token_change)
        
        # Discover button
        self.discover_button = ttk.Button(openshock_frame, text="Discover Shockers", 
                                        command=self.discover_shockers)
        self.discover_button.grid(row=1, column=0, columnspan=2, pady=5)
        
        # Shockers list
        ttk.Label(openshock_frame, text="Shocker Assignments:").grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(10, 5))
        
        # Create treeview for shocker assignments
        self.shockers_tree = ttk.Treeview(openshock_frame, columns=('Name', 'ID', 'Group'), show='headings', height=4)
        self.shockers_tree.heading('Name', text='Shocker Name')
        self.shockers_tree.heading('ID', text='ID')
        self.shockers_tree.heading('Group', text='OSC Group')
        self.shockers_tree.column('Name', width=150)
        self.shockers_tree.column('ID', width=80)
        self.shockers_tree.column('Group', width=100)
        self.shockers_tree.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Scrollbar for treeview
        tree_scrollbar = ttk.Scrollbar(openshock_frame, orient=tk.VERTICAL, command=self.shockers_tree.yview)
        tree_scrollbar.grid(row=3, column=2, sticky=(tk.N, tk.S), pady=5)
        self.shockers_tree.configure(yscrollcommand=tree_scrollbar.set)
        
        # Group assignment frame
        assign_frame = ttk.Frame(openshock_frame)
        assign_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(assign_frame, text="Assign to group:").grid(row=0, column=0, padx=(0, 5))
        self.group_var = tk.StringVar()
        self.group_combo = ttk.Combobox(assign_frame, textvariable=self.group_var, 
                                       values=['leftleg', 'rightleg'], state='readonly', width=15)
        self.group_combo.grid(row=0, column=1, padx=5)
        
        self.assign_button = ttk.Button(assign_frame, text="Assign", command=self.assign_shocker)
        self.assign_button.grid(row=0, column=2, padx=5)
        
        self.unassign_button = ttk.Button(assign_frame, text="Unassign", command=self.unassign_shocker)
        self.unassign_button.grid(row=0, column=3, padx=5)
        
        # Test shock button
        self.test_shock_button = ttk.Button(openshock_frame, text="Test Shock", command=self.test_shock)
        self.test_shock_button.grid(row=5, column=0, columnspan=2, pady=10)
        
        # Configure column weights for proper stretching
        parent.columnconfigure(1, weight=1)
        self.static_frame.columnconfigure(1, weight=1)
        self.random_frame.columnconfigure(1, weight=1)
        duration_frame.columnconfigure(1, weight=1)
        openshock_frame.columnconfigure(1, weight=1)
        
        # Load existing shocker assignments
        self.refresh_shockers_display()
        
        # Initial mode setup
        self.on_mode_change()
        
    def on_mode_change(self):
        """Handle mode change between static and random"""
        mode = self.shock_mode_var.get()
        if mode == "static":
            self.static_frame.grid()
            self.random_frame.grid_remove()
        else:
            self.static_frame.grid_remove()
            self.random_frame.grid()
        self.on_shock_settings_change()
        
    def on_shock_settings_change(self, *args):
        """Handle any ShockOSC setting change"""
        # Update label displays
        self.static_intensity_label.config(text=f"{int(self.static_intensity_var.get())}%")
        self.random_min_label.config(text=f"{int(self.random_min_var.get())}%")
        self.random_max_label.config(text=f"{int(self.random_max_var.get())}%")
        self.duration_label.config(text=f"{self.duration_var.get():.1f}s")
        self.cooldown_label.config(text=f"{self.cooldown_var.get():.1f}s")
        
        # Display hold time in milliseconds for values < 1s, otherwise seconds
        hold_time = self.hold_time_var.get()
        if hold_time < 1.0:
            self.hold_time_label.config(text=f"{int(hold_time * 1000)}ms")
        else:
            self.hold_time_label.config(text=f"{hold_time:.1f}s")
        
        # Ensure min <= max for random mode
        if self.random_min_var.get() > self.random_max_var.get():
            self.random_max_var.set(self.random_min_var.get())
            self.random_max_label.config(text=f"{int(self.random_max_var.get())}%")
        
        # Save settings
        if not hasattr(self, 'config'):
            return
            
        if "shockosc" not in self.config:
            self.config["shockosc"] = {}
            
        self.config["shockosc"].update({
            "enabled": self.shock_enabled_var.get(),
            "mode": self.shock_mode_var.get(),
            "static_intensity": int(self.static_intensity_var.get()),
            "random_min": int(self.random_min_var.get()),
            "random_max": int(self.random_max_var.get()),
            "duration": round(self.duration_var.get(), 1),
            "show_shock_info": self.shock_show_info_var.get(),
            "cooldown_delay": round(self.cooldown_var.get(), 1),
            "hold_time": round(self.hold_time_var.get(), 2),
            "openshock_token": self.token_var.get() if hasattr(self, 'token_var') else self.config["shockosc"].get("openshock_token", ""),
            "shockers": self.config["shockosc"].get("shockers", {}),
            "openshock_url": self.config["shockosc"].get("openshock_url", "https://api.openshock.app")
        })
        
        save_app_config(self.config)
        
        # Update messenger if available
        if self.messenger and hasattr(self.messenger, 'update_shock_config'):
            self.messenger.update_shock_config(self.config["shockosc"])
        
        # Show status (only if status_label exists)
        if hasattr(self, 'status_label'):
            status = "enabled" if self.config["shockosc"]["enabled"] else "disabled"
            self.status_label.config(text=f"ShockOSC {status}")
            self.root.after(2000, lambda: self.status_label.config(text=""))
        
    def on_music_toggle(self):
        """Handle music toggle change"""
        self.config["show_music"] = self.show_music_var.get()
        save_app_config(self.config)
        
        # Update messenger if available
        if self.messenger:
            self.messenger.show_music = self.config["show_music"]
            self.messenger.request_display_update()
        
        # Show status message
        status = "enabled" if self.config["show_music"] else "disabled"
        self.status_label.config(text=f"Music display {status}")
        self.root.after(2000, lambda: self.status_label.config(text=""))
        
    def on_token_change(self, *args):
        """Handle API token change"""
        if not hasattr(self, 'config'):
            return
        if "shockosc" not in self.config:
            self.config["shockosc"] = {}
        
        self.config["shockosc"]["openshock_token"] = self.token_var.get()
        save_app_config(self.config)
        
        # Update messenger if available
        if self.messenger and hasattr(self.messenger, 'update_shock_config'):
            self.messenger.update_shock_config(self.config["shockosc"])
    
    def discover_shockers(self):
        """Discover available shockers from OpenShock API"""
        token = self.token_var.get().strip()
        if not token:
            messagebox.showerror("Error", "Please enter your OpenShock API token first.")
            return
        
        # Disable button and show loading
        self.discover_button.config(state='disabled', text='Discovering...')
        
        def discover_thread():
            try:
                # Validate token format
                if not token or len(token) < 10:
                    self.root.after(0, lambda: messagebox.showerror("Invalid Token", "API token appears too short. Please check your token."))
                    return
                    
                base_url = self.config['shockosc'].get('openshock_url', 'https://api.openshock.app')
                # Try different endpoints - the API docs show multiple possibilities
                endpoints_to_try = [
                    "/2/devices",  # Version 2 devices endpoint (preferred)
                    "/1/devices",  # Version 1 devices endpoint
                    "/2/shockers", # Version 2 shockers endpoint
                    "/1/shockers"  # Version 1 shockers endpoint
                ]
                
                headers = {
                    'OpenShockToken': token,
                    'User-Agent': 'VRCChatbox-ShockOSC/1.0',
                    'Accept': 'application/json'
                }
                
                print(f"DEBUG: Attempting to discover shockers")
                headers_debug = dict(headers)
                headers_debug['OpenShockToken'] = f"{'*' * (len(token) - 4)}{token[-4:]}" if len(token) > 4 else "***"
                print(f"DEBUG: Headers: {headers_debug}")
                print(f"DEBUG: Token length: {len(token)} characters")
                
                # Try different endpoints until we find one that works
                response = None
                successful_url = None
                
                for endpoint in endpoints_to_try:
                    url = f"{base_url}{endpoint}"
                    print(f"DEBUG: Trying endpoint: {url}")
                    
                    try:
                        response = requests.get(url, headers=headers, timeout=10)
                        print(f"DEBUG: Response status: {response.status_code}")
                        
                        if response.status_code == 200:
                            print(f"DEBUG: Success with endpoint: {endpoint}")
                            successful_url = url
                            break
                        elif response.status_code == 404:
                            print(f"DEBUG: Endpoint not found: {endpoint}")
                            continue
                        else:
                            print(f"DEBUG: Error with {endpoint}: {response.status_code} - {response.text[:200]}")
                            # Continue trying other endpoints for 4xx errors, but break for auth issues
                            if response.status_code == 401:
                                break
                            continue
                    except requests.RequestException as e:
                        print(f"DEBUG: Network error with {endpoint}: {e}")
                        continue
                
                if not response or response.status_code != 200:
                    if response:
                        print(f"DEBUG: Final response status: {response.status_code}")
                        print(f"DEBUG: Final response headers: {dict(response.headers)}")
                        print(f"DEBUG: Final response text: {response.text[:500]}")  # First 500 chars
                    else:
                        print(f"DEBUG: No successful response from any endpoint")
                
                if not response or response.status_code != 200:
                    if not response:
                        error_msg = "Failed to connect to any OpenShock API endpoint. Possible issues:\n"
                        error_msg += "• Network connectivity problems\n"
                        error_msg += "• OpenShock servers unavailable\n"
                        error_msg += f"• All endpoints tried: {endpoints_to_try}"
                        self.root.after(0, lambda: messagebox.showerror("Connection Error", error_msg))
                        return
                    elif response.status_code == 400:
                        error_msg = f"Bad Request (400) from all endpoints. This might mean:\n"
                        error_msg += f"• Invalid API token format\n"
                        error_msg += f"• Missing required headers\n"
                        error_msg += f"• Token length: {len(token)} chars\n"
                        error_msg += f"• Last response: {response.text[:200]}"
                        self.root.after(0, lambda: messagebox.showerror("API Error", error_msg))
                        return
                    elif response.status_code == 401:
                        self.root.after(0, lambda: messagebox.showerror("Authentication Error", "Invalid API token. Please check your token and try again."))
                        return
                    elif response.status_code == 403:
                        self.root.after(0, lambda: messagebox.showerror("Permission Error", "Token doesn't have permission to access devices."))
                        return
                    else:
                        error_msg = f"API Error {response.status_code}\n\nResponse: {response.text[:300]}\n\nLast URL: {url if 'url' in locals() else 'Unknown'}"
                        self.root.after(0, lambda: messagebox.showerror("API Error", error_msg))
                        return
                
                try:
                    api_response = response.json()
                    print(f"DEBUG: Successfully parsed JSON response")
                    print(f"DEBUG: Response type: {type(api_response)}")
                    print(f"DEBUG: Response keys: {list(api_response.keys()) if isinstance(api_response, dict) else 'Not a dict'}")
                    print(f"DEBUG: Response sample: {str(api_response)[:300]}")
                except ValueError as json_err:
                    error_msg = f"Invalid JSON response from API:\n{response.text}\n\nJSON Error: {json_err}"
                    self.root.after(0, lambda: messagebox.showerror("Response Error", error_msg))
                    return
                
                shockers = []
                
                # Handle different response formats
                devices = None
                if isinstance(api_response, list):
                    # Direct list of devices/shockers
                    devices = api_response
                    print(f"DEBUG: Response is a list with {len(devices)} items")
                elif isinstance(api_response, dict):
                    # Check for common wrapper keys
                    if 'data' in api_response:
                        devices = api_response['data']
                        print(f"DEBUG: Found data wrapper with {len(devices) if isinstance(devices, list) else 'non-list'} items")
                    elif 'devices' in api_response:
                        devices = api_response['devices'] 
                        print(f"DEBUG: Found devices key with {len(devices) if isinstance(devices, list) else 'non-list'} items")
                    elif 'shockers' in api_response:
                        # Direct shockers response
                        direct_shockers = api_response['shockers']
                        print(f"DEBUG: Found direct shockers response with {len(direct_shockers) if isinstance(direct_shockers, list) else 'non-list'} items")
                        for i, shocker in enumerate(direct_shockers):
                            print(f"DEBUG: Direct shocker {i}: {shocker}")
                            shockers.append({
                                'id': shocker.get('id'),
                                'name': shocker.get('name', f"Shocker {shocker.get('id', 'Unknown')}"),
                                'device_name': shocker.get('device', {}).get('name', 'Unknown Device') if isinstance(shocker.get('device'), dict) else 'Unknown Device'
                            })
                        devices = None  # Skip device processing below
                    else:
                        # Response might be a single object or different format
                        devices = [api_response]
                        print(f"DEBUG: Treating response as single device object")
                
                # Process devices if we have them
                if devices:
                    print(f"DEBUG: Processing {len(devices)} device(s)")
                    for i, device in enumerate(devices):
                        print(f"DEBUG: Device {i}: {device.get('name', 'Unnamed')} - Keys: {list(device.keys()) if isinstance(device, dict) else 'Not a dict'}")
                        
                        # Handle different device formats
                        device_shockers = []
                        if isinstance(device, dict):
                            if 'shockers' in device:
                                device_shockers = device['shockers']
                            elif 'id' in device and 'name' in device:
                                # This might be a shocker object directly
                                device_shockers = [device]
                        
                        if device_shockers:
                            print(f"DEBUG: Found {len(device_shockers)} shocker(s) in device")
                            for j, shocker in enumerate(device_shockers):
                                print(f"DEBUG: Shocker {j}: {shocker}")
                                if isinstance(shocker, dict) and 'id' in shocker:
                                    shockers.append({
                                        'id': shocker['id'],
                                        'name': shocker.get('name', f"Shocker {shocker['id']}"),
                                        'device_name': device.get('name', 'Unknown Device') if isinstance(device, dict) else 'Unknown Device'
                                    })
                        else:
                            print(f"DEBUG: No shockers found in device {i}")
                
                print(f"DEBUG: Total shockers found: {len(shockers)}")
                
                # Update UI on main thread
                self.root.after(0, lambda: self._update_discovered_shockers(shockers))
                
            except requests.RequestException as e:
                error_msg = f"Network error connecting to OpenShock API:\n{str(e)}\n\nURL: {url if 'url' in locals() else 'Unknown'}"
                print(f"DEBUG: Network error: {e}")
                self.root.after(0, lambda: messagebox.showerror("Network Error", error_msg))
            except Exception as e:
                error_msg = f"Unexpected error during discovery:\n{str(e)}\n\nType: {type(e).__name__}"
                print(f"DEBUG: Unexpected error: {e}")
                import traceback
                print(f"DEBUG: Traceback: {traceback.format_exc()}")
                self.root.after(0, lambda: messagebox.showerror("Error", error_msg))
            finally:
                # Re-enable button
                self.root.after(0, lambda: self.discover_button.config(state='normal', text='Discover Shockers'))
        
        # Start discovery in background thread
        threading.Thread(target=discover_thread, daemon=True).start()
    
    def _update_discovered_shockers(self, shockers):
        """Update the shockers display with discovered shockers"""
        # Store discovered shockers
        self.discovered_shockers = {str(s['id']): s for s in shockers}
        
        if not shockers:
            messagebox.showinfo("No Shockers", "No shockers found. Make sure you have shockers configured in your OpenShock account.")
            return
        
        messagebox.showinfo("Success", f"Discovered {len(shockers)} shocker(s).")
        self.refresh_shockers_display()
    
    def refresh_shockers_display(self):
        """Refresh the shockers treeview display"""
        # Clear existing items
        for item in self.shockers_tree.get_children():
            self.shockers_tree.delete(item)
        
        # Add discovered shockers
        if hasattr(self, 'discovered_shockers'):
            shock_config = self.config.get("shockosc", {})
            assigned_shockers = shock_config.get("shockers", {})
            
            for shocker_id, shocker in self.discovered_shockers.items():
                group = assigned_shockers.get(shocker_id, "")
                display_name = f"{shocker['name']} ({shocker['device_name']})"
                self.shockers_tree.insert('', 'end', values=(display_name, shocker_id, group))
    
    def assign_shocker(self):
        """Assign selected shocker to a group"""
        selection = self.shockers_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a shocker to assign.")
            return
        
        group = self.group_var.get()
        if not group:
            messagebox.showwarning("No Group", "Please select a group to assign the shocker to.")
            return
        
        # Get shocker ID from selection
        item = self.shockers_tree.item(selection[0])
        shocker_id = item['values'][1]
        
        # Update config
        if "shockers" not in self.config["shockosc"]:
            self.config["shockosc"]["shockers"] = {}
        
        self.config["shockosc"]["shockers"][shocker_id] = group
        save_app_config(self.config)
        
        # Update messenger if available
        if self.messenger and hasattr(self.messenger, 'update_shock_config'):
            self.messenger.update_shock_config(self.config["shockosc"])
        
        # Refresh display
        self.refresh_shockers_display()
        
        # Clear selection
        self.group_var.set("")
        
        self.status_label.config(text=f"Shocker assigned to {group}")
        self.root.after(2000, lambda: self.status_label.config(text=""))
    
    def unassign_shocker(self):
        """Unassign selected shocker from its group"""
        selection = self.shockers_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a shocker to unassign.")
            return
        
        # Get shocker ID from selection
        item = self.shockers_tree.item(selection[0])
        shocker_id = item['values'][1]
        
        # Remove from config
        if "shockers" in self.config["shockosc"] and shocker_id in self.config["shockosc"]["shockers"]:
            del self.config["shockosc"]["shockers"][shocker_id]
            save_app_config(self.config)
            
            # Update messenger if available
            if self.messenger and hasattr(self.messenger, 'update_shock_config'):
                self.messenger.update_shock_config(self.config["shockosc"])
            
            # Refresh display
            self.refresh_shockers_display()
            
            self.status_label.config(text="Shocker unassigned")
            self.root.after(2000, lambda: self.status_label.config(text=""))
    
    def test_shock(self):
        """Test shock functionality"""
        if not self.messenger or not hasattr(self.messenger, 'shock_controller'):
            messagebox.showerror("Error", "No shock controller available")
            return
        
        # Disable button during test
        self.test_shock_button.config(state='disabled', text='Testing...')
        
        def test_thread():
            try:
                # Run the test shock
                self.messenger.shock_controller.test_shock()
                self.root.after(0, lambda: messagebox.showinfo("Test Complete", "Test shock sent! Check console for details."))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Test Failed", f"Test shock failed: {str(e)}"))
            finally:
                # Re-enable button
                self.root.after(0, lambda: self.test_shock_button.config(state='normal', text='Test Shock'))
        
        # Start test in background thread
        threading.Thread(target=test_thread, daemon=True).start()
        
    def run(self):
        """Run the GUI"""
        self.root.mainloop()


def show_settings_gui(messenger=None):
    """Show the settings GUI"""
    gui = VRCChatboxGUI(messenger)
    gui.run()


if __name__ == "__main__":
    show_settings_gui()