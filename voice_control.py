import time
import threading
import logging
import config

logger = logging.getLogger("VisionVoice.VoiceControl")

class VoiceController:
    """
    Speech Recognition & Voice Command Controller for VisionVoice.
    Configured for the USB PnP Sound Device: Audio (hw:3,0) at device_index=2.

    CRITICAL HARDWARE THREAD SAFETY:
    Enforces strict single-owner serialized access to the physical microphone hardware.
    Background wake-word / command listening and synchronous phrase prompts
    never compete for or open simultaneous streams on the microphone.
    """

    def __init__(self, callback_handler=None):
        self.callback_handler = callback_handler
        self.running = False
        self.pause_background = False
        self.recognizer = None
        self.microphone = None
        self.listen_thread = None
        self.mic_lock = threading.Lock()

        self._init_speech_recognition()

    def _init_speech_recognition(self):
        """Initializes SpeechRecognition with serialized USB PnP Sound Device (index 2)."""
        try:
            import speech_recognition as sr
            self.sr = sr
            self.recognizer = sr.Recognizer()
            self.recognizer.energy_threshold = 300
            self.recognizer.dynamic_energy_threshold = True
            self.recognizer.pause_threshold = 0.8

            target_idx = getattr(config, "MIC_DEVICE_INDEX", 2)

            # Detect available devices and initialize sr.Microphone(device_index=2)
            try:
                mics = sr.Microphone.list_microphone_names()
                logger.info(f"Available audio input devices: {mics}")

                if target_idx < len(mics):
                    self.microphone = sr.Microphone(device_index=target_idx)
                    logger.info(f"Configured USB Microphone at device_index={target_idx}: '{mics[target_idx]}'")
                else:
                    # Fallback for dev environments with fewer audio devices
                    matched_idx = None
                    for idx, name in enumerate(mics):
                        if "USB" in name or "PnP" in name or "Headset" in name or "Headphone" in name:
                            matched_idx = idx
                            break
                    if matched_idx is not None:
                        self.microphone = sr.Microphone(device_index=matched_idx)
                        logger.info(f"Configured USB Microphone at matched index {matched_idx}: '{mics[matched_idx]}'")
                    else:
                        self.microphone = sr.Microphone()
                        logger.info("Configured default system microphone.")
            except Exception as ex:
                logger.warning(f"Microphone list query exception ({ex}). Initializing sr.Microphone(device_index={target_idx})")
                self.microphone = sr.Microphone(device_index=target_idx)

            # Perform initial ambient noise calibration with exclusive lock
            try:
                with self.mic_lock:
                    with self.microphone as source:
                        logger.info("Calibrating microphone ambient noise baseline...")
                        self.recognizer.adjust_for_ambient_noise(source, duration=0.8)
                        logger.info(f"Calibrated dynamic energy threshold to {self.recognizer.energy_threshold}")
            except Exception as ce:
                logger.warning(f"Ambient noise calibration note: {ce}")

            logger.info("Speech Recognition initialized successfully.")
        except Exception as e:
            logger.warning(f"SpeechRecognition initialization warning ({e}). Fallback active.")
            self.recognizer = None
            self.microphone = None

    def start_listening(self):
        """Starts background microphone listening thread."""
        if self.running:
            return
        self.running = True
        self.pause_background = False
        self.listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.listen_thread.start()
        logger.info("Voice controller serialized background listening thread started.")

    def _listen_loop(self):
        """
        Continuous background listening loop.
        Acquires self.mic_lock on each cycle to guarantee single-owner microphone access.
        """
        while self.running:
            if self.pause_background or not self.recognizer or not self.microphone:
                time.sleep(0.1)
                continue

            acquired = self.mic_lock.acquire(timeout=0.2)
            if not acquired:
                time.sleep(0.05)
                continue

            try:
                if not self.running or self.pause_background:
                    continue

                audio = None
                try:
                    with self.microphone as source:
                        audio = self.recognizer.listen(source, timeout=1.5, phrase_time_limit=3.5)
                except Exception:
                    # Normal listen window timeout when no speech is detected
                    audio = None

                if audio is not None and not self.pause_background:
                    # Check RMS audio energy to avoid making recognition requests on ambient silence
                    if not self._has_speech_energy(audio):
                        continue

                    text = self._recognize_audio(audio)
                    if text:
                        logger.info(f"Recognized voice phrase: '{text}'")
                        self._process_phrase(text)

            except Exception as e:
                logger.debug(f"Background listen cycle error: {e}")
            finally:
                self.mic_lock.release()
                time.sleep(0.05)

    def _has_speech_energy(self, audio_data, threshold=350):
        """
        Pure Python RMS energy check on raw 16-bit PCM audio.
        Returns False for ambient room silence, preventing wasteful API requests.
        """
        try:
            raw = audio_data.get_raw_data()
            if not raw:
                return False
            count = len(raw) // 2
            if count == 0:
                return False
            import struct
            # Subsample frames for ultra-fast calculation
            step = 4
            shorts = struct.unpack(f"{count}h", raw)
            sample_shorts = shorts[::step]
            sum_squares = sum(s * s for s in sample_shorts)
            rms = (sum_squares / len(sample_shorts)) ** 0.5
            return rms > threshold
        except Exception:
            return True

    def _recognize_audio(self, audio_data):
        """
        Offline-first speech recognition with graceful cloud fallback.
        1. Attempts local offline recognizer (Sphinx) if available.
        2. Fallback to Google Speech Recognition only when speech energy is present.
        """
        # 1. Try offline Sphinx recognizer
        try:
            text = str(self.recognizer.recognize_sphinx(audio_data)).lower().strip()
            if text:
                return text
        except Exception:
            pass

        # 2. Fallback to Google Speech Recognition
        try:
            text = str(self.recognizer.recognize_google(audio_data)).lower().strip()
            if text:
                return text
        except Exception:
            pass

        return ""

    def listen_for_phrase(self, timeout=8.0, phrase_time_limit=5.0):
        """
        Listens synchronously for a single phrase (e.g. during language/mode setup prompts).
        Exclusively takes ownership of the microphone, pausing background listener.

        Returns:
            str: lowercased recognized text, or "" if timed out or failed.
        """
        if not self.recognizer or not self.microphone:
            return ""

        logger.info("Pausing background listener and acquiring exclusive microphone lock...")
        self.pause_background = True

        with self.mic_lock:
            try:
                with self.microphone as source:
                    logger.info("Listening for prompt response...")
                    audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)

                text = self._recognize_audio(audio)
                logger.info(f"Captured prompt response: '{text}'")
                return text
            except Exception as e:
                logger.debug(f"Phrase capture timeout/error: {e}")
                return ""
            finally:
                self.pause_background = False
                logger.info("Exclusive microphone lock released. Background listener resumed.")

    def _process_phrase(self, phrase):
        """Matches recognized speech phrase to system commands and invokes callbacks."""
        if not phrase:
            return

        command_type = self.parse_command(phrase)
        if command_type and self.callback_handler:
            logger.info(f"Dispatching voice command: '{command_type}'")
            self.callback_handler(command_type)

    def parse_command(self, phrase):
        """
        Parses a speech phrase string and categorizes it into a standard VisionVoice command.

        Returns:
            str or None: 'wake_word', 'start_reading', 'stop_reading', 'repeat',
                         'repeat_beginning', 'continue_reading', 'vol_up', 'vol_down'.
        """
        phrase = phrase.lower().strip()

        # Check wake word
        for kw in config.WAKE_WORD_PHRASES:
            if kw in phrase:
                return "wake_word"

        # Check Repeat from Beginning (before Repeat)
        for kw in config.CMD_REPEAT_FROM_BEGINNING:
            if kw in phrase:
                return "repeat_beginning"

        # Check Stop Reading (before Start Reading)
        for kw in config.CMD_STOP_READING:
            if kw in phrase:
                return "stop_reading"

        # Check Next Sentence
        for kw in getattr(config, "CMD_NEXT_SENTENCE", ["next sentence", "next"]):
            if kw in phrase:
                return "next_sentence"

        # Check Continue Reading
        for kw in config.CMD_CONTINUE_READING:
            if kw in phrase:
                return "continue_reading"

        # Check Start Reading
        for kw in config.CMD_START_READING:
            if kw in phrase:
                return "start_reading"

        # Check Repeat
        for kw in config.CMD_REPEAT:
            if kw in phrase:
                return "repeat"

        # Check Increase Volume
        for kw in config.CMD_INCREASE_VOLUME:
            if kw in phrase:
                return "vol_up"

        # Check Decrease Volume
        for kw in config.CMD_DECREASE_VOLUME:
            if kw in phrase:
                return "vol_down"

        return None

    def parse_language_choice(self, phrase):
        """
        Parses user's spoken response for language selection.

        Returns:
            str or None: language code ('en', 'ta', 'kn', 'te', 'ml', 'hi')
        """
        phrase = phrase.lower()
        for code, info in config.SUPPORTED_LANGUAGES.items():
            for kw in info["keywords"]:
                if kw in phrase or info["name"].lower() in phrase:
                    return code
        return None

    def parse_mode_choice(self, phrase):
        """
        Parses user's spoken response for reading mode ('original' vs 'preferred').

        Returns:
            str or None: 'original' or 'preferred'
        """
        phrase = phrase.lower()
        if "original" in phrase or "same" in phrase or "book language" in phrase:
            return config.READING_MODE_ORIGINAL
        elif "preferred" in phrase or "translate" in phrase or "my language" in phrase:
            return config.READING_MODE_PREFERRED
        return None

    def stop(self):
        """Stops voice listening thread, terminates microphone capture, and releases locks."""
        self.running = False
        self.pause_background = True
        if self.listen_thread and self.listen_thread.is_alive():
            try:
                self.listen_thread.join(timeout=1.0)
            except Exception:
                pass
        self.listen_thread = None
        logger.info("Voice controller stopped and microphone resources released.")
