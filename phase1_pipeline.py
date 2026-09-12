#!/usr/bin/env python3
"""
VisionVoice — Phase 1 Core Pipeline Runner.
Connects directly:
  CAMERA -> CAPTURE -> OPENCV PREPROCESSING -> TESSERACT OCR -> eSpeak-ng -> ALSA plughw:3,0 -> HEADPHONES

Executes the primary assistive reading loop with zero unnecessary abstractions.
"""

import os
import sys
import time
import subprocess
import logging

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

import config
from camera import CameraManager
from page_processor import PageProcessor
from ocr import OCRManager
from speech import SpeechEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("VisionVoice.Phase1")

def run_phase1_cycle():
    print("=" * 60)
    print("      VisionVoice — PHASE 1 CORE PIPELINE EXECUTION")
    print("      Camera -> OCR -> eSpeak-ng -> plughw:3,0")
    print("=" * 60)

    # 1. Initialize Subsystems
    logger.info("[1/5] Initializing Camera, Processor, OCR, and Speech Engine...")
    camera = CameraManager()
    processor = PageProcessor()
    ocr = OCRManager()
    speech = SpeechEngine()

    try:
        # 2. Camera Frame Capture
        logger.info("[2/5] Capturing page image from camera...")
        frame = camera.capture_page()
        if frame is None:
            logger.error("Camera capture returned None. Ensure camera hardware is connected.")
            speech.speak("Camera error. Please verify camera connection.", lang="en")
            return False

        h, w = frame.shape[:2]
        logger.info(f"Captured frame resolution: {w}x{h}")

        # 3. OpenCV Page Preprocessing Pipeline
        logger.info("[3/5] Applying OpenCV preprocessing (grayscale, bilateral noise reduction, CLAHE contrast, adaptive threshold)...")
        processed = processor.preprocess_page(
            frame,
            upscale=False,
            noise_reduction="bilateral",
            contrast_enhancement="clahe",
            threshold_method="adaptive",
            save_debug=True
        )

        # 4. Multilingual Tesseract OCR Extraction
        logger.info("[4/5] Running Tesseract OCR on preprocessed image...")
        ocr_result = ocr.extract_text(processed, target_lang="en")
        extracted_text = ocr_result.get("text", "").strip()
        sentences = ocr_result.get("sentences", [])

        print("-" * 60)
        if extracted_text:
            print(f"OCR RESULT ({len(sentences)} sentences):\n{extracted_text}")
        else:
            print("OCR RESULT:\n<no text detected>")
        print("-" * 60)

        # 5. Text-to-Speech via eSpeak-ng & ALSA plughw:3,0
        logger.info("[5/5] Synthesizing speech via eSpeak-ng and playing through ALSA plughw:3,0...")
        if sentences:
            for idx, sentence in enumerate(sentences):
                logger.info(f"Reading sentence [{idx+1}/{len(sentences)}]: '{sentence}'")
                speech.speak(sentence, lang="en", blocking=True)
        else:
            speech.speak("No legible text detected on the page. Please check lighting.", lang="en", blocking=True)

        logger.info("✓ Phase 1 pipeline cycle completed successfully!")
        return True

    except Exception as e:
        logger.error(f"Phase 1 execution error: {e}", exc_info=True)
        return False
    finally:
        logger.info("Releasing camera and audio resources...")
        camera.release()
        speech.stop()

if __name__ == "__main__":
    success = run_phase1_cycle()
    sys.exit(0 if success else 1)
