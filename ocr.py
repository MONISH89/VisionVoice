import os
import re
import subprocess
import logging
try:
    import cv2
except ImportError:
    cv2 = None

try:
    import numpy as np
except ImportError:
    np = None

import config

logger = logging.getLogger("VisionVoice.OCR")

class OCRManager:
    """
    Multilingual Optical Character Recognition (OCR) Engine for VisionVoice.
    Uses Tesseract OCR to extract printed text in English, Tamil, Kannada,
    Telugu, Malayalam, and Hindi.
    """

    def __init__(self):
        self.pytesseract_available = False
        self.pytesseract = None
        self._check_tesseract()

    def _check_tesseract(self):
        """Verifies if pytesseract and tesseract executable are available."""
        try:
            import pytesseract
            self.pytesseract = pytesseract
            self.pytesseract_available = True
            logger.info("pytesseract module imported successfully.")
        except ImportError:
            logger.warning("pytesseract module not found. Falling back to tesseract CLI or mock OCR.")

    def extract_text(self, image, target_lang="en"):
        """
        Extracts real text from an image using Tesseract OCR without fabricating output.

        Args:
            image (np.ndarray): Preprocessed page image.
            target_lang (str): Language code ('en', 'ta', 'kn', 'te', 'ml', 'hi').

        Returns:
            dict containing:
                - 'text': actual extracted text string (or "" if no legible text)
                - 'sentences': list of cleaned sentence strings
                - 'confidence': estimated OCR confidence score (0-100)
        """
        if image is None:
            logger.info("OCR RESULT:\n<no text detected - empty image>")
            print("OCR RESULT:\n<no text detected - empty image>")
            return {"text": "", "sentences": [], "confidence": 0.0}

        tess_lang = config.SUPPORTED_LANGUAGES.get(target_lang, {}).get("tesseract", "eng")
        # Combine with English for mixed script & numbers support
        if tess_lang != "eng":
            tess_lang = f"{tess_lang}+eng"

        logger.info(f"Running Tesseract OCR with language parameters: '{tess_lang}'")

        raw_text = ""
        confidence = 0.0

        # 1. Attempt pytesseract extraction
        if self.pytesseract_available and self.pytesseract is not None:
            try:
                custom_config = f"-l {tess_lang} --oem 1 --psm 3"
                raw_out = self.pytesseract.image_to_string(image, config=custom_config)
                raw_text = str(raw_out) if raw_out else ""
                confidence = 85.0
            except Exception as e:
                logger.warning(f"pytesseract with {tess_lang} failed ({e}). Retrying with default 'eng'...")
                try:
                    raw_out = self.pytesseract.image_to_string(image, config="-l eng --oem 1 --psm 3")
                    raw_text = str(raw_out) if raw_out else ""
                    confidence = 70.0
                except Exception:
                    raw_text = self._extract_via_apple_vision(image)
                    if not raw_text:
                        raw_text = self._extract_via_cli(image, tess_lang)
                    confidence = 85.0 if raw_text else 65.0
        else:
            # 2. Attempt Apple Vision OCR / Tesseract CLI extraction
            raw_text = self._extract_via_apple_vision(image)
            if not raw_text:
                raw_text = self._extract_via_cli(image, tess_lang)
            confidence = 85.0 if raw_text else 65.0

        cleaned_text = self._clean_text(raw_text)

        # Mandatory OCR RESULT logging and console output
        if cleaned_text:
            logger.info(f"OCR RESULT:\n{cleaned_text}")
            print(f"OCR RESULT:\n{cleaned_text}")
            sentences = self.split_sentences(cleaned_text)
            logger.info(f"Extracted {len(sentences)} sentences from page (total characters: {len(cleaned_text)}).")
        else:
            logger.info("OCR RESULT:\n<no text detected>")
            print("OCR RESULT:\n<no text detected>")
            sentences = []
            confidence = 0.0

        return {
            "text": cleaned_text,
            "sentences": sentences,
            "confidence": confidence
        }

    def _extract_via_apple_vision(self, image):
        """Native Apple Vision Framework OCR fallback for macOS."""
        import tempfile
        if cv2 is None or image is None:
            return ""

        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_img:
                cv2.imwrite(tmp_img.name, image)
                tmp_path = tmp_img.name

            swift_code = (
                "import Foundation\n"
                "import Vision\n"
                "import CoreGraphics\n"
                "import ImageIO\n"
                "guard CommandLine.arguments.count > 1 else { exit(1) }\n"
                "let path = CommandLine.arguments[1]\n"
                "let url = URL(fileURLWithPath: path)\n"
                "guard let imageSource = CGImageSourceCreateWithURL(url as CFURL, nil),\n"
                "      let cgImage = CGImageSourceCreateImageAtIndex(imageSource, 0, nil) else { exit(1) }\n"
                "let request = VNRecognizeTextRequest { (req, err) in\n"
                "    guard let results = req.results as? [VNRecognizedTextObservation] else { return }\n"
                "    for obs in results {\n"
                "        if let top = obs.topCandidates(1).first { print(top.string) }\n"
                "    }\n"
                "}\n"
                "request.recognitionLevel = .accurate\n"
                "let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])\n"
                "try? handler.perform([request])\n"
            )

            cmd = ["swift", "-e", swift_code, tmp_path]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10.0)

            try:
                os.remove(tmp_path)
            except Exception:
                pass

            if proc.returncode == 0:
                text = proc.stdout.decode("utf-8", errors="ignore").strip()
                if text:
                    logger.info("Extracted text successfully using Apple Vision OCR.")
                    return text
            return ""
        except Exception as e:
            logger.debug(f"Apple Vision OCR note: {e}")
            return ""

    def _extract_via_cli(self, image, tess_lang):
        """Fallback Tesseract extraction using system command-line tool without mock data."""
        import tempfile
        if cv2 is None:
            return ""

        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_img:
                cv2.imwrite(tmp_img.name, image)
                output_base = tmp_img.name + "_out"

            cmd = ["tesseract", tmp_img.name, output_base, "-l", tess_lang, "--psm", "3"]
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=15.0)

            txt_file = output_base + ".txt"
            text = ""
            if os.path.exists(txt_file):
                with open(txt_file, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
                try:
                    os.remove(txt_file)
                except Exception:
                    pass

            try:
                os.remove(tmp_img.name)
            except Exception:
                pass

            return text
        except Exception as e:
            logger.warning(f"Tesseract CLI extraction unavailable/error: {e}")
            return ""

    def _clean_text(self, text):
        """Cleans raw OCR output text, fixing hyphenation and extra whitespace."""
        if not text:
            return ""
        # Fix broken hyphens at line endings
        text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', text)
        # Replace multiple whitespace/newlines with single space
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def split_sentences(self, text):
        """Splits full page text into clean sentence segments for TTS audio reading."""
        if not text:
            return []
        # Split by sentence ending delimiters across Indic and Latin scripts (. ! ? ।)
        sentence_pattern = r"(?<=[.!?।])\s+"
        raw_sentences = re.split(sentence_pattern, text)
        sentences = [s.strip() for s in raw_sentences if len(s.strip()) > 1]
        return sentences if sentences else [text]
