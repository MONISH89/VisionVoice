import time
import threading
import logging
import config

logger = logging.getLogger("VisionVoice.Buttons")

class HardwareButtonController:
    """
    Physical GPIO Hardware Controls and LED Status Indicator Manager.
    
    GPIO PINOUT (BCM Numbering):
      - GPIO17 -> Main / Interaction button (Pull-Up)
      - GPIO27 -> Volume Up button (Pull-Up)
      - GPIO22 -> Volume Down button (Pull-Up)
      - GPIO24 -> Status LED (Output)

    LED STATE INDICATION:
      - WAIT_WAKE_WORD  -> Ready indication (Solid ON)
      - LISTENING       -> Listening indication (Steady pulse: 0.3s on / 0.3s off)
      - ALIGNING_PAGE   -> Alignment indication (Medium blink: 0.2s on / 0.2s off)
      - PROCESSING_PAGE -> Processing indication (Fast blink: 0.07s on / 0.07s off)
      - READING         -> Reading indication (Solid ON)
      - ERROR           -> Error indication (3 fast strobe blinks + 0.5s pause)

    CRITICAL ARCHITECTURE:
      - Completely headless operation without any HDMI, display, or GUI dependency.
      - Double hardware and software debouncing on all button pins.
      - Asynchronous, non-blocking button callback dispatch to avoid stalling the main FSM.
    """

    def __init__(self, main_callback=None, vol_up_callback=None, vol_down_callback=None, power_callback=None):
        self.main_callback = main_callback or power_callback
        self.power_callback = power_callback
        self.vol_up_callback = vol_up_callback
        self.vol_down_callback = vol_down_callback

        self.gpio_available = False
        self.running = False
        self.led_state = False
        self.current_indication_state = "OFF"
        self.GPIO = None

        # Threading and LED control
        self._led_thread = None
        self._led_lock = threading.Lock()
        self._last_press_times = {}
        self._debounce_cooldown = 0.25  # seconds

        self._init_gpio()

    def _init_gpio(self):
        """Attempts to initialize RPi.GPIO library using BCM numbering."""
        try:
            import RPi.GPIO as GPIO  # type: ignore
            self.GPIO = GPIO
            self.GPIO.setmode(GPIO.BCM)
            self.GPIO.setwarnings(False)

            # Setup Input Pins with Internal Pull-Up Resistors
            # GPIO17 -> Main / Interaction button
            # GPIO27 -> Volume Up
            # GPIO22 -> Volume Down
            pin_main = getattr(config, "PIN_MAIN_BTN", 17)
            pin_vol_up = getattr(config, "PIN_VOL_UP_BTN", 27)
            pin_vol_down = getattr(config, "PIN_VOL_DOWN_BTN", 22)
            pin_led = getattr(config, "PIN_STATUS_LED", 24)

            self.GPIO.setup(pin_main, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            self.GPIO.setup(pin_vol_up, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            self.GPIO.setup(pin_vol_down, GPIO.IN, pull_up_down=GPIO.PUD_UP)

            # Setup Status LED Output Pin
            self.GPIO.setup(pin_led, GPIO.OUT)
            self.GPIO.output(pin_led, GPIO.LOW)

            # Add Hardware Interrupt Event Detectors with 300ms bouncetime
            self.GPIO.add_event_detect(pin_main, GPIO.FALLING, callback=self._on_main_btn_interrupt, bouncetime=300)
            self.GPIO.add_event_detect(pin_vol_up, GPIO.FALLING, callback=self._on_vol_up_btn_interrupt, bouncetime=250)
            self.GPIO.add_event_detect(pin_vol_down, GPIO.FALLING, callback=self._on_vol_down_btn_interrupt, bouncetime=250)

            self.gpio_available = True
            logger.info("RPi.GPIO hardware buttons (GPIO17, GPIO27, GPIO22) and Status LED (GPIO24) initialized with BCM numbering.")
        except Exception as e:
            logger.warning(f"RPi.GPIO hardware initialization unavailable ({e}). Running in fallback mode.")
            self.gpio_available = False

    def start(self):
        """Starts hardware controller workers and background LED indication loop."""
        if self.running:
            return
        self.running = True
        self._led_thread = threading.Thread(target=self._led_indication_loop, daemon=True)
        self._led_thread.start()
        logger.info("Hardware button controller & LED indication thread started.")

    # --- Debounced Non-Blocking Interrupt Handlers ---

    def _is_debounced(self, pin):
        """Software debounce check to eliminate physical contact bounce."""
        now = time.time()
        last = self._last_press_times.get(pin, 0.0)
        if (now - last) >= self._debounce_cooldown:
            self._last_press_times[pin] = now
            return True
        return False

    def _on_main_btn_interrupt(self, channel):
        """Hardware interrupt for GPIO17. Spawns asynchronous non-blocking worker."""
        if not self._is_debounced(channel):
            return
        threading.Thread(target=self._async_handle_main_press, daemon=True).start()

    def _async_handle_main_press(self):
        """
        Asynchronously measures hold duration on GPIO17.
        Short press (<2.5s) -> Main interaction callback.
        Long press (>=2.5s) -> Power off callback.
        Never blocks the main FSM thread.
        """
        logger.info("Physical Main/Interaction Button (GPIO17) pressed!")
        pin_main = getattr(config, "PIN_MAIN_BTN", 17)

        # Distinguish short press vs long press if GPIO is active
        if self.gpio_available and self.GPIO is not None:
            press_time = time.time()
            time.sleep(0.04)  # Short debounce settle
            while self.GPIO.input(pin_main) == self.GPIO.LOW:
                if (time.time() - press_time) >= 2.5:
                    logger.info("Main button held >=2.5s: Triggering Power Off shutdown.")
                    if self.power_callback:
                        self.power_callback()
                    return
                time.sleep(0.05)

        # Short press interaction trigger
        if self.main_callback:
            self.main_callback()

    def _on_vol_up_btn_interrupt(self, channel):
        """Hardware interrupt for GPIO27 (Volume Up). Spawns non-blocking worker."""
        if not self._is_debounced(channel):
            return
        threading.Thread(target=self._async_handle_vol_up, daemon=True).start()

    def _async_handle_vol_up(self):
        logger.info("Physical Volume Up Button (GPIO27) pressed!")
        if self.vol_up_callback:
            self.vol_up_callback()

    def _on_vol_down_btn_interrupt(self, channel):
        """Hardware interrupt for GPIO22 (Volume Down). Spawns non-blocking worker."""
        if not self._is_debounced(channel):
            return
        threading.Thread(target=self._async_handle_vol_down, daemon=True).start()

    def _async_handle_vol_down(self):
        logger.info("Physical Volume Down Button (GPIO22) pressed!")
        if self.vol_down_callback:
            self.vol_down_callback()

    # --- System State LED Indications ---

    def indicate_state(self, state_name):
        """
        Sets the active system state for LED signaling.

        Supported states:
          - 'WAIT_WAKE_WORD' / 'READY' -> Ready indication (Solid ON)
          - 'LISTENING' / 'ASK_PREFERENCES' -> Listening indication (Steady 0.3s pulse)
          - 'ALIGNING_PAGE' -> Alignment indication (0.2s medium blink)
          - 'PROCESSING_PAGE' -> Processing indication (0.07s rapid flash)
          - 'READING' -> Reading indication (Solid ON)
          - 'ERROR' -> Error indication (3 quick bursts + pause)
          - 'OFF' -> LED off
        """
        with self._led_lock:
            if self.current_indication_state != state_name:
                self.current_indication_state = state_name
                logger.debug(f"LED Status Pattern set to: '{state_name}'")

    def _set_physical_led(self, state):
        """Directly writes HIGH or LOW to GPIO24 output pin."""
        self.led_state = state
        if self.gpio_available and self.GPIO is not None:
            pin_led = getattr(config, "PIN_STATUS_LED", 24)
            try:
                self.GPIO.output(pin_led, self.GPIO.HIGH if state else self.GPIO.LOW)
            except Exception as e:
                logger.debug(f"LED output write error: {e}")

    def _led_indication_loop(self):
        """Continuous background thread rendering state patterns on GPIO24."""
        while self.running:
            with self._led_lock:
                state = self.current_indication_state

            if state in ["WAIT_WAKE_WORD", "WAIT_START_READING", "READY", "READING"]:
                # Ready & Reading: Solid ON
                self._set_physical_led(True)
                time.sleep(0.1)

            elif state in ["LISTENING", "ASK_PREFERENCES"]:
                # Listening: Steady pulse (0.3s ON / 0.3s OFF)
                self._set_physical_led(True)
                time.sleep(0.3)
                self._set_physical_led(False)
                time.sleep(0.3)

            elif state == "ALIGNING_PAGE":
                # Page Alignment: Medium blink (0.2s ON / 0.2s OFF)
                self._set_physical_led(True)
                time.sleep(0.2)
                self._set_physical_led(False)
                time.sleep(0.2)

            elif state == "PROCESSING_PAGE":
                # Page Processing / OCR: Fast blink (0.07s ON / 0.07s OFF)
                self._set_physical_led(True)
                time.sleep(0.07)
                self._set_physical_led(False)
                time.sleep(0.07)

            elif state == "ERROR":
                # Error: 3 rapid strobe bursts then 0.5s pause
                for _ in range(3):
                    self._set_physical_led(True)
                    time.sleep(0.06)
                    self._set_physical_led(False)
                    time.sleep(0.06)
                time.sleep(0.4)

            elif state == "PAGE_FINISHED":
                # Page Finished: Slow double blink
                for _ in range(2):
                    self._set_physical_led(True)
                    time.sleep(0.15)
                    self._set_physical_led(False)
                    time.sleep(0.15)
                time.sleep(0.3)

            elif state == "OFF":
                self._set_physical_led(False)
                time.sleep(0.1)

            else:
                self._set_physical_led(True)
                time.sleep(0.1)

    # Convenience helper methods
    def set_led(self, state):
        """Sets status LED solid ON or OFF."""
        self.indicate_state("READY" if state else "OFF")

    def start_led_blink(self, interval=0.3):
        """Compatibility helper for setting blink."""
        if interval <= 0.1:
            self.indicate_state("PROCESSING_PAGE")
        elif interval <= 0.25:
            self.indicate_state("ALIGNING_PAGE")
        else:
            self.indicate_state("LISTENING")

    def cleanup(self):
        """Releases GPIO pins and terminates LED background thread on shutdown."""
        self.running = False
        self._set_physical_led(False)
        if self.gpio_available and self.GPIO is not None:
            try:
                self.GPIO.cleanup()
                logger.info("GPIO pins cleaned up successfully.")
            except Exception as e:
                logger.error(f"Error during GPIO cleanup: {e}")
