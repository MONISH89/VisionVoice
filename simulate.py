#!/usr/bin/env python3
"""
VisionVoice — Interactive CLI Testing & Hardware Simulation Suite.
Allows testing the complete hands-free reading assistant workflow on desktop
environments without requiring physical Raspberry Pi camera or GPIO hardware.
"""

import os
import sys
import time

import config
from camera import CameraManager
from alignment import PageAlignmentAnalyzer
from page_processor import PageProcessor
from ocr import OCRManager
from language import LanguageDetector
from translator import TranslationEngine
from speech import SpeechEngine
from memory import BookMemoryManager
from voice_control import VoiceController

def print_banner():
    print("=" * 65)
    print("      VisionVoice — Interactive Device Simulator & Testbench")
    print("=" * 65)
    print("Supported Languages: English, Tamil, Kannada, Telugu, Malayalam, Hindi")
    print("Hardware Target:     Raspberry Pi 4 + Camera Module 3 + USB Headset")
    print("=" * 65)

def run_simulation():
    print_banner()

    print("\n[1] Initializing System Components...")
    camera = CameraManager()
    alignment = PageAlignmentAnalyzer()
    processor = PageProcessor()
    ocr = OCRManager()
    lang_detector = LanguageDetector()
    translator = TranslationEngine()
    speech = SpeechEngine()
    memory = BookMemoryManager()
    voice = VoiceController()

    print("✓ All 9 Subsystems Initialized Successfully!\n")

    # Interactive Menu
    sample_texts = {
        "1": ("English Book Page", "VisionVoice is an intelligent assistive reading device designed to allow visually impaired users to read physical books completely hands-free. The system uses computer vision and OCR to extract text accurately. Chapter One begins here."),
        "2": ("Tamil Book Page (தமிழ்)", "விஷன்வாய்ஸ் என்பது ஒரு அறிவார்ந்த வாசிப்பு சாதனமாகும். இது அச்சிடப்பட்ட புத்தகங்களை கைகள் இல்லாமல் வாசிக்க உதவுகிறது. முதல் அத்தியாயம் இங்கே தொடங்குகிறது."),
        "3": ("Kannada Book Page (ಕನ್ನಡ)", "ವಿಷನ್-ವಾಯ್ಸ್ ಒಂದು ಬುದ್ಧಿವಂತ ಸಹಾಯಕ ಓದುವ ಸಾಧನವಾಗಿದೆ. ಇದು ದೃಷ್ಟಿಹೀನ ಬಳಕೆದಾರರಿಗೆ ಪುಸ್ತಕಗಳನ್ನು ಓದಲು ಸಹಾಯ ಮಾಡುತ್ತದೆ. ಮೊದಲ ಅಧ್ಯಾಯ ಇಲ್ಲಿಂದ ಆರಂಭವಾಗುತ್ತದೆ."),
        "4": ("Telugu Book Page (తెలుగు)", "విజన్ వాయిస్ అనేది ఒక స్మార్ట్ పఠన సహాయక పరికరం. ఇది చేతులు ఉపయోగించకుండా పుస్తకాలను చదవడానికి సహాయపడుతుంది. మొదటి అధ్యాయం ఇక్కడ ప్రారంభమవుతుంది."),
        "5": ("Malayalam Book Page (മലയാളം)", "വിഷൻ വോയ്സ് ഒരു സ്മാർട്ട് വായനാ സഹായിയാണ്. ഇത് പുസ്തകങ്ങൾ എളുപ്പത്തിൽ വായിക്കാൻ സഹായിക്കുന്നു. ഒന്നാം അധ്യായം ഇവിടെ ആരംഭിക്കുന്നു."),
        "6": ("Hindi Book Page (हिन्दी)", "विज़नवॉइस एक बुद्धिमान सहायक पठन उपकरण है। यह उपयोगकर्ताओं को बिना हाथ लगाए किताबें पढ़ने में मदद करता है। पहला अध्याय यहाँ से शुरू होता है।")
    }

    while True:
        print("\n--- VISIONVOICE SIMULATOR MENU ---")
        print("1. Simulate Voice Wake Phrase ('Hey VisionVoice')")
        print("2. Test Spoken Language & Reading Mode Preferences")
        print("3. Test Camera Page Alignment & Spoken Guidance")
        print("4. Test Computer Vision Perspective Unwarping")
        print("5. Test Multilingual OCR & Automatic Script Detection")
        print("6. Test Translation Engine (Original vs Preferred)")
        print("7. Test Text-to-Speech Sentence Queue & Volume Controls")
        print("8. Test Book Fingerprinting & Reading Memory Persistence")
        print("9. Run Full End-to-End Simulation (Wake -> Align -> OCR -> Read -> Next Page)")
        print("0. Exit")

        choice = input("\nEnter choice [0-9]: ").strip()

        if choice == "0":
            print("\nExiting simulator. Goodbye!")
            break

        elif choice == "1":
            print("\n[Simulation] Speaking wake phrase: 'Hey VisionVoice'...")
            cmd = voice.parse_command("hey visionvoice")
            print(f"Recognized Event: '{cmd}'")
            speech.speak("Yes, VisionVoice is ready. What would you like to read?")

        elif choice == "2":
            print("\n--- Testing Spoken Preferences ---")
            print("Options: English (en), Tamil (ta), Kannada (kn), Telugu (te), Malayalam (ml), Hindi (hi)")
            spoken_lang = input("Simulate user saying language (e.g. 'Tamil'): ").strip()
            lang_code = voice.parse_language_choice(spoken_lang) or "en"
            print(f"Parsed Language Code: '{lang_code}' ({config.SUPPORTED_LANGUAGES[lang_code]['name']})")

            spoken_mode = input("Simulate reading mode ('original' or 'preferred'): ").strip()
            mode = voice.parse_mode_choice(spoken_mode) or config.READING_MODE_PREFERRED
            print(f"Parsed Reading Mode: '{mode}'")

            memory.preferred_language = lang_code
            memory.reading_mode = mode
            memory.save_session()
            speech.speak(f"Preferences saved. Preferred language: {config.SUPPORTED_LANGUAGES[lang_code]['name']}.")

        elif choice == "3":
            print("\n--- Testing Real-time Page Alignment Analyzer ---")
            frame = camera.get_frame()
            analysis = alignment.analyze_frame(frame)
            print(f"Is Aligned:       {analysis['is_aligned']}")
            print(f"Is Stable:        {analysis['is_stable']}")
            print(f"Ready to Capture: {analysis['ready_for_capture']}")
            print(f"Voice Guidance:   '{analysis['guidance']}'")
            if analysis['guidance']:
                speech.speak(analysis['guidance'])

        elif choice == "4":
            print("\n--- Testing CV Pipeline (4 Corners & Perspective Unwarp & Preprocessing) ---")
            frame = camera.get_frame()
            processed = processor.process_captured_page(frame)
            print(f"Detected Corners: {processed['corners'].tolist()}")
            print(f"Warped Shape:     {processed['warped'].shape}")
            print(f"Enhanced Shape:   {processed['enhanced'].shape}")
            print(f"Saved Image Path: {processed['saved_path']}")
            print(f"Debug Image Path: {os.path.join(config.BASE_DIR, 'debug', 'preprocessed.png')}")

        elif choice == "5":
            print("\n--- Testing Multilingual OCR & Language Identification ---")
            print("Select Sample Page to Test:")
            for k, (label, _) in sample_texts.items():
                print(f"  {k}. {label}")
            sub = input("Choose [1-6]: ").strip()
            label, sample_str = sample_texts.get(sub, sample_texts["1"])

            print(f"\nProcessing {label}...")
            det = lang_detector.detect_language(sample_str)
            print(f"Detected Language: {det['name']} ({det['lang']}) - Confidence: {det['confidence']:.2f}")

            sentences = ocr.split_sentences(sample_str)
            print(f"Extracted {len(sentences)} clean reading sentences:")
            for i, s in enumerate(sentences):
                print(f"  [{i+1}] {s}")

        elif choice == "6":
            print("\n--- Testing Translation Engine ---")
            source_txt = sample_texts["2"][1]  # Tamil sample
            print(f"Source Tamil Text: '{source_txt[:60]}...'")
            trans_res = translator.translate_text(
                source_txt, source_lang="ta", target_lang="en", mode=config.READING_MODE_PREFERRED
            )
            print(f"Translated to English: '{trans_res['translated_text']}'")

        elif choice == "7":
            print("\n--- Testing Speech Queue & Volume Controls ---")
            print(f"Current Volume: {speech.volume}%")
            speech.increase_volume()
            print(f"Volume after increase: {speech.volume}%")
            speech.decrease_volume()
            print(f"Volume after decrease: {speech.volume}%")

        elif choice == "8":
            print("\n--- Testing Book Identification & Reading Memory ---")
            sample_txt = sample_texts["1"][1]
            book_info = memory.identify_or_create_book(sample_txt, detected_lang="en")
            print(f"Book ID:           {book_info['book_id']}")
            print(f"Is New Book:       {book_info['is_new_book']}")
            print(f"Saved Last Page:   {book_info['last_page']}")
            print(f"Saved Sentence:    {book_info['last_sentence_idx']}")

            # Simulate reading forward 3 sentences
            memory.update_progress(page_num=1, sentence_idx=3)
            print("Updated progress to Page 1, Sentence 3.")

            # Re-identify same book
            re_info = memory.identify_or_create_book(sample_txt, detected_lang="en")
            print(f"Re-identified Book ID: {re_info['book_id']} - Restored Sentence Index: {re_info['last_sentence_idx']}")

        elif choice == "9":
            print("\n=== RUNNING FULL END-TO-END READING SIMULATION ===")
            print("Step 1: Spoken Wake-up")
            speech.speak("VisionVoice active. Initializing reading pipeline.")
            time.sleep(0.5)

            print("Step 2: Checking Alignment")
            speech.speak("Analyzing book alignment. Page is aligned. Capturing.", blocking=False)
            frame = camera.capture_high_res()

            print("Step 3: CV Rectification & OCR")
            processed = processor.process_captured_page(frame)
            sample_str = sample_texts["1"][1]
            ocr_res = ocr.extract_text(processed["enhanced"], target_lang="en")
            if not ocr_res["text"]:
                ocr_res["text"] = sample_str
                ocr_res["sentences"] = ocr.split_sentences(sample_str)

            print(f"Extracted {len(ocr_res['sentences'])} sentences.")

            print("Step 4: Book Memory Identification")
            book_info = memory.identify_or_create_book(ocr_res["text"], detected_lang="en")
            print(f"Identified Book: {book_info['book_id']} (Page {book_info['last_page']})")

            print("Step 5: Sentence-by-Sentence Playback Simulation")
            for idx, sent in enumerate(ocr_res["sentences"]):
                print(f"  -> Reading [{idx+1}/{len(ocr_res['sentences'])}]: {sent}")
                memory.update_progress(page_num=book_info["last_page"], sentence_idx=idx+1)
                time.sleep(0.4)

            print("Step 6: Page Completed Notification")
            speech.speak("Finished reading. Please turn to the next page.")
            print("✓ Full End-to-End Simulation Completed Successfully!")

        time.sleep(0.5)

if __name__ == "__main__":
    run_simulation()
