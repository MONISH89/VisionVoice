import os
import ssl
import time
import queue
import threading
import subprocess
import logging
import tempfile

try:
    import certifi
    os.environ['SSL_CERT_FILE'] = certifi.where()
    os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
except Exception:
    pass

try:
    ssl._create_default_https_context = ssl._create_unverified_context
except Exception:
    pass

import config

logger = logging.getLogger("VisionVoice.Speech")

class SpeechEngine:
    """
    Text-to-Speech (TTS) Engine and Audio Output Controller for VisionVoice.
    Renders spoken output for user interaction, guidance, and book reading
    across English, Tamil, Kannada, Telugu, Malayalam, and Hindi.

    CRITICAL AUDIO HARDWARE CONFIGURATION:
    All speech output routes explicitly through ALSA 'plughw:3,0' (USB PnP Sound Device).
    Never routes to default ALSA, PulseAudio default, or HDMI.
    """

    def __init__(self):
        self.volume = config.DEFAULT_VOLUME
        self.is_speaking = False
        self.stop_requested = False
        self.pause_requested = False
        self.speech_queue = queue.Queue()
        self.current_process = None
        self.lock = threading.Lock()

        self._check_audio_tools()
        self.set_volume(self.volume)

    def _check_audio_tools(self):
        """Detects available audio tools on the host system."""
        self.has_aplay = False
        self.player_cmd = None

        try:
            res = subprocess.run(["which", "aplay"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if res.returncode == 0:
                self.has_aplay = True
                self.player_cmd = "aplay"
                logger.info(f"ALSA aplay detected. Output target: '{config.ALSA_PLAYBACK_DEVICE}'")
                return
        except Exception:
            pass

        # Fallback detection for desktop development testing
        for cmd in ["afplay", "mpg123", "paplay"]:
            try:
                res = subprocess.run(["which", cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if res.returncode == 0:
                    self.player_cmd = cmd
                    logger.info(f"Development audio player fallback: '{cmd}'")
                    break
            except Exception:
                pass

    def speak(self, text, lang="en", blocking=True):
        """
        Synthesizes and speaks a prompt or message.
        Blocks until speech playback is complete if blocking=True.

        Args:
            text (str): Prompt or message to speak.
            lang (str): Language code ('en', 'ta', 'kn', 'te', 'ml', 'hi').
            blocking (bool): If True, waits until speech completes before returning.
        """
        if not text or not str(text).strip():
            return

        text = str(text).strip()
        self.stop()  # Clear any active audio before starting new prompt

        if blocking:
            self._generate_and_play(text, lang)
        else:
            t = threading.Thread(target=self._generate_and_play, args=(text, lang), daemon=True)
            t.start()

    def speak_async(self, text, lang="en"):
        """Non-blocking helper to speak a prompt in a background thread."""
        self.speak(text, lang=lang, blocking=False)

    def _generate_and_play(self, text, lang):
        """Generates speech WAV file and plays it through ALSA plughw:3,0."""
        with self.lock:
            self.stop_requested = False
            self.is_speaking = True

        wav_file = None
        try:
            logger.info("TTS: generating speech")
            wav_file = self._generate_speech_wav(text, lang)
            if wav_file and os.path.exists(wav_file) and os.path.getsize(wav_file) > 44:
                self._play_wav(wav_file)
            else:
                logger.error("TTS generation failed to produce a valid WAV audio file.")
        except Exception as e:
            logger.error(f"TTS error during generation or playback: {e}", exc_info=True)
        finally:
            if wav_file and os.path.exists(wav_file):
                try:
                    os.remove(wav_file)
                except Exception:
                    pass
            with self.lock:
                self.is_speaking = False

    def _generate_speech_wav(self, text, lang):
        """
        Generates a temporary WAV file using eSpeak-ng, eSpeak, gTTS, or pyttsx3.
        Returns:
            str: Path to generated .wav file, or None if failed.
        """
        tts_lang = config.SUPPORTED_LANGUAGES.get(lang, {}).get("tts", lang)

        # 1. Primary Offline Engine: eSpeak-ng / eSpeak (WAV output directly)
        for espeak_bin in ["espeak-ng", "espeak"]:
            try:
                res = subprocess.run(["which", espeak_bin], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if res.returncode == 0:
                    tmp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                    tmp_wav.close()
                    cmd = [espeak_bin, "-v", tts_lang, "-w", tmp_wav.name, text]
                    sub_res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10.0)
                    if sub_res.returncode == 0 and os.path.exists(tmp_wav.name) and os.path.getsize(tmp_wav.name) > 44:
                        return tmp_wav.name
            except Exception as e:
                logger.debug(f"{espeak_bin} attempt failed: {e}")

        # 2. Secondary Engine: gTTS (Google TTS) + MP3 to WAV conversion
        try:
            from gtts import gTTS
            tmp_mp3 = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            tmp_mp3.close()
            tts = gTTS(text=text, lang=tts_lang, slow=False)
            tts.save(tmp_mp3.name)

            tmp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp_wav.close()

            # Convert MP3 to WAV using afconvert (macOS), mpg123, ffmpeg, or sox
            converted = False
            for conv_cmd in [
                ["afconvert", "-f", "WAVE", "-d", "LEI16@22050", tmp_mp3.name, tmp_wav.name],
                ["mpg123", "-w", tmp_wav.name, tmp_mp3.name],
                ["ffmpeg", "-y", "-i", tmp_mp3.name, tmp_wav.name],
                ["sox", tmp_mp3.name, tmp_wav.name]
            ]:
                try:
                    c_res = subprocess.run(conv_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5.0)
                    if c_res.returncode == 0 and os.path.exists(tmp_wav.name) and os.path.getsize(tmp_wav.name) > 44:
                        converted = True
                        break
                except Exception:
                    pass

            try:
                os.remove(tmp_mp3.name)
            except Exception:
                pass

            if converted:
                return tmp_wav.name
        except Exception as e:
            logger.debug(f"gTTS conversion attempt failed: {e}")

        # 3. macOS native 'say' engine fallback
        try:
            res = subprocess.run(["which", "say"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if res.returncode == 0:
                tmp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                tmp_wav.close()
                cmd = ["say", "-o", tmp_wav.name, "--data-format=LEI16@22050", text]
                sub_res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10.0)
                if sub_res.returncode == 0 and os.path.exists(tmp_wav.name) and os.path.getsize(tmp_wav.name) > 44:
                    return tmp_wav.name
        except Exception as e:
            logger.debug(f"macOS say attempt failed: {e}")

        # 4. Tertiary Engine: pyttsx3 fallback
        try:
            import pyttsx3
            engine = pyttsx3.init()
            tmp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp_wav.close()
            engine.save_to_file(text, tmp_wav.name)
            engine.runAndWait()
            if os.path.exists(tmp_wav.name) and os.path.getsize(tmp_wav.name) > 44:
                return tmp_wav.name
        except Exception as e:
            logger.debug(f"pyttsx3 attempt failed: {e}")

        return None

    def _play_wav(self, wav_file):
        """
        Executes WAV audio playback strictly through ALSA plughw:3,0 (or host audio player fallback).
        Blocks until speech playback is completely finished.
        """
        if self.stop_requested:
            return

        logger.info(f"TTS: playing through {self.player_cmd or ('ALSA ' + config.ALSA_PLAYBACK_DEVICE)}")

        if self.has_aplay:
            cmd = ["aplay", "-D", config.ALSA_PLAYBACK_DEVICE, "-q", wav_file]
        elif self.player_cmd == "afplay":
            cmd = ["afplay", wav_file]
        else:
            cmd = ["aplay", "-D", config.ALSA_PLAYBACK_DEVICE, wav_file]

        try:
            self.current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            play_start_time = time.time()
            max_timeout = getattr(config, "MAX_TTS_PLAYBACK_TIMEOUT_SEC", 60.0)

            # Monitor process until playback finishes, stop is requested, or timeout occurs
            while self.current_process and self.current_process.poll() is None:
                if self.stop_requested:
                    logger.info("Speech stop requested. Terminating audio process.")
                    self.current_process.terminate()
                    try:
                        self.current_process.wait(timeout=0.5)
                    except subprocess.TimeoutExpired:
                        self.current_process.kill()
                    break

                if (time.time() - play_start_time) > max_timeout:
                    logger.error(f"TTS playback exceeded max timeout ({max_timeout}s). Forcibly terminating process.")
                    self.current_process.terminate()
                    try:
                        self.current_process.wait(timeout=0.5)
                    except subprocess.TimeoutExpired:
                        self.current_process.kill()
                    break

                time.sleep(0.02)

            if self.current_process and not self.stop_requested:
                _, stderr = self.current_process.communicate()
                if self.current_process.returncode != 0:
                    err_text = stderr.decode('utf-8', errors='ignore').strip()
                    logger.error(f"TTS playback process exited with error code {self.current_process.returncode}: {err_text}")
                else:
                    logger.info("TTS: playback complete")
            else:
                logger.info("TTS: playback complete")

        except Exception as e:
            logger.error(f"TTS playback failed with exception: {e}", exc_info=True)
        finally:
            self.current_process = None

    def stop(self):
        """Immediately interrupts active speech playback and releases ALSA audio endpoints."""
        with self.lock:
            self.stop_requested = True
            self.pause_requested = False
            self.is_speaking = False

        if self.current_process and self.current_process.poll() is None:
            try:
                self.current_process.terminate()
                try:
                    self.current_process.wait(timeout=0.3)
                except subprocess.TimeoutExpired:
                    self.current_process.kill()
            except Exception:
                pass
            self.current_process = None

    def pause(self):
        """Pauses speech playback."""
        with self.lock:
            self.pause_requested = True
        logger.info("Speech playback paused.")

    def resume(self):
        """Resumes speech playback."""
        with self.lock:
            self.pause_requested = False
        logger.info("Speech playback resumed.")

    def set_volume(self, level):
        """
        Sets audio output volume (0 to 100).
        Applies volume adjustment via ALSA amixer explicitly to card 3 (USB PnP Sound Device).
        """
        self.volume = max(0, min(100, level))
        logger.info(f"System volume set to {self.volume}%")

        # Configure ALSA volume for USB PnP Sound Device (Card 3)
        for control in ["Speaker", "Playback", "Master", "Headphone"]:
            try:
                subprocess.run(
                    ["amixer", "-c", str(config.ALSA_CARD_INDEX), "set", control, f"{self.volume}%"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=1.0
                )
            except Exception:
                pass

    def increase_volume(self):
        """Increases volume by VOLUME_STEP."""
        new_vol = self.volume + config.VOLUME_STEP
        self.set_volume(new_vol)
        self.speak_async(f"Volume {self.volume} percent")
        return self.volume

    def decrease_volume(self):
        """Decreases volume by VOLUME_STEP."""
        new_vol = self.volume - config.VOLUME_STEP
        self.set_volume(new_vol)
        self.speak_async(f"Volume {self.volume} percent")
        return self.volume
