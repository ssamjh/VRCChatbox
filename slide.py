import random
import threading
import time


class SlideController:
    def __init__(self, dispatcher, shock_controller):
        """Initialize Slide controller

        Args:
            dispatcher: pythonosc dispatcher for OSC message routing
            shock_controller: ShockOSCController instance for triggering shocks
        """
        # Threading components
        self.polling_thread = None
        self.polling_active = False
        self.values_lock = threading.Lock()

        # OSC integration
        self.dispatcher = dispatcher
        self.shock_controller = shock_controller
        self.current_values = {}  # {osc_path: float_value}

        # Config
        self.config = {}

        print("SlideController initialized")

    def update_config(self, config):
        """Update slide configuration and restart polling if needed

        Args:
            config: Dictionary containing slide configuration
        """
        # Stop existing polling
        self.stop_polling()

        # Update config
        self.config = config
        print(f"Slide config updated: {self.config}")

        # Update dispatcher mappings for OSC variables
        self._update_dispatcher_mappings()

        # Start polling if enabled
        if config.get("enabled", False):
            self.start_polling()

    def start_polling(self):
        """Start the polling thread"""
        if self.polling_thread and self.polling_thread.is_alive():
            print("Slide polling already running")
            return

        self.polling_active = True
        self.polling_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self.polling_thread.start()
        print("Slide polling started")

    def stop_polling(self):
        """Stop the polling thread and wait for it to finish"""
        if not self.polling_active:
            return

        self.polling_active = False

        # Wait for thread to finish (with timeout)
        if self.polling_thread and self.polling_thread.is_alive():
            self.polling_thread.join(timeout=2.0)
            print("Slide polling stopped")

    def _poll_loop(self):
        """Main polling loop - runs in separate thread"""
        print("Slide polling loop started")
        while self.polling_active:
            try:
                self._check_all_variables()
            except Exception as e:
                print(f"Error in slide polling loop: {e}")

            # Sleep for poll interval
            poll_interval = self.config.get("poll_interval", 1.0)
            time.sleep(poll_interval)

    def _check_all_variables(self):
        """Check all enabled variables and trigger shocks based on probability"""
        variables = self.config.get("variables", [])

        for var in variables:
            # Skip disabled variables
            if not var.get("enabled", True):
                continue

            try:
                self._check_variable(var)
            except Exception as e:
                print(f"Error checking variable {var.get('name', 'unknown')}: {e}")

    def _check_variable(self, var):
        """Check a single variable and potentially trigger shock

        Args:
            var: Variable configuration dictionary with osc_path, threshold, etc.
        """
        osc_path = var.get("osc_path")
        threshold = var.get("threshold", 0.0)

        if not osc_path:
            return

        # Get current value from cache (thread-safe)
        with self.values_lock:
            current_value = self.current_values.get(osc_path, 0.0)

        # Check threshold
        if current_value < threshold:
            return

        # Cubic probability curve for dramatic ramp-up
        # P = value³ gives: 0.5→12.5%, 0.7→34%, 0.9→73%
        probability = current_value ** 3
        if random.random() <= probability:
            # Probability succeeded - trigger shock
            self._trigger_slide_shock(var, current_value)

    def _trigger_slide_shock(self, var, current_value):
        """Trigger a shock from a slide variable

        Args:
            var: Variable configuration that triggered the shock
            current_value: Current OSC value that triggered the shock
        """
        # Check if shock system is enabled
        if not self.shock_controller.config.get("enabled", False):
            return

        # Get shocker IDs for this variable
        variable_shockers = var.get("shockers", [])
        shockers_config = self.shock_controller.config.get("shockers", {})

        # If no shockers specified, use all available shockers
        if not variable_shockers:
            variable_shockers = list(shockers_config.keys())

        if not variable_shockers:
            print(f"Slide shock skipped - no shockers configured")
            return

        # Filter out shockers whose groups are on cooldown
        available_shockers = []
        for shocker_id in variable_shockers:
            if shocker_id in shockers_config:
                shocker_info = shockers_config[shocker_id]
                # Handle both old format (string) and new format (dict)
                group = shocker_info.get("group") if isinstance(shocker_info, dict) else shocker_info

                # Only include if group is not on cooldown
                if not self.shock_controller.is_group_on_cooldown(group):
                    available_shockers.append(shocker_id)

        if not available_shockers:
            print(f"Slide shock skipped - all selected shockers on cooldown")
            return

        # Directly send command to shockers (bypass group-based send_shock)
        intensity = self.shock_controller.get_shock_intensity()
        duration = self.shock_controller.config.get("duration", 1.0)
        self.shock_controller.send_openshock_command(available_shockers, intensity, duration)

        # Start cooldown for affected groups
        for shocker_id in available_shockers:
            if shocker_id in shockers_config:
                shocker_info = shockers_config[shocker_id]
                group = shocker_info.get("group") if isinstance(shocker_info, dict) else shocker_info
                self.shock_controller.start_cooldown(group)

        var_name = var.get("name", var.get("osc_path", "unknown"))
        probability = current_value ** 3
        print(f"Slide shock triggered from '{var_name}' (value: {current_value:.2f}, probability: {probability:.1%}, shockers: {len(available_shockers)})")

    def _handle_variable_update(self, address, *args):
        """OSC handler to cache variable values

        Args:
            address: OSC address path
            *args: OSC arguments (first should be the float value)
        """
        # Check if this address is still configured (conditional handler)
        if not any(v.get("osc_path") == address for v in self.config.get("variables", [])):
            return

        # Thread-safe value update
        with self.values_lock:
            self.current_values[address] = float(args[0]) if args else 0.0

    def _update_dispatcher_mappings(self):
        """Add/update dispatcher handlers for all configured OSC variables

        Note: pythonosc doesn't have an unmap method, so we use conditional
        handlers that check if the path is still configured before processing.
        """
        variables = self.config.get("variables", [])

        # Add mappings for all configured variables
        for var in variables:
            osc_path = var.get("osc_path")
            if osc_path:
                # Map the OSC path to our handler
                # The handler will check if the path is still configured
                self.dispatcher.map(osc_path, self._handle_variable_update)

        print(f"Dispatcher mappings updated for {len(variables)} variables")

    def is_group_on_cooldown(self, group):
        """Check if a shock group is on cooldown

        Args:
            group: Group name to check

        Returns:
            bool: True if group is on cooldown, False otherwise
        """
        # Delegate to shock controller
        return self.shock_controller.is_group_on_cooldown(group)
