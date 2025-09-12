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
        
        # Test buttons frame
        test_frame = ttk.Frame(openshock_frame)
        test_frame.grid(row=5, column=0, columnspan=2, pady=10, sticky=(tk.W, tk.E))
        
        # Test shock button
        self.test_shock_button = ttk.Button(test_frame, text="Test Shock", command=self.test_shock)
        self.test_shock_button.grid(row=0, column=0, padx=(0, 5))
        
        # Test simulation buttons
        self.test_leftleg_button = ttk.Button(test_frame, text="Test Left Leg", command=self.test_leftleg)
        self.test_leftleg_button.grid(row=0, column=1, padx=2)
        
        self.test_rightleg_button = ttk.Button(test_frame, text="Test Right Leg", command=self.test_rightleg)
        self.test_rightleg_button.grid(row=0, column=2, padx=(5, 0))
        
        # Configure column weights for proper stretching
        parent.columnconfigure(1, weight=1)
        self.static_frame.columnconfigure(1, weight=1)
        self.random_frame.columnconfigure(1, weight=1)
        duration_frame.columnconfigure(1, weight=1)
        openshock_frame.columnconfigure(1, weight=1)
        
        # Convert legacy shocker config format if needed
        self._convert_legacy_shocker_config()
        
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
                # Use v1 endpoints for discovery since they work with API tokens
                # v2 /shares endpoint requires session cookies, not API tokens
                endpoints_to_try = [
                    "/1/shockers/own",    # V1: Get own shockers directly (preferred)
                    "/1/shockers/shared", # V1: Get shared shockers
                    "/1/devices/own",     # V1: Fallback to devices with shockers
                ]
                
                headers = {
                    'Open-Shock-Token': token,
                    'User-Agent': 'VRCChatbox-ShockOSC/1.0',
                    'Accept': 'application/json'
                }
                
                
                # Try different endpoints until we find one that works
                response = None
                successful_url = None
                
                for endpoint in endpoints_to_try:
                    url = f"{base_url}{endpoint}"
                    
                    try:
                        response = requests.get(url, headers=headers, timeout=10)
                        
                        if response.status_code == 200:
                            successful_url = url
                            break
                        elif response.status_code == 404:
                            continue
                        else:
                            # Continue trying other endpoints for 4xx errors, but break for auth issues
                            if response.status_code == 401:
                                break
                            continue
                    except requests.RequestException as e:
                        continue
                
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
                except ValueError as json_err:
                    error_msg = f"Invalid JSON response from API:\n{response.text}\n\nJSON Error: {json_err}"
                    self.root.after(0, lambda: messagebox.showerror("Response Error", error_msg))
                    return
                
                shockers = []
                
                # Handle different response formats - prioritize v1 shocker endpoints
                devices = None
                
                # Check if this is from the /shockers/* endpoints (v1 API)
                if isinstance(api_response, dict) and 'data' in api_response:
                    # OpenShock API typically wraps responses in a 'data' field
                    data = api_response['data']
                    
                    if isinstance(data, list):
                        # Check if these are direct shockers or devices with shockers
                        if data and isinstance(data[0], dict) and 'shockers' in data[0]:
                            # These are devices containing shockers
                            devices = data
                        elif data and isinstance(data[0], dict) and ('id' in data[0] or 'name' in data[0]):
                            # These might be direct shockers
                            for shocker in data:
                                shockers.append({
                                    'id': shocker.get('id'),
                                    'name': shocker.get('name', f"Shocker {shocker.get('id', 'Unknown')}"),
                                    'device_name': shocker.get('device', {}).get('name', 'Unknown Device') if isinstance(shocker.get('device'), dict) else 'Unknown Device'
                                })
                            devices = None  # Skip device processing below
                elif isinstance(api_response, list):
                    # Direct list of devices/shockers
                    devices = api_response
                elif isinstance(api_response, dict):
                    # Check for other common wrapper keys
                    if 'devices' in api_response:
                        devices = api_response['devices'] 
                    elif 'shockers' in api_response:
                        # Direct shockers response (legacy format)
                        direct_shockers = api_response['shockers']
                        for shocker in direct_shockers:
                            shockers.append({
                                'id': shocker.get('id'),
                                'name': shocker.get('name', f"Shocker {shocker.get('id', 'Unknown')}"),
                                'device_name': shocker.get('device', {}).get('name', 'Unknown Device') if isinstance(shocker.get('device'), dict) else 'Unknown Device'
                            })
                        devices = None  # Skip device processing below
                    else:
                        # Response might be a single object or different format
                        devices = [api_response]
                
                # Process devices if we have them
                if devices:
                    for device in devices:
                        # Handle different device formats
                        device_shockers = []
                        if isinstance(device, dict):
                            if 'shockers' in device:
                                device_shockers = device['shockers']
                            elif 'id' in device and 'name' in device:
                                # This might be a shocker object directly
                                device_shockers = [device]
                        
                        if device_shockers:
                            for shocker in device_shockers:
                                if isinstance(shocker, dict) and 'id' in shocker:
                                    shockers.append({
                                        'id': shocker['id'],
                                        'name': shocker.get('name', f"Shocker {shocker['id']}"),
                                        'device_name': device.get('name', 'Unknown Device') if isinstance(device, dict) else 'Unknown Device'
                                    })
                
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
        
        shock_config = self.config.get("shockosc", {})
        assigned_shockers = shock_config.get("shockers", {})
        
        # Add discovered shockers if available
        if hasattr(self, 'discovered_shockers'):
            for shocker_id, shocker in self.discovered_shockers.items():
                # Check if we have saved assignment info
                if shocker_id in assigned_shockers:
                    if isinstance(assigned_shockers[shocker_id], dict):
                        group = assigned_shockers[shocker_id].get("group", "")
                    else:
                        # Legacy format - just the group string
                        group = assigned_shockers[shocker_id]
                else:
                    group = ""
                display_name = f"{shocker['name']} ({shocker['device_name']})"
                self.shockers_tree.insert('', 'end', values=(display_name, shocker_id, group))
        else:
            # If no discovered shockers yet, show saved assignments from config
            for shocker_id, assignment_info in assigned_shockers.items():
                if isinstance(assignment_info, dict):
                    # New format with complete info
                    group = assignment_info.get("group", "")
                    name = assignment_info.get("name", f"Shocker {shocker_id[:8]}...")
                    device_name = assignment_info.get("device_name", "Unknown Device")
                    display_name = f"{name} ({device_name})"
                else:
                    # Legacy format - just the group string
                    group = assignment_info
                    display_name = f"Shocker {shocker_id[:8]}..."
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
        
        # Get full shocker info for saving
        shocker_info = None
        if hasattr(self, 'discovered_shockers') and shocker_id in self.discovered_shockers:
            shocker_info = self.discovered_shockers[shocker_id]
        
        # Update config with complete shocker information
        if "shockers" not in self.config["shockosc"]:
            self.config["shockosc"]["shockers"] = {}
        
        # Save complete shocker info instead of just group
        self.config["shockosc"]["shockers"][shocker_id] = {
            "group": group,
            "name": shocker_info.get('name', f"Shocker {shocker_id[:8]}...") if shocker_info else f"Shocker {shocker_id[:8]}...",
            "device_name": shocker_info.get('device_name', 'Unknown Device') if shocker_info else 'Unknown Device'
        }
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
    
    def test_leftleg(self):
        """Test leftleg shocker"""
        if not self.messenger or not hasattr(self.messenger, 'shock_controller'):
            messagebox.showerror("Error", "No shock controller available")
            return
        
        # Disable button during test
        self.test_leftleg_button.config(state='disabled', text='Testing...')
        
        def test_thread():
            try:
                # Run the leftleg test
                self.messenger.shock_controller.test_leftleg_shock()
                self.root.after(0, lambda: messagebox.showinfo("Test Complete", "Left leg test shock sent!"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Test Failed", f"Left leg test failed: {str(e)}"))
            finally:
                # Re-enable button
                self.root.after(0, lambda: self.test_leftleg_button.config(state='normal', text='Test Left Leg'))
        
        # Start test in background thread
        threading.Thread(target=test_thread, daemon=True).start()
    
    def test_rightleg(self):
        """Test rightleg shocker"""
        if not self.messenger or not hasattr(self.messenger, 'shock_controller'):
            messagebox.showerror("Error", "No shock controller available")
            return
        
        # Disable button during test
        self.test_rightleg_button.config(state='disabled', text='Testing...')
        
        def test_thread():
            try:
                # Run the rightleg test
                self.messenger.shock_controller.test_rightleg_shock()
                self.root.after(0, lambda: messagebox.showinfo("Test Complete", "Right leg test shock sent!"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Test Failed", f"Right leg test failed: {str(e)}"))
            finally:
                # Re-enable button
                self.root.after(0, lambda: self.test_rightleg_button.config(state='normal', text='Test Right Leg'))
        
        # Start test in background thread
        threading.Thread(target=test_thread, daemon=True).start()
    
    def _convert_legacy_shocker_config(self):
        """Convert legacy shocker config format (string) to new format (dict)"""
        shock_config = self.config.get("shockosc", {})
        shockers_config = shock_config.get("shockers", {})
        
        # Check if we have any legacy entries to convert
        needs_save = False
        for shocker_id, assignment_info in shockers_config.items():
            if isinstance(assignment_info, str):
                # This is a legacy entry - convert it
                shockers_config[shocker_id] = {
                    "group": assignment_info,
                    "name": f"Shocker {shocker_id[:8]}...",
                    "device_name": "Unknown Device"
                }
                needs_save = True
        
        # Save if we made changes
        if needs_save:
            save_app_config(self.config)
        
    def run(self):
        """Run the GUI"""
        self.root.mainloop()


def show_settings_gui(messenger=None):
    """Show the settings GUI"""
    gui = VRCChatboxGUI(messenger)
    gui.run()


if __name__ == "__main__":
    show_settings_gui()