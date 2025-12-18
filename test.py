#!/usr/bin/env python3
"""
VRChat OSC Monitor
A real-time monitor for VRChat OSC parameters and their values.

Requirements:
    pip install python-osc

Usage:
    python vrchat_osc_monitor.py

VRChat sends OSC data to port 9001 by default.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
from datetime import datetime
from threading import Thread
import queue

try:
    from pythonosc import dispatcher, osc_server
except ImportError:
    print("Please install python-osc: pip install python-osc")
    exit(1)


class VRChatOSCMonitor:
    def __init__(self, root):
        self.root = root
        self.root.title("VRChat OSC Monitor")
        self.root.geometry("900x700")
        self.root.configure(bg="#1a1a2e")
        
        # Data storage
        self.parameters = {}  # {address: (value, last_update)}
        self.update_queue = queue.Queue()
        self.server = None
        self.server_thread = None
        
        # Style configuration
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.configure_styles()
        
        # Build UI
        self.create_ui()
        
        # Start OSC server
        self.start_osc_server()
        
        # Start UI update loop
        self.process_updates()
    
    def configure_styles(self):
        self.style.configure("Title.TLabel", 
                           background="#1a1a2e", 
                           foreground="#00d9ff",
                           font=("Segoe UI", 16, "bold"))
        self.style.configure("Status.TLabel",
                           background="#1a1a2e",
                           foreground="#00ff88",
                           font=("Segoe UI", 10))
        self.style.configure("Info.TLabel",
                           background="#1a1a2e",
                           foreground="#888888",
                           font=("Segoe UI", 9))
        self.style.configure("Custom.Treeview",
                           background="#16213e",
                           foreground="#ffffff",
                           fieldbackground="#16213e",
                           font=("Consolas", 10))
        self.style.configure("Custom.Treeview.Heading",
                           background="#0f3460",
                           foreground="#00d9ff",
                           font=("Segoe UI", 10, "bold"))
        self.style.map("Custom.Treeview",
                      background=[("selected", "#0f3460")])
    
    def create_ui(self):
        # Main container
        main_frame = tk.Frame(self.root, bg="#1a1a2e")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Header
        header_frame = tk.Frame(main_frame, bg="#1a1a2e")
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        title_label = ttk.Label(header_frame, 
                               text="🎮 VRChat OSC Monitor",
                               style="Title.TLabel")
        title_label.pack(side=tk.LEFT)
        
        self.status_label = ttk.Label(header_frame,
                                     text="● Listening on port 9001",
                                     style="Status.TLabel")
        self.status_label.pack(side=tk.RIGHT)
        
        # Stats frame
        stats_frame = tk.Frame(main_frame, bg="#16213e", padx=10, pady=5)
        stats_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.param_count_label = ttk.Label(stats_frame,
                                          text="Parameters: 0",
                                          style="Info.TLabel")
        self.param_count_label.pack(side=tk.LEFT, padx=(0, 20))
        
        self.update_count_label = ttk.Label(stats_frame,
                                           text="Updates: 0",
                                           style="Info.TLabel")
        self.update_count_label.pack(side=tk.LEFT, padx=(0, 20))
        
        self.last_update_label = ttk.Label(stats_frame,
                                          text="Last update: --",
                                          style="Info.TLabel")
        self.last_update_label.pack(side=tk.LEFT)
        
        # Clear button
        clear_btn = tk.Button(stats_frame, 
                             text="Clear All",
                             command=self.clear_parameters,
                             bg="#e94560",
                             fg="white",
                             relief=tk.FLAT,
                             padx=10)
        clear_btn.pack(side=tk.RIGHT)
        
        # Search frame
        search_frame = tk.Frame(main_frame, bg="#1a1a2e")
        search_frame.pack(fill=tk.X, pady=(0, 10))
        
        search_label = ttk.Label(search_frame, 
                                text="Filter:",
                                style="Info.TLabel")
        search_label.pack(side=tk.LEFT, padx=(0, 5))
        
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self.on_filter_change)
        search_entry = tk.Entry(search_frame,
                               textvariable=self.search_var,
                               bg="#16213e",
                               fg="#ffffff",
                               insertbackground="#00d9ff",
                               relief=tk.FLAT,
                               font=("Consolas", 10))
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5)
        
        # Treeview for parameters
        tree_frame = tk.Frame(main_frame, bg="#1a1a2e")
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create treeview with scrollbars
        self.tree = ttk.Treeview(tree_frame, 
                                columns=("address", "value", "type", "updated"),
                                show="headings",
                                style="Custom.Treeview")
        
        # Column configuration
        self.tree.heading("address", text="OSC Address")
        self.tree.heading("value", text="Value")
        self.tree.heading("type", text="Type")
        self.tree.heading("updated", text="Last Updated")
        
        self.tree.column("address", width=350, minwidth=200)
        self.tree.column("value", width=200, minwidth=100)
        self.tree.column("type", width=80, minwidth=60)
        self.tree.column("updated", width=150, minwidth=100)
        
        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        # Grid layout for treeview
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        
        tree_frame.grid_columnconfigure(0, weight=1)
        tree_frame.grid_rowconfigure(0, weight=1)
        
        # Log frame
        log_frame = tk.Frame(main_frame, bg="#1a1a2e")
        log_frame.pack(fill=tk.X, pady=(10, 0))
        
        log_label = ttk.Label(log_frame, 
                             text="Recent Activity:",
                             style="Info.TLabel")
        log_label.pack(anchor=tk.W)
        
        self.log_text = scrolledtext.ScrolledText(log_frame,
                                                  height=6,
                                                  bg="#16213e",
                                                  fg="#888888",
                                                  font=("Consolas", 9),
                                                  relief=tk.FLAT)
        self.log_text.pack(fill=tk.X, pady=(5, 0))
        
        # Update counter
        self.update_count = 0
    
    def start_osc_server(self):
        """Start the OSC server to listen for VRChat data."""
        disp = dispatcher.Dispatcher()
        disp.set_default_handler(self.osc_handler)
        
        try:
            self.server = osc_server.ThreadingOSCUDPServer(
                ("127.0.0.1", 9001), disp
            )
            self.server_thread = Thread(target=self.server.serve_forever, daemon=True)
            self.server_thread.start()
            self.log_message("OSC server started on 127.0.0.1:9001")
        except OSError as e:
            self.status_label.configure(text="● Error: Port 9001 in use", 
                                       foreground="#e94560")
            self.log_message(f"Error starting server: {e}")
    
    def osc_handler(self, address, *args):
        """Handle incoming OSC messages."""
        value = args[0] if len(args) == 1 else list(args)
        timestamp = datetime.now()
        self.update_queue.put((address, value, timestamp))
    
    def process_updates(self):
        """Process queued updates and refresh UI."""
        updates_this_cycle = 0
        
        while not self.update_queue.empty() and updates_this_cycle < 100:
            try:
                address, value, timestamp = self.update_queue.get_nowait()
                self.parameters[address] = (value, timestamp)
                self.update_count += 1
                updates_this_cycle += 1
                
                # Log significant updates
                if updates_this_cycle <= 3:
                    self.log_message(f"{address} = {value}")
                    
            except queue.Empty:
                break
        
        if updates_this_cycle > 0:
            self.refresh_treeview()
            self.param_count_label.configure(text=f"Parameters: {len(self.parameters)}")
            self.update_count_label.configure(text=f"Updates: {self.update_count}")
            self.last_update_label.configure(
                text=f"Last update: {datetime.now().strftime('%H:%M:%S')}"
            )
        
        # Schedule next update
        self.root.after(50, self.process_updates)
    
    def refresh_treeview(self):
        """Refresh the treeview with current parameters."""
        filter_text = self.search_var.get().lower()
        
        # Store current selection
        selected = self.tree.selection()
        selected_addresses = [self.tree.item(s)["values"][0] for s in selected if s]
        
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Re-populate with filtered data
        for address, (value, timestamp) in sorted(self.parameters.items()):
            if filter_text and filter_text not in address.lower():
                continue
            
            # Determine value type
            value_type = type(value).__name__
            if isinstance(value, bool):
                value_type = "bool"
            elif isinstance(value, float):
                value_type = "float"
            elif isinstance(value, int):
                value_type = "int"
            
            # Format value for display
            display_value = str(value)
            if isinstance(value, float):
                display_value = f"{value:.4f}"
            elif isinstance(value, bool):
                display_value = "True" if value else "False"
            
            time_str = timestamp.strftime("%H:%M:%S.%f")[:-3]
            
            item_id = self.tree.insert("", tk.END, values=(
                address, display_value, value_type, time_str
            ))
            
            # Restore selection
            if address in selected_addresses:
                self.tree.selection_add(item_id)
    
    def on_filter_change(self, *args):
        """Handle filter text changes."""
        self.refresh_treeview()
    
    def clear_parameters(self):
        """Clear all stored parameters."""
        self.parameters.clear()
        self.update_count = 0
        self.refresh_treeview()
        self.param_count_label.configure(text="Parameters: 0")
        self.update_count_label.configure(text="Updates: 0")
        self.log_message("Cleared all parameters")
    
    def log_message(self, message):
        """Add a message to the log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        
        # Limit log size
        lines = int(self.log_text.index('end-1c').split('.')[0])
        if lines > 100:
            self.log_text.delete('1.0', '2.0')
    
    def on_closing(self):
        """Handle window close."""
        if self.server:
            self.server.shutdown()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = VRChatOSCMonitor(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()