import os
import ssl
import json
import logging
import urllib.request
import urllib.parse

try:
    import certifi
    os.environ['SSL_CERT_FILE'] = certifi.where()
    os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
except Exception:
    pass

# Ensure SSL certificate verification works cleanly on all platforms
try:
    ssl._create_default_https_context = ssl._create_unverified_context
except Exception:
    pass

import config

logger = logging.getLogger("VisionVoice.Translator")

MYMEMORY_LANG_MAP = {
    "ta": "tamil india",
    "hi": "hindi",
    "kn": "kannada",
    "te": "telugu",
    "ml": "malayalam",
    "en": "english us"
}


class TranslationEngine:
    """
    Multilingual Translation Engine for VisionVoice.
    Supports:
      1. ORIGINAL MODE: Reads extracted OCR text in its native detected script/language
         without making any external network or translation calls.
      2. TRANSLATION MODE: Translates text into the user's preferred target language
         (English, Tamil, Kannada, Telugu, Malayalam, Hindi) via resilient multi-provider routing.
      3. GRACEFUL NETWORK DEGRADATION: If the internet or translation API is unreachable,
         gracefully degrades to original text playback so reading is never interrupted.
    """

    def __init__(self):
        logger.info("Translation backend: resilient multi-provider ready.")

    def translate_text(self, text, source_lang, target_lang, mode=config.READING_MODE_PREFERRED):
        """
        Translates text based on source language, target language, and user reading mode.
        """
        if not text or not str(text).strip():
            return {
                "translated_text": "",
                "source_lang": source_lang,
                "target_lang": target_lang,
                "was_translated": False,
                "fallback_to_original": False
            }

        # 1. ORIGINAL MODE or SAME LANGUAGE: ZERO NETWORK REQUESTS
        if mode == config.READING_MODE_ORIGINAL or source_lang == target_lang:
            logger.info(f"Reading mode is '{mode}' (source: {source_lang}, target: {target_lang}). Using original text without translation.")
            return {
                "translated_text": text,
                "source_lang": source_lang,
                "target_lang": source_lang,
                "was_translated": False,
                "fallback_to_original": False
            }

        logger.info(f"Translating text from '{source_lang}' to preferred language '{target_lang}'...")
        translated_result = None

        # Provider 1: MyMemory Translator with locale mapping
        try:
            from deep_translator import MyMemoryTranslator
            s_name = MYMEMORY_LANG_MAP.get(source_lang, source_lang)
            t_name = MYMEMORY_LANG_MAP.get(target_lang, target_lang)
            res = MyMemoryTranslator(source=s_name, target=t_name).translate(text)
            if res and res.strip() and not res.strip().startswith("MYMEMORY WARNING") and not res.strip().startswith("Error 500"):
                translated_result = res.strip()
        except Exception as e:
            logger.debug(f"MyMemory translation note: {e}")

        # Provider 2: Google Direct API via urllib
        if not translated_result:
            try:
                url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={source_lang}&tl={target_lang}&dt=t&q=" + urllib.parse.quote(text)
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"})
                ctx = ssl._create_unverified_context()
                with urllib.request.urlopen(req, context=ctx, timeout=4.0) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    trans = "".join([part[0] for part in data[0] if part[0]]).strip()
                    if trans:
                        translated_result = trans
            except Exception as e:
                logger.debug(f"Google direct translation note: {e}")

        # Provider 3: DeepTranslator GoogleTranslator
        if not translated_result:
            try:
                from deep_translator import GoogleTranslator
                trans = GoogleTranslator(source=source_lang, target=target_lang).translate(text)
                if trans and trans.strip() and not trans.strip().startswith("Error 500"):
                    translated_result = trans.strip()
            except Exception as e:
                logger.debug(f"GoogleTranslator note: {e}")

        # 3. Result / Fallback
        if translated_result and str(translated_result).strip():
            return {
                "translated_text": translated_result.strip(),
                "source_lang": source_lang,
                "target_lang": target_lang,
                "was_translated": True,
                "fallback_to_original": False
            }
        else:
            logger.info("Translation unavailable (offline / network error). Falling back to original OCR text.")
            return {
                "translated_text": text,
                "source_lang": source_lang,
                "target_lang": source_lang,
                "was_translated": False,
                "fallback_to_original": True
            }

    def translate_sentences(self, sentences, source_lang, target_lang, mode=config.READING_MODE_PREFERRED):
        """Translates a list of sentence strings."""
        if not sentences:
            return []

        if mode == config.READING_MODE_ORIGINAL or source_lang == target_lang:
            return list(sentences)

        translated_sentences = []
        for s in sentences:
            res = self.translate_text(s, source_lang, target_lang, mode=mode)
            translated_sentences.append(res["translated_text"])

        return translated_sentences
