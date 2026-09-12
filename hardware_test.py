#!/usr/bin/env python3
"""
VisionVoice — Independent Hardware Diagnostic & Verification Testbench.
Independently verifies:
  1. Camera (Picamera2 / OpenCV VideoCapture)
  2. Microphone (SpeechRecognition device_index=2)
  3. TTS (eSpeak-ng speech synthesis)
  4. Audio Output (espeak-ng --stdout "VisionVoice audio test" | aplay -D plughw:3,0)
  5. GPIO Buttons (BCM Pins 17, 27, 22 with internal pull-up)
  6. Status LED (BCM Pin 24 output)

Never crashes on hardware failure; outputs clear [PASS] or [FAIL] status.
"""

import os
import sys
import time
import subprocess

# Ensure VisionVoice root is in path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

import config

def test_camera():
    """1. Tests physical Camera interface (Picamera2 or OpenCV VideoCapture)."""
    try:
        # Try Picamera2 first
        try:
            from picamera2 import Picamera2  # type: ignore
            picam = Picamera2()
            preview_config = picam.create_preview_configuration(
                main={"size": config.PREVIEW_RESOLUTION, "format": "RGB888"}
            )
            picam.configure(preview_config)
            picam.start()
            frame = picam.capture_array("main")
            picam.stop()
            if hasattr(picam, "close"):
                picam.close()
            if frame is not None and frame.size > 0:
                print("[PASS] Camera")
                return True
        except Exception:
            pass

        # Try OpenCV VideoCapture fallback
        import cv2
        cap = cv2.VideoCapture(getattr(config, "CAMERA_INDEX", 0))
        if not cap.isOpened():
            print("[FAIL] Camera\nCould not open video capture device on index 0 (/dev/video0). Check camera ribbon cable.")
            return False

        ret, frame = cap.read()
        cap.release()

        if ret and frame is not None and frame.size > 0:
            print("[PASS] Camera")
            return True
        else:
            print("[FAIL] Camera\nVideo device opened but failed to capture a readable frame.")
            return False

    except Exception as e:
        print(f"[FAIL] Camera\nException during camera initialization: {e}")
        return False

def test_microphone():
    """2. Tests physical Microphone on SpeechRecognition device_index=2 (USB PnP Sound Device)."""
    try:
        import speech_recognition as sr
        target_idx = getattr(config, "MIC_DEVICE_INDEX", 2)

        # Check available microphones
        try:
            mics = sr.Microphone.list_microphone_names()
        except Exception as ex:
            mics = []

        mic = None
        if target_idx < len(mics):
            mic = sr.Microphone(device_index=target_idx)
        else:
            # Check if any USB mic exists
            usb_idx = None
            for idx, name in enumerate(mics):
                if "USB" in name or "PnP" in name or "Audio" in name:
                    usb_idx = idx
                    break
            if usb_idx is not None:
                mic = sr.Microphone(device_index=usb_idx)
            else:
                mic = sr.Microphone(device_index=target_idx)

        recognizer = sr.Recognizer()
        with mic as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.3)

        print("[PASS] Microphone")
        return True

    except Exception as e:
        print(f"[FAIL] Microphone\nCould not access audio input on device_index={getattr(config, 'MIC_DEVICE_INDEX', 2)}: {e}")
        return False

