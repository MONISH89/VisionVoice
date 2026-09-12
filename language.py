import logging
import config

logger = logging.getLogger("VisionVoice.Language")

class LanguageDetector:
    """
    Automatic Language Identifier for VisionVoice.
    Identifies whether extracted text is in English, Tamil, Kannada, Telugu,
    Malayalam, or Hindi using script character range analysis & langdetect.
    """

    def detect_language(self, text):
        """
        Detects language code from text string.

        Args:
            text (str): Input text from OCR.

        Returns:
            dict containing:
                - 'lang': language code ('en', 'ta', 'kn', 'te', 'ml', 'hi')
                - 'name': human readable name ('English', 'Tamil', etc.)
                - 'confidence': confidence score (0.0 to 1.0)
        """
        if not text or len(text.strip()) == 0:
            return {"lang": config.DEFAULT_LANGUAGE, "name": config.SUPPORTED_LANGUAGES[config.DEFAULT_LANGUAGE]["name"], "confidence": 0.0}

        # 1. Primary Check: Unicode Block Character Frequency Analysis
        counts = {
            "ta": 0,  # Tamil: U+0B80 to U+0BFF
            "kn": 0,  # Kannada: U+0C80 to U+0CFF
            "te": 0,  # Telugu: U+0C00 to U+0C7F
            "ml": 0,  # Malayalam: U+0D00 to U+0D7F
            "hi": 0,  # Devanagari (Hindi): U+0900 to U+097F
            "en": 0   # Basic Latin: U+0041 to U+007A
        }

        total_chars = 0
        for char in text:
            code = ord(char)
            if 0x0B80 <= code <= 0x0BFF:
                counts["ta"] += 1
                total_chars += 1
            elif 0x0C80 <= code <= 0x0CFF:
                counts["kn"] += 1
                total_chars += 1
            elif 0x0C00 <= code <= 0x0C7F:
                counts["te"] += 1
                total_chars += 1
            elif 0x0D00 <= code <= 0x0D7F:
                counts["ml"] += 1
                total_chars += 1
            elif 0x0900 <= code <= 0x097F:
                counts["hi"] += 1
                total_chars += 1
            elif (0x0041 <= code <= 0x005A) or (0x0061 <= code <= 0x007A):
                counts["en"] += 1
                total_chars += 1

        if total_chars > 0:
            best_lang = max(counts, key=lambda k: counts[k])
            ratio = counts[best_lang] / float(total_chars)
            if ratio > 0.15:
                lang_name = config.SUPPORTED_LANGUAGES.get(best_lang, {}).get("name", "English")
                logger.info(f"Language identified via Unicode block: '{best_lang}' ({lang_name}) with ratio {ratio:.2f}")
                return {"lang": best_lang, "name": lang_name, "confidence": ratio}

        # 2. Secondary Check: langdetect library
        try:
            from langdetect import detect
            detected = detect(text)
            # Map langdetect output to supported languages
            lang_map = {"ta": "ta", "kn": "kn", "te": "te", "ml": "ml", "hi": "hi", "en": "en"}
            mapped = lang_map.get(detected, "en")
            lang_name = config.SUPPORTED_LANGUAGES.get(mapped, {}).get("name", "English")
            logger.info(f"Language identified via langdetect: '{mapped}' ({lang_name})")
            return {"lang": mapped, "name": lang_name, "confidence": 0.85}
        except Exception as e:
            logger.debug(f"langdetect unavailable or failed: {e}")

        # Default fallback
        default_name = config.SUPPORTED_LANGUAGES[config.DEFAULT_LANGUAGE]["name"]
        return {"lang": config.DEFAULT_LANGUAGE, "name": default_name, "confidence": 0.50}
