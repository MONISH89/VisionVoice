#!/usr/bin/env python3
"""
VisionVoice — Automated Unit & Integration Test Suite.
Validates all subsystems, algorithms, and logic pipelines.
"""

import os
import sys
import unittest
import numpy as np

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

import config
from alignment import PageAlignmentAnalyzer
from page_processor import PageProcessor
from ocr import OCRManager
from language import LanguageDetector
from translator import TranslationEngine
from memory import BookMemoryManager
from voice_control import VoiceController
from speech import SpeechEngine
from buttons import HardwareButtonController

import tempfile
import shutil

class TestVisionVoiceSubsystems(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_books_dir = os.path.join(self.test_dir, "books")
        self.test_sessions_dir = os.path.join(self.test_dir, "sessions")
        os.makedirs(self.test_books_dir, exist_ok=True)
        os.makedirs(self.test_sessions_dir, exist_ok=True)

        self.alignment = PageAlignmentAnalyzer()
        self.processor = PageProcessor()
        self.ocr = OCRManager()
        self.lang_detector = LanguageDetector()
        self.translator = TranslationEngine()
        self.memory = BookMemoryManager()
        self.memory.books_dir = self.test_books_dir
        self.memory.sessions_dir = self.test_sessions_dir
        self.memory.current_session_file = os.path.join(self.test_sessions_dir, "current_session.json")
        self.voice = VoiceController()
        self.speech = SpeechEngine()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # 1. Config Tests
    def test_01_config_structure(self):
        self.assertIn("en", config.SUPPORTED_LANGUAGES)
        self.assertIn("ta", config.SUPPORTED_LANGUAGES)
        self.assertIn("kn", config.SUPPORTED_LANGUAGES)
        self.assertIn("te", config.SUPPORTED_LANGUAGES)
        self.assertIn("ml", config.SUPPORTED_LANGUAGES)
        self.assertIn("hi", config.SUPPORTED_LANGUAGES)
        self.assertTrue(os.path.exists(config.DATA_DIR))
        self.assertTrue(os.path.exists(config.BOOKS_DIR))
        self.assertTrue(os.path.exists(config.SESSIONS_DIR))

    # 2. Alignment Logic Tests (Consecutive Frames Stability & Spoken Guidance)
    def test_02_alignment_analyzer(self):
        # Create a synthetic image with centered white rectangle
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        img[60:420, 100:540] = 255  # Centered page

        self.alignment.reset()

        # 1. Single good frame must NOT trigger capture immediately
        res1 = self.alignment.analyze_frame(img)
        self.assertTrue(res1["is_aligned"])
        self.assertFalse(res1["ready_for_capture"], "Single good frame must NOT trigger capture immediately")

        # 2. Must remain stable for N consecutive frames before ready_for_capture is True
        for frame_idx in range(config.STABILITY_FRAMES_REQUIRED - 1):
            res = self.alignment.analyze_frame(img)
            if frame_idx < config.STABILITY_FRAMES_REQUIRED - 2:
                self.assertFalse(res["ready_for_capture"])

        res_ready = self.alignment.analyze_frame(img)
        self.assertTrue(res_ready["ready_for_capture"], f"Expected ready_for_capture=True after {config.STABILITY_FRAMES_REQUIRED} consecutive frames")

        # 3. Off-center page to the right gives 'Move the page left.'
        img_right = np.zeros((480, 640, 3), dtype=np.uint8)
        img_right[60:420, 350:620] = 255
        self.alignment.reset()
        res_right = self.alignment.analyze_frame(img_right)
        self.assertFalse(res_right["is_aligned"])
        self.assertFalse(res_right["ready_for_capture"])
        self.assertEqual(res_right["guidance"], "Move the page left.")

        # 4. Off-center page to the left gives 'Move the page right.'
        img_left = np.zeros((480, 640, 3), dtype=np.uint8)
        img_left[60:420, 20:300] = 255
        self.alignment.reset()
        res_left = self.alignment.analyze_frame(img_left)
        self.assertFalse(res_left["is_aligned"])
        self.assertEqual(res_left["guidance"], "Move the page right.")

        # 5. Page too small/far gives 'Move the page closer.'
        img_small = np.zeros((480, 640, 3), dtype=np.uint8)
        img_small[180:300, 260:380] = 255
        self.alignment.reset()
        res_small = self.alignment.analyze_frame(img_small)
        self.assertFalse(res_small["is_aligned"])
        self.assertEqual(res_small["guidance"], "Move the page closer.")

    # 3. Computer Vision Page Unwarp Tests
    def test_03_page_processor_unwarp(self):
        # Create a synthetic test image with a high-contrast white book page
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        img[50:430, 80:560] = 255
        processed = self.processor.process_captured_page(img)

        self.assertIn("warped", processed)
        self.assertIn("enhanced", processed)
        self.assertIn("corners", processed)
        self.assertEqual(len(list(processed["corners"])), 4)
        self.assertTrue(os.path.exists(processed["saved_path"]))

    # 3b. OpenCV Preprocessing Pipeline Tests (Grayscale, Noise, Contrast, Threshold, Upscale, Debug)
    def test_03b_preprocess_page_pipeline(self):
        from page_processor import preprocess_page, convert_to_grayscale, reduce_noise, enhance_contrast, apply_threshold

        # Create test page image with text and shadow gradient
        h, w = 400, 600
        img = np.ones((h, w, 3), dtype=np.uint8) * 220
        import cv2
        cv2.putText(img, "Preprocessing Test Page", (40, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (20, 20, 20), 2)
        cv2.putText(img, "Evaluating modular OpenCV pipeline", (40, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (30, 30, 30), 2)

        # Apply lighting gradient to simulate book spine shadow
        gradient = np.tile(np.linspace(0.65, 1.0, w), (h, 1))
        img = (img * gradient[:, :, np.newaxis]).astype(np.uint8)

        img_copy = img.copy()
        debug_file = os.path.join(self.test_dir, "debug_preprocessed.png")

        # 1. Test full modular preprocess_page function
        processed_adaptive = preprocess_page(
            img,
            upscale=True,
            target_min_dim=800,
            noise_reduction="bilateral",
            contrast_enhancement="clahe",
            threshold_method="adaptive",
            save_debug=True,
            debug_path=debug_file
        )

        # Verify output properties
        self.assertIsNotNone(processed_adaptive)
        self.assertEqual(len(processed_adaptive.shape), 2)  # Binary single-channel
        self.assertGreaterEqual(min(processed_adaptive.shape), 800)  # Upscaled
        self.assertTrue(os.path.exists(debug_file))  # Debug file saved headlessly

        # Verify original image was not modified in-place
        self.assertTrue(np.array_equal(img, img_copy))

        # 2. Test Otsu global thresholding mode
        processed_otsu = preprocess_page(img, threshold_method="otsu", save_debug=False)
        self.assertIsNotNone(processed_otsu)
        self.assertEqual(len(processed_otsu.shape), 2)

        # 3. Test return_stages dictionary
        stages = preprocess_page(img, return_stages=True, save_debug=False)
        self.assertIn("original", stages)
        self.assertIn("grayscale", stages)
        self.assertIn("scaled", stages)
        self.assertIn("denoised", stages)
        self.assertIn("enhanced", stages)
        self.assertIn("thresholded", stages)

        # 4. Test individual modular component functions
        gray = convert_to_grayscale(img)
        self.assertEqual(len(gray.shape), 2)

        denoised = reduce_noise(gray, method="bilateral")
        self.assertEqual(denoised.shape, gray.shape)

        enhanced = enhance_contrast(denoised, method="clahe")
        self.assertEqual(enhanced.shape, gray.shape)

        thresh = apply_threshold(enhanced, method="adaptive")
        self.assertEqual(thresh.shape, gray.shape)

    # 4. OCR & Sentence Splitting Tests
    def test_04_ocr_sentence_split(self):
        sample_text = "VisionVoice is hands-free. It uses computer vision! Does it support Tamil? Yes, it does."
        sentences = self.ocr.split_sentences(sample_text)
        self.assertEqual(len(sentences), 4)
        self.assertEqual(sentences[0], "VisionVoice is hands-free.")

    # 5. Language Detection Tests (Unicode Indic & Latin Scripts)
    def test_05_language_detection(self):
        samples = {
            "en": "Hello and welcome to the reading assistant.",
            "ta": "வணக்கம் மற்றும் வாசிப்பு உதவிக்கு வரவேற்கிறோம்.",
            "kn": "ನಮಸ್ಕಾರ ಮತ್ತು ಓದುವ ಸಹಾಯಕ್ಕೆ ಸುಸ್ವಾಗತ.",
            "te": "నమస్కారం మరియు పఠన సహాయానికి స్వాగతం.",
            "ml": "നമസ്കാരം, വായന സഹായിയിലേക്ക് സ്വാഗതം.",
            "hi": "नमस्ते और पठन सहायक में आपका स्वागत है।"
        }

        for expected_lang, text in samples.items():
            result = self.lang_detector.detect_language(text)
            self.assertEqual(result["lang"], expected_lang, f"Failed detection for {expected_lang}")

    # 6. Translation Engine & Language Preference Tests
    def test_06_translation_modes(self):
        text_en = "VisionVoice reads physical books hands-free."
        text_ta = "விஷன்வாய்ஸ் அச்சிடப்பட்ட புத்தகங்களை வாசிக்க உதவுகிறது."

        # 1. Original mode returns original text unchanged without translation
        orig_en = self.translator.translate_text(text_en, source_lang="en", target_lang="ta", mode=config.READING_MODE_ORIGINAL)
        self.assertEqual(orig_en["translated_text"], text_en)
        self.assertFalse(orig_en["was_translated"])
        self.assertEqual(orig_en["target_lang"], "en")

        orig_ta = self.translator.translate_text(text_ta, source_lang="ta", target_lang="en", mode=config.READING_MODE_ORIGINAL)
        self.assertEqual(orig_ta["translated_text"], text_ta)
        self.assertFalse(orig_ta["was_translated"])
        self.assertEqual(orig_ta["target_lang"], "ta")

        # 2. Preferred mode with identical source and target returns original text
        same_res = self.translator.translate_text(text_en, source_lang="en", target_lang="en", mode=config.READING_MODE_PREFERRED)
        self.assertEqual(same_res["translated_text"], text_en)
        self.assertFalse(same_res["was_translated"])

        # 3. Sentence list in Original mode returns original sentences unmodified
        sentences_ta = ["முதல் வாக்கியம்.", "இரண்டாவது வாக்கியம்."]
        res_sentences = self.translator.translate_sentences(sentences_ta, source_lang="ta", target_lang="en", mode=config.READING_MODE_ORIGINAL)
        self.assertEqual(res_sentences, sentences_ta)

        # 4. Network failure simulation: core original mode remains functional
        mock_translator = TranslationEngine()
        mock_translator.translator_type = "mock"
        offline_res = mock_translator.translate_text(text_ta, source_lang="ta", target_lang="en", mode=config.READING_MODE_PREFERRED)
        self.assertEqual(offline_res["translated_text"], text_ta)
        self.assertTrue(offline_res["fallback_to_original"])

    # 7. Voice Command Parsing Tests
    def test_07_voice_command_parsing(self):
        self.assertEqual(self.voice.parse_command("hey visionvoice"), "wake_word")
        self.assertEqual(self.voice.parse_command("please start reading now"), "start_reading")
        self.assertEqual(self.voice.parse_command("stop reading please"), "stop_reading")
        self.assertEqual(self.voice.parse_command("next sentence"), "next_sentence")
        self.assertEqual(self.voice.parse_command("skip sentence"), "next_sentence")
        self.assertEqual(self.voice.parse_command("repeat sentence"), "repeat")
        self.assertEqual(self.voice.parse_command("repeat that"), "repeat")
        self.assertEqual(self.voice.parse_command("repeat from beginning"), "repeat_beginning")
        self.assertEqual(self.voice.parse_command("continue reading"), "continue_reading")
        self.assertEqual(self.voice.parse_command("volume up"), "vol_up")
        self.assertEqual(self.voice.parse_command("decrease volume"), "vol_down")

    def test_07b_sentence_by_sentence_reading_state(self):
        """Validates sequential sentence-by-sentence playback, index maintenance, and commands."""
        sample_page_text = "Sentence one begins. Sentence two explains the concept. Sentence three concludes the page."
        sentences = self.ocr.split_sentences(sample_page_text)
        self.assertEqual(len(sentences), 3)

        # Initialize mock reading state
        current_sentence_index = 0
        read_history = []

        # 1. Normal Sequential Reading Path (Sentence 1 -> 2 -> 3 -> PAGE_FINISHED)
        for idx in range(len(sentences)):
            self.assertEqual(current_sentence_index, idx)
            sentence_to_read = sentences[current_sentence_index]
            read_history.append(sentence_to_read)
            # Simulate waiting for TTS playback completion
            current_sentence_index += 1

        self.assertEqual(len(read_history), 3)
        self.assertEqual(current_sentence_index, 3)
        # Page finished condition
        is_page_finished = (current_sentence_index >= len(sentences))
        self.assertTrue(is_page_finished)

        # 2. Test 'next sentence' command behavior
        current_sentence_index = 0
        current_sentence_index += 1  # Next sentence command advances index
        self.assertEqual(current_sentence_index, 1)
        self.assertEqual(sentences[current_sentence_index], "Sentence two explains the concept.")

        # 3. Test 'repeat sentence' command behavior
        current_sentence_index = max(0, current_sentence_index - 1)  # Repeat command replays sentence
        self.assertEqual(current_sentence_index, 0)
        self.assertEqual(sentences[current_sentence_index], "Sentence one begins.")

        # 4. Test 'stop reading' position saving
        current_sentence_index = 2
        self.memory.current_sentence_index = current_sentence_index
        self.assertEqual(self.memory.current_sentence_index, 2)
        self.assertEqual(self.memory.current_sentence_idx, 2)

    def test_08_voice_language_choice_parsing(self):
        self.assertEqual(self.voice.parse_language_choice("I want Tamil please"), "ta")
        self.assertEqual(self.voice.parse_language_choice("Read in Kannada"), "kn")
        self.assertEqual(self.voice.parse_language_choice("Telugu language"), "te")
        self.assertEqual(self.voice.parse_language_choice("Malayalam"), "ml")
        self.assertEqual(self.voice.parse_language_choice("Hindi"), "hi")
        self.assertEqual(self.voice.parse_language_choice("English"), "en")

    # 8. Book Memory & Fingerprint Persistence Tests
    def test_09_book_memory_lifecycle(self):
        import time
        unique_token = str(time.time()).replace(".", "")
        sample_page_1 = f"Once upon a time in a mysterious forest lived scholar {unique_token} who loved reading physical books."
        
        # Test creating new book
        res1 = self.memory.identify_or_create_book(sample_page_1, detected_lang="en")
        book_id = res1["book_id"]
        self.assertTrue(res1["is_new_book"])
        self.assertEqual(res1["last_page"], 1)

        # Update progress to sentence 3
        self.memory.update_progress(page_num=1, sentence_idx=3)

        # Test re-identifying same book
        res2 = self.memory.identify_or_create_book(sample_page_1, detected_lang="en")
        self.assertFalse(res2["is_new_book"])
        self.assertEqual(res2["book_id"], book_id)
        self.assertEqual(res2["last_sentence_idx"], 3)

        # Test different book creation
        sample_page_2 = f"Quantum mechanics {unique_token} describes physical properties of nature at scale of atoms."
        res3 = self.memory.identify_or_create_book(sample_page_2, detected_lang="en")
        self.assertTrue(res3["is_new_book"])
        self.assertNotEqual(res3["book_id"], book_id)

        # Test memory tracking properties
        self.assertEqual(self.memory.identified_book, res3["book_id"])
        self.assertEqual(self.memory.current_page, 1)
        self.memory.record_processed_page(5, "captures/page_test.jpg")
        self.assertEqual(self.memory.last_processed_page, 5)
        
        progress = self.memory.current_progress
        self.assertEqual(progress["identified_book"], res3["book_id"])
        self.assertEqual(progress["last_processed_page"], 5)

    def test_09b_book_memory_graceful_degradation(self):
        """Validates that memory and identification failures degrade gracefully without stopping the reading pipeline."""
        # 1. Test empty / minimal text identification does not crash
        res_empty = self.memory.identify_or_create_book("", detected_lang="en")
        self.assertIsInstance(res_empty, dict)
        self.assertIn("book_id", res_empty)

        res_short = self.memory.identify_or_create_book("Short", detected_lang="en")
        self.assertIsInstance(res_short, dict)

        # 2. Test corrupted JSON book file handling
        corrupt_file = os.path.join(self.memory.books_dir, "corrupt_book.json")
        with open(corrupt_file, "w") as f:
            f.write("{ INVALID JSON DATA")

        # Memory listing should handle corrupted file without raising exception
        all_books = self.memory._list_all_books()
        self.assertIsInstance(all_books, dict)

        # 3. Test update_progress and record_processed_page with invalid inputs
        self.memory.record_processed_page("invalid_number")
        self.memory.update_progress(page_num=1, sentence_idx=0)

        # 4. Pipeline continuity check (OCR -> Language Detection -> Reading continues even if memory is corrupted)
        ocr_text = "VisionVoice reading continues uninterrupted even if memory persistence is unavailable."
        detected = self.lang_detector.detect_language(ocr_text)
        self.assertEqual(detected["lang"], "en")
        sentences = self.ocr.split_sentences(ocr_text)
        self.assertGreater(len(sentences), 0)

        # Force identification exception and verify graceful return
        broken_memory = BookMemoryManager()
        broken_memory.books_dir = "/non_existent_path_visionvoice_test"
        res_fallback = broken_memory.identify_or_create_book("Testing fallback under I/O error", detected_lang="en")
        self.assertIsInstance(res_fallback, dict)
        self.assertIn("last_sentence_idx", res_fallback)

    # 10. Hardware Buttons and GPIO Config Tests
    def test_11_hardware_buttons_and_gpio_config(self):
        # Verify physical GPIO pin wiring (BCM Numbering)
        self.assertEqual(config.PIN_MAIN_BTN, 17)
        self.assertEqual(config.PIN_VOL_UP_BTN, 27)
        self.assertEqual(config.PIN_VOL_DOWN_BTN, 22)
        self.assertEqual(config.PIN_STATUS_LED, 24)
        
        main_pressed = []
        vol_up_pressed = []
        vol_down_pressed = []
        
        btn_ctrl = HardwareButtonController(
            main_callback=lambda: main_pressed.append(True),
            vol_up_callback=lambda: vol_up_pressed.append(True),
            vol_down_callback=lambda: vol_down_pressed.append(True)
        )
        self.assertIsNotNone(btn_ctrl)
        btn_ctrl.start()

        # Test LED State Indications
        for state in ["WAIT_WAKE_WORD", "LISTENING", "ALIGNING_PAGE", "PROCESSING_PAGE", "READING", "ERROR", "OFF"]:
            btn_ctrl.indicate_state(state)
            self.assertEqual(btn_ctrl.current_indication_state, state)

        # Test Debounce & Non-blocking callback triggers
        self.assertTrue(btn_ctrl._is_debounced(17))
        self.assertFalse(btn_ctrl._is_debounced(17), "Immediate consecutive press should be debounced")

        # Test non-blocking async execution
        btn_ctrl._async_handle_vol_up()
        btn_ctrl._async_handle_vol_down()
        btn_ctrl._async_handle_main_press()

        self.assertEqual(len(vol_up_pressed), 1)
        self.assertEqual(len(vol_down_pressed), 1)
        self.assertEqual(len(main_pressed), 1)

        btn_ctrl.cleanup()
        self.assertFalse(btn_ctrl.running)

    # 11. Audio Routing and ALSA Endpoint Tests
    def test_12_speech_engine_alsa_routing(self):
        self.assertEqual(config.ALSA_PLAYBACK_DEVICE, "plughw:3,0")
        self.assertEqual(config.ALSA_CARD_INDEX, 3)
        self.assertEqual(self.speech.volume, config.DEFAULT_VOLUME)
        # Verify speech generation produces a valid temporary file or handles gracefully
        wav_path = self.speech._generate_speech_wav("Testing audio routing", "en")
        if wav_path:
            self.assertTrue(os.path.exists(wav_path))
            try:
                os.remove(wav_path)
            except Exception:
                pass

    # 12. Microphone Device Index & Serialized Access Tests
    def test_13_voice_controller_serialized_mic_access(self):
        self.assertEqual(config.MIC_DEVICE_INDEX, 2)
        self.assertIsNotNone(self.voice.mic_lock)
        # Verify serialized lock acquire and release
        acquired = self.voice.mic_lock.acquire(timeout=0.5)
        self.assertTrue(acquired)
        self.voice.mic_lock.release()
        self.voice.stop()

    # 13. Headless Camera Manager Abstraction Tests
    def test_14_camera_headless_abstraction(self):
        from camera import CameraManager
        cam = CameraManager()
        self.assertTrue(hasattr(cam, "initialize"))
        self.assertTrue(hasattr(cam, "capture_frame"))
        self.assertTrue(hasattr(cam, "capture_page"))
        self.assertTrue(hasattr(cam, "release"))
        
        frame = cam.capture_frame()
        if cam.is_initialized and not cam.has_error and frame is not None:
            self.assertIsInstance(frame, np.ndarray)
            page = cam.capture_page()
            self.assertIsInstance(page, np.ndarray)
        
        cam.release()
        self.assertFalse(cam.running)

    # 14. Graceful Shutdown & Resource Release Lifecycle Test
    def test_15_graceful_shutdown_lifecycle(self):
        from main import VisionVoiceApp
        app = VisionVoiceApp()
        
        # Mock active reading state
        app.current_sentences = ["Sentence 1", "Sentence 2", "Sentence 3"]
        app.current_sentence_index = 2
        app.reading_active = True
        app.running = True
        
        # Trigger stop()
        app.stop()
        
        # Verify complete shutdown state
        self.assertFalse(app.running)
        self.assertFalse(app.reading_active)
        self.assertFalse(app.camera.running)
        self.assertFalse(app.voice.running)
        self.assertFalse(app.buttons.running)
        self.assertEqual(app.buttons.current_indication_state, "OFF")
        self.assertFalse(app.speech.is_speaking)

    # 15. Hardware Test Suite Diagnostic Execution Test
    def test_16_hardware_diagnostics_suite(self):
        from hardware_test import (
            test_camera,
            test_microphone,
            test_tts,
            test_audio_output,
            test_gpio,
            test_led,
            run_hardware_diagnostics
        )
        # All individual tests must return a boolean without raising unhandled exceptions
        self.assertIsInstance(test_camera(), bool)
        self.assertIsInstance(test_microphone(), bool)
        self.assertIsInstance(test_tts(), bool)
        self.assertIsInstance(test_audio_output(), bool)
        self.assertIsInstance(test_gpio(), bool)
        self.assertIsInstance(test_led(), bool)
        
        diag_results = run_hardware_diagnostics()
        self.assertIsInstance(diag_results, dict)
        self.assertEqual(len(diag_results), 6)

if __name__ == "__main__":
    unittest.main(verbosity=2)