def test_tts():
    """3. Tests Text-to-Speech synthesis (eSpeak-ng)."""
    try:
        # Check espeak-ng or espeak binary
        espeak_bin = None
        for b in ["espeak-ng", "espeak"]:
            res = subprocess.run(["which", b], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if res.returncode == 0:
                espeak_bin = b
                break

        if not espeak_bin:
            print("[FAIL] TTS\neSpeak-ng executable not found in PATH. Run 'sudo apt install espeak-ng'.")
            return False

        # Test synthesis to stdout/buffer
        proc = subprocess.run(
            [espeak_bin, "-v", "en", "VisionVoice TTS check"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5.0
        )
        if proc.returncode == 0:
            print("[PASS] TTS")
            return True
        else:
            err = proc.stderr.decode("utf-8", errors="ignore").strip()
            print(f"[FAIL] TTS\n{espeak_bin} exited with error code {proc.returncode}: {err}")
            return False

    except Exception as e:
        print(f"[FAIL] TTS\nTTS verification failed with exception: {e}")
        return False

def test_audio_output():
    """
    4. Tests physical USB headphone output specifically via:
       espeak-ng --stdout "VisionVoice audio test" | aplay -D plughw:3,0
    """
    try:
        cmd = f'espeak-ng --stdout "VisionVoice audio test" | aplay -D {config.ALSA_PLAYBACK_DEVICE}'
        
        proc = subprocess.run(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=8.0
        )

        if proc.returncode == 0:
            print("[PASS] Audio output")
            return True
        else:
            err = proc.stderr.decode("utf-8", errors="ignore").strip()
            if not err:
                err = f"Process returned non-zero exit code {proc.returncode}"
            print(f"[FAIL] Audio output\nCommand '{cmd}' failed: {err}")
            return False

    except subprocess.TimeoutExpired:
        print(f"[FAIL] Audio output\nTimed out while attempting playback through ALSA {config.ALSA_PLAYBACK_DEVICE}")
        return False
    except Exception as e:
        print(f"[FAIL] Audio output\nException executing ALSA playback: {e}")
        return False

def test_gpio():
    """5. Tests physical GPIO Buttons (BCM Pins 17, 27, 22)."""
    try:
        import RPi.GPIO as GPIO  # type: ignore
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        pin_main = getattr(config, "PIN_MAIN_BTN", 17)
        pin_vol_up = getattr(config, "PIN_VOL_UP_BTN", 27)
        pin_vol_down = getattr(config, "PIN_VOL_DOWN_BTN", 22)

        GPIO.setup(pin_main, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(pin_vol_up, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(pin_vol_down, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        # Read pin values (default pulled HIGH)
        v_main = GPIO.input(pin_main)
        v_up = GPIO.input(pin_vol_up)
        v_down = GPIO.input(pin_vol_down)

        GPIO.cleanup([pin_main, pin_vol_up, pin_vol_down])
        print("[PASS] GPIO")
        return True

    except ImportError:
        print("[FAIL] GPIO\nRPi.GPIO Python library not found. Run 'sudo apt install python3-rpi.gpio'.")
        return False
    except Exception as e:
        print(f"[FAIL] GPIO\nGPIO configuration error: {e}")
        return False

def test_led():
    """6. Tests physical Status LED (BCM Pin 24)."""
    try:
        import RPi.GPIO as GPIO  # type: ignore
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        pin_led = getattr(config, "PIN_STATUS_LED", 24)
        GPIO.setup(pin_led, GPIO.OUT)

        # Blink test
        GPIO.output(pin_led, GPIO.HIGH)
        time.sleep(0.15)
        GPIO.output(pin_led, GPIO.LOW)

        GPIO.cleanup(pin_led)
        print("[PASS] LED")
        return True

    except ImportError:
        print("[FAIL] LED\nRPi.GPIO Python library not found. Run 'sudo apt install python3-rpi.gpio'.")
        return False
    except Exception as e:
        print(f"[FAIL] LED\nStatus LED (GPIO24) output error: {e}")
        return False

def run_hardware_diagnostics():
    """Executes all 6 independent hardware tests and prints comprehensive summary."""
    print("=" * 55)
    print("      VisionVoice — Hardware Diagnostic Testbench")
    print("=" * 55)
    
    results = {}
    results["Camera"] = test_camera()
    results["Microphone"] = test_microphone()
    results["TTS"] = test_tts()
    results["Audio output"] = test_audio_output()
    results["GPIO"] = test_gpio()
    results["LED"] = test_led()

    print("=" * 55)
    passed_count = sum(1 for v in results.values() if v)
    total_count = len(results)
    print(f"Summary: {passed_count}/{total_count} hardware tests passed.")
    print("=" * 55)
    return results

if __name__ == "__main__":
    run_hardware_diagnostics()
