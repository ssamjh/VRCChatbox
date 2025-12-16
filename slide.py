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

        # Hold mode tracking
        self.hold_timers = {}  # {osc_path: threading.Timer}
        self.hold_active = {}  # {osc_path: bool}

        # Probability mode cooldown tracking
        self.probability_cooldowns = {}  # {osc_path: timestamp}

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

        # Cancel all hold timers
        for timer in self.hold_timers.values():
            if timer:
                timer.cancel()
        self.hold_timers.clear()
        self.hold_active.clear()

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
            # Cancel any active hold timer if below threshold
            self._cancel_hold_timer(osc_path)
            return

        # Handle hold mode (if enabled)
        if var.get("hold_mode", False):
            hold_threshold = var.get("hold_threshold", 0.9)
            hold_time = var.get("hold_time", 3.0)

            if current_value >= hold_threshold:
                # Start hold timer if not already active
                if osc_path not in self.hold_active or not self.hold_active[osc_path]:
                    self._start_hold_timer(var, current_value, hold_time)
            else:
                # Cancel hold timer if value dropped below threshold
                self._cancel_hold_timer(osc_path)

        # Cubic probability curve for dramatic ramp-up (always active)
        # P = value³ gives: 0.5→12.5%, 0.7→34%, 0.9→73%
        # Check probability cooldown before triggering
        if not self._is_probability_on_cooldown(osc_path):
            probability = current_value ** 3
            if random.random() <= probability:
                # Probability succeeded - trigger shock with value-based intensity
                self._trigger_slide_shock(var, current_value, use_value_intensity=True, skip_cooldown=False)

    def _trigger_slide_shock(self, var, current_value, use_value_intensity=True, skip_cooldown=False):
        """Trigger a shock from a slide variable

        Args:
            var: Variable configuration that triggered the shock
            current_value: Current OSC value that triggered the shock
            use_value_intensity: If True, use value-based intensity; if False, use random from hold mode range
            skip_cooldown: If True, don't start probability cooldown (used for hold mode)
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
        affected_groups = []
        for shocker_id in variable_shockers:
            if shocker_id in shockers_config:
                shocker_info = shockers_config[shocker_id]
                # Handle both old format (string) and new format (dict)
                group = shocker_info.get("group") if isinstance(shocker_info, dict) else shocker_info

                # Only include if group is not on cooldown
                if not self.shock_controller.is_group_on_cooldown(group):
                    available_shockers.append(shocker_id)
                    if group not in affected_groups:
                        affected_groups.append(group)

        if not available_shockers:
            print(f"Slide shock skipped - all selected shockers on cooldown")
            return

        # Calculate intensity
        if use_value_intensity:
            # Value-based intensity using global range
            min_intensity = self.config.get("intensity_min", 30)
            max_intensity = self.config.get("intensity_max", 70)
            intensity = int(min_intensity + (current_value * (max_intensity - min_intensity)))
            intensity = max(0, min(100, intensity))  # Clamp to 0-100
            intensity_source = "value-based"
        else:
            # Use hold mode intensity range
            hold_min = self.config.get("hold_intensity_min", 80)
            hold_max = self.config.get("hold_intensity_max", 90)
            intensity = random.randint(hold_min, hold_max)
            intensity_source = "hold mode"

        duration = self.shock_controller.config.get("duration", 1.0)
        self.shock_controller.send_openshock_command(available_shockers, intensity, duration)

        # Start cooldown for affected groups and trigger shock callback
        for group in affected_groups:
            self.shock_controller.start_cooldown(group)
            # Trigger the shock callback to display in chatbox
            if self.shock_controller.shock_callback:
                self.shock_controller.shock_callback(intensity, group, duration)

        # Start probability cooldown if not skipped (hold mode skips this)
        if not skip_cooldown:
            osc_path = var.get("osc_path")
            if osc_path:
                self._start_probability_cooldown(osc_path)

        var_name = var.get("name", var.get("osc_path", "unknown"))
        trigger_type = "hold mode" if skip_cooldown else "probability"
        print(f"Slide shock triggered from '{var_name}' [{trigger_type}] (value: {current_value:.2f}, intensity: {intensity}% [{intensity_source}], shockers: {len(available_shockers)})")

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

    def _start_hold_timer(self, var, current_value, hold_time):
        """Start hold timer for a variable

        Args:
            var: Variable configuration
            current_value: Current OSC value
            hold_time: How long to hold before triggering (seconds)
        """
        osc_path = var.get("osc_path")

        # Cancel existing timer if any
        self._cancel_hold_timer(osc_path)

        # Mark as active
        self.hold_active[osc_path] = True

        # Create timer
        timer = threading.Timer(hold_time, self._trigger_hold_shock, [var, current_value])
        self.hold_timers[osc_path] = timer
        timer.start()

        var_name = var.get("name", osc_path)
        print(f"Hold timer started for '{var_name}' ({hold_time}s)")

    def _cancel_hold_timer(self, osc_path):
        """Cancel hold timer for a variable

        Args:
            osc_path: OSC path to cancel timer for
        """
        if osc_path in self.hold_timers:
            timer = self.hold_timers[osc_path]
            if timer:
                timer.cancel()
            del self.hold_timers[osc_path]

        if osc_path in self.hold_active:
            del self.hold_active[osc_path]

    def _trigger_hold_shock(self, var, current_value):
        """Trigger shock from hold mode (uses random intensity)

        Args:
            var: Variable configuration that triggered the shock
            current_value: Current OSC value when hold timer started
        """
        osc_path = var.get("osc_path")

        # Clear hold state
        if osc_path in self.hold_active:
            del self.hold_active[osc_path]

        var_name = var.get("name", osc_path)
        print(f"Hold mode shock triggered for '{var_name}' (value: {current_value:.2f})")

        # Trigger with random intensity (not value-based), bypassing cooldown
        self._trigger_slide_shock(var, current_value, use_value_intensity=False, skip_cooldown=True)

    def _is_probability_on_cooldown(self, osc_path):
        """Check if a variable is on probability cooldown

        Args:
            osc_path: OSC path to check

        Returns:
            bool: True if on cooldown, False otherwise
        """
        if osc_path not in self.probability_cooldowns:
            return False

        cooldown_time = self.config.get("probability_cooldown", 10.0)
        elapsed = time.time() - self.probability_cooldowns[osc_path]
        return elapsed < cooldown_time

    def _start_probability_cooldown(self, osc_path):
        """Start probability cooldown for a variable

        Args:
            osc_path: OSC path to start cooldown for
        """
        self.probability_cooldowns[osc_path] = time.time()
