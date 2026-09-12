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
    Renders spoken output across English, Tamil, Kannada, Telugu, Malayalam, and Hindi.
    """

    def __init__(self):
        self.volume = getattr(config, "DEFAULT_VOLUME", 80)
        self.is_speaking = False
        self.stop_requested = False
        self.pause_requested = False
        self.speech_queue = queue.Queue()
        self.current_process = None
        self.lock = threading.Lock()

        self._check_audio_tools()
        self.set_volume(self.volume)

    def _check_audio_tools(self):
        """Detects available audio player tools on the host system."""
        self.player_cmd = None
        for cmd in ["afplay", "aplay", "mpg123", "paplay", "ffplay"]:
            try:
                res = subprocess.run(["which", cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if res.returncode == 0:
                    self.player_cmd = cmd
                    logger.info(f"Audio player detected: '{cmd}'")
                    break
            except Exception:
                pass

    def speak(self, text, lang="en", blocking=True):
        """
        Synthesizes and speaks a prompt or message.
        Blocks until speech playback is complete if blocking=True.
        """
        if not text or not str(text).strip():
            return

        text = str(text).strip()
        self.stop()

        if blocking:
            self._generate_and_play(text, lang)
        else:
            t = threading.Thread(target=self._generate_and_play, args=(text, lang), daemon=True)
            t.start()

    def speak_async(self, text, lang="en"):
        """Non-blocking helper to speak a prompt in a background thread."""
        self.speak(text, lang=lang, blocking=False)

    def _generate_and_play(self, text, lang):
        """Generates speech WAV/MP3 file and plays it through available player."""
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
                logger.debug("TTS generation completed.")
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
        Generates a temporary audio file using gTTS, macOS say, eSpeak, or pyttsx3.
        """
        tts_lang = config.SUPPORTED_LANGUAGES.get(lang, {}).get("tts", lang)

        # 1. macOS native 'say' engine fallback
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

        # 2. gTTS (Google TTS)
        try:
            from gtts import gTTS
            tmp_mp3 = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            tmp_mp3.close()
            tts = gTTS(text=text, lang=tts_lang, slow=False)
            tts.save(tmp_mp3.name)

            # If player supports mp3 directly (afplay, mpg123, ffplay)
            if self.player_cmd in ["afplay", "mpg123", "ffplay", "paplay"]:
                return tmp_mp3.name

            # Otherwise convert to WAV
            tmp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp_wav.close()

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

        # 3. eSpeak-ng / eSpeak
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
            except Exception:
                pass

        return None

    def _play_wav(self, audio_file):
        """Executes audio playback through available system audio player."""
        if self.stop_requested or not self.player_cmd:
            return

        cmd = [self.player_cmd, audio_file]

        try:
            self.current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            play_start_time = time.time()
            max_timeout = getattr(config, "MAX_TTS_PLAYBACK_TIMEOUT_SEC", 60.0)

            while self.current_process and self.current_process.poll() is None:
                if self.stop_requested:
                    self.current_process.terminate()
                    try:
                        self.current_process.wait(timeout=0.5)
                    except subprocess.TimeoutExpired:
                        self.current_process.kill()
                    break

                if (time.time() - play_start_time) > max_timeout:
                    self.current_process.terminate()
                    try:
                        self.current_process.wait(timeout=0.5)
                    except subprocess.TimeoutExpired:
                        self.current_process.kill()
                    break

                time.sleep(0.02)

        except Exception as e:
            logger.error(f"Audio playback failed: {e}", exc_info=True)
        finally:
            self.current_process = None

    def stop(self):
        """Immediately interrupts active speech playback."""
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
        with self.lock:
            self.pause_requested = True

    def resume(self):
        with self.lock:
            self.pause_requested = False

    def set_volume(self, level):
        self.volume = max(0, min(100, level))

    def increase_volume(self):
        self.volume = min(100, self.volume + getattr(config, "VOLUME_STEP", 10))
        return self.volume

    def decrease_volume(self):
        self.volume = max(0, self.volume - getattr(config, "VOLUME_STEP", 10))
        return self.volume
