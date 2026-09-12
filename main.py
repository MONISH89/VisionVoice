import os
import sys
import time
import signal
import logging

# Configure Master System Logger
import config

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(config.LOGS_DIR, "visionvoice.log"), encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("VisionVoice.Main")

from camera import CameraManager
from alignment import PageAlignmentAnalyzer
from page_processor import PageProcessor
from ocr import OCRManager
from language import LanguageDetector
from translator import TranslationEngine
from speech import SpeechEngine
from voice_control import VoiceController
from memory import BookMemoryManager
from buttons import HardwareButtonController

class VisionVoiceApp:
    """
    Master Application Controller & Finite State Machine (FSM) for VisionVoice.
    Operates as an integrated, hands-free smart physical-book assistive reading device.

    CRITICAL RELIABILITY ARCHITECTURE:
    - Every state has clear entry conditions, exit conditions, timeouts, and error paths.
    - All state transitions are explicitly logged.
    - No infinite unmonitored loops.
    """

    def __init__(self):
        logger.info(f"Initializing {config.APP_NAME} v{config.VERSION}...")

        # System Components Initialization
        self.camera = CameraManager()
        self.alignment = PageAlignmentAnalyzer()
        self.processor = PageProcessor()
        self.ocr = OCRManager()
        self.lang_detector = LanguageDetector()
        self.translator = TranslationEngine()
        self.speech = SpeechEngine()
        self.memory = BookMemoryManager()
        self.voice = VoiceController(callback_handler=self.on_voice_command)
        self.buttons = HardwareButtonController(
            main_callback=self.on_main_button,
            vol_up_callback=self.on_volume_up_button,
            vol_down_callback=self.on_volume_down_button,
            power_callback=self.on_power_button
        )

        # FSM State & Lifecycle Control
        self.state = "BOOT"
        self.state_entry_time = time.time()
        self.running = True
        self.current_sentences = []
        self._current_sentence_index = 0
        self.reading_active = False
        self.pause_requested = False
        self.ocr_retry_count = 0
        self.prompted_start_reading = False

        # User Preferences
        self.preferred_lang = self.memory.preferred_language
        self.reading_mode = self.memory.reading_mode
        self.current_book_lang = config.DEFAULT_LANGUAGE

        # Register Signal Handlers for Clean Headless Shutdown (SIGINT / SIGTERM)
        try:
            signal.signal(signal.SIGINT, self.signal_handler)
            signal.signal(signal.SIGTERM, self.signal_handler)
            logger.info("Signal handlers registered for SIGINT & SIGTERM.")
        except Exception as e:
            logger.debug(f"Signal handler registration note: {e}")

    @property
    def current_sentence_index(self):
        return self._current_sentence_index

    @current_sentence_index.setter
    def current_sentence_index(self, val):
        self._current_sentence_index = max(0, val)

    @property
    def current_sentence_idx(self):
        return self._current_sentence_index

    @current_sentence_idx.setter
    def current_sentence_idx(self, val):
        self._current_sentence_index = max(0, val)

    def set_state(self, new_state):
        """
        Transitions the FSM to a new state with explicit logging and lifecycle bookkeeping.
        Updates physical GPIO status LED pattern according to system state.
        """
        if self.state != new_state:
            logger.info(f"FSM State Transition: '{self.state}' -> '{new_state}'")
            self.state = new_state
            self.state_entry_time = time.time()

            # Update LED state indication pattern on GPIO24
            if hasattr(self, "buttons") and self.buttons:
                self.buttons.indicate_state(new_state)

            # State entry housekeeping
            if new_state == "WAIT_START_READING":
                self.prompted_start_reading = False
            elif new_state in ["WAIT_WAKE_WORD", "READING"]:
                self.ocr_retry_count = 0

    def start(self):
        """Starts background hardware workers and enters main lifecycle loop."""
        logger.info("Starting VisionVoice application services...")
        self.camera.start()
        self.voice.start_listening()
        self.buttons.start()

        self.run_fsm()

    def run_fsm(self):
        """Finite State Machine (FSM) Lifecycle execution loop."""
        self.set_state("WAIT_WAKE_WORD")
        self.speech.speak("VisionVoice powered on and ready. Say Hey VisionVoice or press the main button to begin.")

        while self.running:
            try:
                if self.state == "WAIT_WAKE_WORD":
                    self._handle_wait_wake_word()

                elif self.state == "ASK_PREFERENCES":
                    self._handle_ask_preferences()

                elif self.state == "WAIT_START_READING":
                    self._handle_wait_start_reading()

                elif self.state == "ALIGNING_PAGE":
                    self._handle_aligning_page()

                elif self.state == "PROCESSING_PAGE":
                    self._handle_processing_page()

                elif self.state == "READING":
                    self._handle_reading_loop()

                elif self.state == "PAGE_FINISHED":
                    self._handle_page_finished()

                time.sleep(0.05)

            except Exception as e:
                logger.error(f"Unexpected exception in state '{self.state}': {e}", exc_info=True)
                if hasattr(self, "buttons") and self.buttons:
                    self.buttons.indicate_state("ERROR")
                self.speech.speak("A system error occurred. Returning to standby.")
                self.set_state("WAIT_START_READING")
                time.sleep(0.5)

    # --- FSM State Handlers ---

    def _handle_wait_wake_word(self):
        """
        State: WAIT_WAKE_WORD
        Entry: Boot or idle return.
        Exit: Spoken wake phrase ('Hey VisionVoice'), 'Start reading' command, or Main button press.
        Timeout: Indefinite standby by design; responsive to shutdown signals.
        """
        time.sleep(0.3)

    def _handle_ask_preferences(self):
        """
        State: ASK_PREFERENCES
        Entry: Wake phrase recognized.
        Exit: Preferences configured; transitions to WAIT_START_READING.
        Timeout: PROMPT_LISTEN_TIMEOUT_SEC per question; defaults gracefully on timeout.
        """
        logger.info("Executing ASK_PREFERENCES flow...")
        self.buttons.indicate_state("LISTENING")

        timeout_sec = getattr(config, "PROMPT_LISTEN_TIMEOUT_SEC", 7.0)

        # 1. Ask Preferred Reading Language
        self.speech.speak("Please tell me your preferred reading language. Options are English, Tamil, Kannada, Telugu, Malayalam, or Hindi.")
        response = self.voice.listen_for_phrase(timeout=timeout_sec)

        chosen_lang = self.voice.parse_language_choice(response)
        if chosen_lang:
            self.preferred_lang = chosen_lang
            lang_name = config.SUPPORTED_LANGUAGES[chosen_lang]["name"]
            self.speech.speak(f"Language set to {lang_name}.")
        else:
            lang_name = config.SUPPORTED_LANGUAGES.get(self.preferred_lang, {}).get("name", "English")
            self.speech.speak(f"Language defaulting to {lang_name}.")

        # 2. Ask Original vs Preferred Reading Mode
        self.speech.speak("Would you like content read in the original language of the book, or translated to your preferred language?")
        response = self.voice.listen_for_phrase(timeout=timeout_sec)

        chosen_mode = self.voice.parse_mode_choice(response)
        if chosen_mode:
            self.reading_mode = chosen_mode
            mode_desc = "original language" if chosen_mode == config.READING_MODE_ORIGINAL else "preferred language translation"
            self.speech.speak(f"Reading mode set to {mode_desc}.")
        else:
            self.reading_mode = config.READING_MODE_PREFERRED
            self.speech.speak("Reading mode defaulting to preferred language.")

        # Save preferences to persistent memory
        self.memory.preferred_language = self.preferred_lang
        self.memory.reading_mode = self.reading_mode
        self.memory.save_session()

        self.set_state("WAIT_START_READING")

    def _handle_wait_start_reading(self):
        """
        State: WAIT_START_READING
        Entry: Preferences configured or error recovery.
        Exit: Spoken 'Start reading' command or physical Main button press.
        Timeout: Controlled standby loop.
        """
        if not self.prompted_start_reading:
            self.speech.speak("Please place your book under the camera and say Start reading or press the main button.")
            self.prompted_start_reading = True
            self.buttons.set_led(True)

        time.sleep(0.3)

    def _handle_aligning_page(self):
        """
        State: ALIGNING_PAGE
        Entry: Start reading command or page turn completed.
        Exit: Page aligned and stable -> PROCESSING_PAGE.
        Timeout: ALIGNMENT_TIMEOUT_SEC -> speaks guidance and transitions to WAIT_START_READING.
        Error Path: MAX_CAMERA_READ_RETRIES exceeded -> speaks error and transitions to WAIT_START_READING.
        """
        logger.info("Executing ALIGNING_PAGE real-time alignment...")
        self.buttons.start_led_blink(0.2)
        self.alignment.reset()

        start_time = time.time()
        alignment_timeout = getattr(config, "ALIGNMENT_TIMEOUT_SEC", 30.0)
        max_camera_retries = getattr(config, "MAX_CAMERA_READ_RETRIES", 10)
        consecutive_read_errors = 0
        aligned_and_ready = False

        while self.running and self.state == "ALIGNING_PAGE" and not aligned_and_ready:
            # 1. Timeout Guard
            if (time.time() - start_time) > alignment_timeout:
                logger.info(f"Alignment timed out after {alignment_timeout}s without stable page detection.")
                self.speech.speak("Alignment timed out. Place your book and say Start reading or press the main button.")
                self.set_state("WAIT_START_READING")
                return

            # 2. Camera Frame Acquisition Guard
            frame = self.camera.capture_frame()
            if frame is None:
                consecutive_read_errors += 1
                if consecutive_read_errors >= max_camera_retries:
                    logger.error(f"Camera frame acquisition error threshold ({max_camera_retries}) exceeded.")
                    self.speech.speak("Camera error. Please verify camera connection.")
                    self.set_state("WAIT_START_READING")
                    return
                time.sleep(0.1)
                continue

            consecutive_read_errors = 0

            # 3. Analyze Page Alignment
            analysis = self.alignment.analyze_frame(frame)

            # Spoken directional voice guidance if out of position
            if analysis["guidance"]:
                logger.info(f"Guidance prompt: {analysis['guidance']}")
                self.speech.speak(analysis["guidance"], blocking=False)

            if analysis["ready_for_capture"]:
                logger.info("Page is properly aligned and stable! Auto-capture triggered.")
                aligned_and_ready = True
                self.buttons.set_led(True)
                self.speech.speak("Page aligned.", blocking=False)
                break

            time.sleep(1.0 / config.CAMERA_FPS)

        if aligned_and_ready:
            self.set_state("PROCESSING_PAGE")

    def _handle_processing_page(self):
        """
        State: PROCESSING_PAGE
        Entry: Automatic high-res capture triggered.
        Exit: Clean text extracted, language identified, translation ready -> READING.
        Retry/Error Path:
          - If OCR text is empty/illegible: Retries up to MAX_OCR_RETRIES before reverting to WAIT_START_READING.
          - If capture/CV fails: Reverts to WAIT_START_READING.
        """
        logger.info("Executing PROCESSING_PAGE pipeline...")
        self.buttons.start_led_blink(0.1)

        # 1. High-Resolution Image Capture
        high_res_frame = self.camera.capture_page()
        if high_res_frame is None:
            logger.error("High-resolution camera capture returned None.")
            self.speech.speak("Camera capture failed. Returning to standby.")
            self.set_state("WAIT_START_READING")
            return

        # 2. Computer Vision Pipeline (4-corner detection, perspective unwarp, contrast enhancement)
        try:
            processed = self.processor.process_captured_page(high_res_frame)
        except Exception as e:
            logger.error(f"CV perspective rectification pipeline error: {e}", exc_info=True)
            self.speech.speak("Image processing failed. Please adjust book page.")
            self.set_state("WAIT_START_READING")
            return

        # 3. Multilingual Tesseract OCR Extraction
        ocr_result = self.ocr.extract_text(processed["enhanced"], target_lang=self.preferred_lang)
        max_ocr_retries = getattr(config, "MAX_OCR_RETRIES", 3)

        if not ocr_result.get("text") or not ocr_result.get("sentences"):
            self.ocr_retry_count += 1
            logger.warning(f"OCR extracted no legible text (Attempt {self.ocr_retry_count}/{max_ocr_retries}).")

            if self.ocr_retry_count < max_ocr_retries:
                self.speech.speak("Could not extract legible text. Please align the page and try again.")
                self.set_state("ALIGNING_PAGE")
            else:
                self.ocr_retry_count = 0
                logger.error("OCR maximum retry limit reached.")
                self.speech.speak("Unable to read page after multiple attempts. Returning to standby. Please ensure adequate lighting.")
                self.set_state("WAIT_START_READING")
            return

        # Reset retry counter upon successful OCR extraction
        self.ocr_retry_count = 0

        # 4. Language Detection
        detected = self.lang_detector.detect_language(ocr_result["text"])
        self.current_book_lang = detected["lang"]
        logger.info(f"Book page language detected: {detected['name']} ({detected['lang']})")

        # 5. Book Identification & Reading Memory (Secondary feature - graceful degradation)
        start_sentence_idx = 0
        try:
            self.memory.record_processed_page(self.memory.current_page_num, processed.get("saved_path"))
            book_info = self.memory.identify_or_create_book(ocr_result["text"], detected_lang=detected["lang"])
            if book_info and isinstance(book_info, dict):
                if book_info.get("is_new_book"):
                    self.speech.speak("New book detected. Starting from beginning.")
                elif book_info.get("book_id"):
                    self.speech.speak(f"Recognized previously read book. Continuing from page {book_info.get('last_page', 1)}.")
                start_sentence_idx = book_info.get("last_sentence_idx", 0)
        except Exception as mem_err:
            logger.warning(f"Book memory identification encountered an issue ({mem_err}). Gracefully continuing reading pipeline.")
            start_sentence_idx = 0

        # 6. Reading Mode & Translation Determination
        if self.reading_mode == config.READING_MODE_ORIGINAL or detected["lang"] == self.preferred_lang:
            logger.info(f"Original mode active or matching language ('{detected['lang']}'). No translation requested.")
            self.current_sentences = list(ocr_result["sentences"])
            self.active_reading_lang = detected["lang"]
        else:
            logger.info(f"Translation mode active: translating '{detected['lang']}' -> '{self.preferred_lang}'")
            self.current_sentences = self.translator.translate_sentences(
                ocr_result["sentences"],
                source_lang=detected["lang"],
                target_lang=self.preferred_lang,
                mode=self.reading_mode
            )
            self.active_reading_lang = self.preferred_lang

        self.current_sentence_index = start_sentence_idx

        # Bounds validation for saved sentence progress
        if self.current_sentence_index >= len(self.current_sentences):
            self.current_sentence_index = 0

        self.set_state("READING")

    def _handle_reading_loop(self):
        """
        State: READING
        Entry: Sentences extracted and translated (or original).
        Exit: End of sentences reached -> PAGE_FINISHED; or paused/stopped by user.
        """
        logger.info("Executing READING state loop...")
        self.buttons.set_led(True)
        self.reading_active = True
        self.pause_requested = False

        reading_lang = getattr(self, "active_reading_lang", None)
        if not reading_lang:
            reading_lang = self.preferred_lang if self.reading_mode == config.READING_MODE_PREFERRED else getattr(self, "current_book_lang", config.DEFAULT_LANGUAGE)

        while self.running and self.state == "READING" and self.reading_active:
            if self.pause_requested:
                time.sleep(0.2)
                continue

            if self.current_sentence_idx >= len(self.current_sentences):
                logger.info("Completed reading all sentences on current page.")
                self.set_state("PAGE_FINISHED")
                break

            sentence = self.current_sentences[self.current_sentence_idx]
            logger.info(f"Reading sentence [{self.current_sentence_idx + 1}/{len(self.current_sentences)}]: '{sentence}'")

            # Speak sentence (blocks until playback finishes or is interrupted)
            self.speech.speak(sentence, lang=reading_lang, blocking=True)

            # Check if stop or pause was requested during playback
            if not self.reading_active or self.state != "READING":
                break

            # Update persistent progress after sentence completion
            self.current_sentence_idx += 1
            self.memory.update_progress(self.memory.current_page_num, self.current_sentence_idx)

    def _handle_page_finished(self):
        """
        State: PAGE_FINISHED
        Entry: Completed reading current page.
        Exit: Next page alignment started -> ALIGNING_PAGE.
        """
        logger.info("Executing PAGE_FINISHED state...")
        self.speech.speak("Finished reading. Please turn to the next page.")

        # Update page count in memory
        self.memory.current_page_num += 1
        self.memory.current_sentence_idx = 0
        self.memory.update_progress(self.memory.current_page_num, 0)
        self.ocr_retry_count = 0

        # Wait briefly for physical page turn before starting next alignment
        time.sleep(2.0)
        self.set_state("ALIGNING_PAGE")

    # --- Voice & Hardware Callback Handlers ---

    def on_voice_command(self, command_type):
        """Dispatches recognized voice commands dynamically."""
        logger.info(f"Voice Command Received: '{command_type}' (Current state: '{self.state}')")

        if command_type == "wake_word":
            if self.state == "WAIT_WAKE_WORD":
                self.speech.speak("Yes, VisionVoice here.")
                self.set_state("ASK_PREFERENCES")
            else:
                self.speech.speak("VisionVoice active.")

        elif command_type == "start_reading":
            if self.state in ["WAIT_START_READING", "WAIT_WAKE_WORD"]:
                self.speech.speak("Starting alignment and scanning.")
                self.set_state("ALIGNING_PAGE")

        elif command_type == "stop_reading":
            if self.state == "READING":
                self.reading_active = False
                self.pause_requested = True
                self.speech.stop()
                self.speech.speak("Reading stopped. Position saved.")
                self.memory.update_progress(self.memory.current_page_num, self.current_sentence_index)

        elif command_type == "next_sentence":
            if self.state == "READING":
                self.speech.stop()
                self.current_sentence_index += 1
                logger.info(f"Advancing to next sentence index: {self.current_sentence_index}")
                if self.current_sentence_index >= len(self.current_sentences):
                    self.set_state("PAGE_FINISHED")
                else:
                    self.speech.speak("Next sentence.")

        elif command_type == "continue_reading":
            if self.pause_requested or self.state != "READING":
                self.pause_requested = False
                self.reading_active = True
                self.set_state("READING")
                self.speech.speak("Resuming reading.")

        elif command_type in ["repeat", "repeat_sentence"]:
            if self.state == "READING":
                self.speech.stop()
                self.current_sentence_index = max(0, self.current_sentence_index - 1)
                self.speech.speak("Repeating sentence.")

        elif command_type == "repeat_beginning":
            if self.state == "READING" or self.memory.current_book_id:
                self.speech.stop()
                self.memory.reset_book_progress(self.memory.current_book_id)
                self.current_sentence_index = 0
                self.speech.speak("Restarting book from beginning.")
                self.set_state("READING")

        elif command_type == "vol_up":
            self.speech.increase_volume()

        elif command_type == "vol_down":
            self.speech.decrease_volume()

    def on_main_button(self):
        """
        Callback for physical Main/Interaction button press (GPIO17).
        Acts as universal action button: start scanning / pause / resume / next page.
        """
        logger.info(f"Main button (GPIO17) pressed in state: '{self.state}'")
        if self.state in ["WAIT_WAKE_WORD", "WAIT_START_READING"]:
            self.speech.speak("Starting scanning.")
            self.set_state("ALIGNING_PAGE")
        elif self.state == "READING":
            if self.reading_active and not self.pause_requested:
                self.reading_active = False
                self.pause_requested = True
                self.speech.stop()
                self.speech.speak("Paused.")
                self.memory.update_progress(self.memory.current_page_num, self.current_sentence_idx)
            else:
                self.pause_requested = False
                self.reading_active = True
                self.speech.speak("Resumed.")
        elif self.state == "PAGE_FINISHED":
            self.speech.speak("Scanning next page.")
            self.set_state("ALIGNING_PAGE")
        elif self.state == "ALIGNING_PAGE":
            self.speech.speak("Scanning now.", blocking=False)
            self.set_state("PROCESSING_PAGE")

    def on_power_button(self):
        """Callback for physical power button press (long press on GPIO17)."""
        logger.info("Power button triggered shutdown sequence.")
        self.speech.speak("VisionVoice powering off. Goodbye.")
        self.stop()

    def on_volume_up_button(self):
        """Callback for physical Volume Up button press (GPIO27)."""
        self.speech.increase_volume()

    def on_volume_down_button(self):
        """Callback for physical Volume Down button press (GPIO22)."""
        self.speech.decrease_volume()

    def stop(self):
        """
        Gracefully shuts down all hardware and software background services.
        Guarantees that camera, GPIO pins, and audio devices are never left locked.
        """
        logger.info("Graceful shutdown sequence initiated...")
        self.running = False
        self.reading_active = False

        # 1. Save Reading Progress to Memory
        if hasattr(self, "memory") and self.memory:
            try:
                self.memory.update_progress(self.memory.current_page_num, self.current_sentence_idx)
                self.memory.save_session()
                logger.info(f"Reading session saved at page {self.memory.current_page_num}, sentence {self.current_sentence_idx}.")
            except Exception as e:
                logger.warning(f"Error saving progress during shutdown: {e}")

        # 2. Stop TTS Audio Playback & Subprocesses (Releases ALSA plughw:3,0)
        if hasattr(self, "speech") and self.speech:
            try:
                self.speech.stop()
                logger.info("TTS audio playback terminated and sound endpoints released.")
            except Exception as e:
                logger.debug(f"Speech shutdown note: {e}")

        # 3. Stop Microphone & Speech Recognition Background Listener
        if hasattr(self, "voice") and self.voice:
            try:
                self.voice.stop()
                logger.info("Voice recognition listener stopped and microphone released.")
            except Exception as e:
                logger.debug(f"Voice shutdown note: {e}")

        # 4. Stop Camera Hardware & Frame Buffer Worker (Releases /dev/video* & V4L2)
        if hasattr(self, "camera") and self.camera:
            try:
                self.camera.release()
                logger.info("Camera capture hardware released.")
            except Exception as e:
                logger.debug(f"Camera shutdown note: {e}")

        # 5. Turn off Status LED & Cleanup GPIO Interrupts
        if hasattr(self, "buttons") and self.buttons:
            try:
                self.buttons.cleanup()
                logger.info("Status LED turned off and GPIO pins cleaned up.")
            except Exception as e:
                logger.debug(f"Buttons shutdown note: {e}")

        logger.info("VisionVoice shutdown complete. All hardware resources cleanly released.")

    def signal_handler(self, sig, frame):
        """Signal handler for system termination signals (SIGINT / SIGTERM)."""
        sig_name = sig
        try:
            sig_name = signal.Signals(sig).name
        except Exception:
            pass
        logger.info(f"System signal {sig} ({sig_name}) received. Executing graceful shutdown...")
        self.stop()
        sys.exit(0)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ["--dashboard", "--web", "-d", "-w"]:
        import dashboard
        dashboard.main()
    elif len(sys.argv) > 1 and sys.argv[1] in ["--gui", "-g", "--ui"]:
        from gui_app import main as run_gui
        run_gui()
    elif len(sys.argv) > 1 and sys.argv[1] in ["--test", "--test-hardware", "-t"]:
        from hardware_test import run_hardware_diagnostics
        run_hardware_diagnostics()
    else:
        app = VisionVoiceApp()
        app.start()

