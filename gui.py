import tkinter as tk
from tkinter import ttk
from config import load_app_config, save_app_config


class VRCChatboxGUI:
    def __init__(self, messenger=None):
        self.messenger = messenger
        self.config = load_app_config()
        
        # Create main window
        self.root = tk.Tk()
        self.root.title("VRC Chatbox Settings")
        self.root.geometry("400x450")
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
        
        # Configure column weights for proper stretching
        parent.columnconfigure(1, weight=1)
        self.static_frame.columnconfigure(1, weight=1)
        self.random_frame.columnconfigure(1, weight=1)
        duration_frame.columnconfigure(1, weight=1)
        
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
            "hold_time": round(self.hold_time_var.get(), 2)
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
        
    def run(self):
        """Run the GUI"""
        self.root.mainloop()


def show_settings_gui(messenger=None):
    """Show the settings GUI"""
    gui = VRCChatboxGUI(messenger)
    gui.run()


if __name__ == "__main__":
    show_settings_gui()