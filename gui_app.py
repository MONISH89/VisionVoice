#!/usr/bin/env python3
"""
VisionVoice — Fullscreen Camera & Interactive Assistive Reading Station.
Features:
  - Full-screen high-resolution live camera video stream
  - Dynamic ROI alignment guide & spoken positioning cues
  - Live HUD with active sentence display and TTS speech synchronization
  - Keyboard shortcuts (Space: Scan & Read, F: Fullscreen, Esc: Exit Fullscreen, P: Pause)
  - Multilingual OCR (Tesseract / Apple Vision), language detection & machine translation
"""

import os
import sys
import time
import threading
import tkinter as tk
from tkinter import ttk
import cv2
import numpy as np
from PIL import Image, ImageTk

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

import config
from camera import CameraManager
from alignment import PageAlignmentAnalyzer
from page_processor import PageProcessor
from ocr import OCRManager
from language import LanguageDetector
from translator import TranslationEngine
from speech import SpeechEngine
from memory import BookMemoryManager


class VisionVoiceFullscreenGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("VisionVoice — Fullscreen Camera Reading Station")
        self.root.geometry("1200x800")
        self.root.configure(bg="#0B0E14")

        # Fullscreen state
        self.is_fullscreen = False

        # Initialize Subsystems
        self.camera = CameraManager()
        self.alignment = PageAlignmentAnalyzer()
        self.processor = PageProcessor()
        self.ocr = OCRManager()
        self.lang_detector = LanguageDetector()
        self.translator = TranslationEngine()
        self.speech = SpeechEngine()
        self.memory = BookMemoryManager()

        # FSM and App State
        self.state = "WAIT_WAKE_WORD"
        self.preferred_lang = self.memory.preferred_language or config.DEFAULT_LANGUAGE
        self.reading_mode = self.memory.reading_mode or config.READING_MODE_PREFERRED
        self.current_sentences = []
        self.current_sentence_idx = 0
        self.current_speaking_sentence = ""
        self.is_reading = False
        self.pause_requested = False
        self.running = True
        self.last_guidance_text = "Place book inside the green target box"
        self.last_guidance_color = (0, 220, 255)  # BGR

        # Build UI Layout
        self._build_ui()

        # Bind Key Shortcuts
        self.root.bind("<F11>", lambda e: self.toggle_fullscreen())
        self.root.bind("<f>", lambda e: self.toggle_fullscreen())
        self.root.bind("<F>", lambda e: self.toggle_fullscreen())
        self.root.bind("<Escape>", lambda e: self.exit_fullscreen())
        self.root.bind("<space>", lambda e: self.trigger_scan_and_read())
        self.root.bind("<Return>", lambda e: self.trigger_scan_and_read())
        self.root.bind("<p>", lambda e: self.toggle_pause())
        self.root.bind("<P>", lambda e: self.toggle_pause())
        self.root.bind("<n>", lambda e: self.next_sentence())
        self.root.bind("<N>", lambda e: self.next_sentence())
        self.root.bind("<r>", lambda e: self.repeat_sentence())
        self.root.bind("<R>", lambda e: self.repeat_sentence())
        self.root.bind("<plus>", lambda e: self.volume_up())
        self.root.bind("<equal>", lambda e: self.volume_up())
        self.root.bind("<minus>", lambda e: self.volume_down())

        # Start Camera Video Stream Loop
        self.update_video_stream()

        # Start with Fullscreen Mode enabled
        self.toggle_fullscreen()

        # Initial Welcome Prompt
        threading.Thread(
            target=lambda: self.speech.speak("VisionVoice camera ready. Press Space to scan and read.", blocking=False),
            daemon=True
        ).start()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_ui(self):
        # 1. Top HUD Bar
        self.top_hud = tk.Frame(self.root, bg="#111620", height=48)
        self.top_hud.pack(fill=tk.X, side=tk.TOP)

        title_lbl = tk.Label(
            self.top_hud, text="👁️ VisionVoice Live Camera Reader",
            font=("Helvetica", 14, "bold"), bg="#111620", fg="#00E5FF"
        )
        title_lbl.pack(side=tk.LEFT, padx=14, pady=8)

        # Quick Language Selector in Top Bar
        lang_frame = tk.Frame(self.top_hud, bg="#111620")
        lang_frame.pack(side=tk.LEFT, padx=20)
        tk.Label(lang_frame, text="Language:", bg="#111620", fg="#A0AEC0", font=("Helvetica", 10)).pack(side=tk.LEFT, padx=4)

        lang_options = [f"{v['name']} ({k})" for k, v in config.SUPPORTED_LANGUAGES.items()]
        self.lang_var = tk.StringVar(value=f"{config.SUPPORTED_LANGUAGES.get(self.preferred_lang, {}).get('name', 'English')} ({self.preferred_lang})")
        self.lang_dropdown = ttk.Combobox(lang_frame, textvariable=self.lang_var, values=lang_options, state="readonly", width=14)
        self.lang_dropdown.pack(side=tk.LEFT, padx=4)
        self.lang_dropdown.bind("<<ComboboxSelected>>", self.on_language_changed)

        # Mode Selector
        self.mode_btn = tk.Button(
            self.top_hud, text=f"Mode: {self.reading_mode.capitalize()}",
            font=("Helvetica", 9, "bold"), bg="#1E293B", fg="#38BDF8", bd=1,
            activebackground="#334155", command=self.cycle_reading_mode
        )
        self.mode_btn.pack(side=tk.LEFT, padx=8)

        # Fullscreen Toggle Button
        self.fs_btn = tk.Button(
            self.top_hud, text="⛶ Toggle Fullscreen [F]",
            font=("Helvetica", 9, "bold"), bg="#0284C7", fg="#FFFFFF",
            activebackground="#0369A1", command=self.toggle_fullscreen
        )
        self.fs_btn.pack(side=tk.RIGHT, padx=12, pady=6)

        self.status_badge = tk.Label(
            self.top_hud, text="● READY", font=("Helvetica", 11, "bold"),
            bg="#111620", fg="#10B981"
        )
        self.status_badge.pack(side=tk.RIGHT, padx=12)

        # 2. Main Center Camera Canvas
        self.video_container = tk.Frame(self.root, bg="#000000")
        self.video_container.pack(fill=tk.BOTH, expand=True)

        self.video_label = tk.Label(self.video_container, bg="#000000")
        self.video_label.pack(fill=tk.BOTH, expand=True)

        # 3. Bottom Translucent Action HUD Bar
        self.bottom_hud = tk.Frame(self.root, bg="#111620", height=68)
        self.bottom_hud.pack(fill=tk.X, side=tk.BOTTOM)

        # Large Scan Button
        self.scan_btn = tk.Button(
            self.bottom_hud, text="🔘 SCAN & READ BOOK [SPACE]",
            font=("Helvetica", 12, "bold"), bg="#059669", fg="#FFFFFF",
            activebackground="#10B981", padx=18, pady=8, bd=0,
            command=self.trigger_scan_and_read
        )
        self.scan_btn.pack(side=tk.LEFT, padx=14, pady=8)

        # Pause / Resume Button
        self.pause_btn = tk.Button(
            self.bottom_hud, text="⏸ Pause [P]", font=("Helvetica", 10, "bold"),
            bg="#2563EB", fg="#FFFFFF", activebackground="#3B82F6", padx=12, pady=8, bd=0,
            command=self.toggle_pause
        )
        self.pause_btn.pack(side=tk.LEFT, padx=6, pady=8)

        # Repeat & Skip Buttons
        tk.Button(
            self.bottom_hud, text="🔄 Repeat [R]", font=("Helvetica", 10),
            bg="#374151", fg="#F3F4F6", padx=10, pady=8, bd=0,
            command=self.repeat_sentence
        ).pack(side=tk.LEFT, padx=4, pady=8)

        tk.Button(
            self.bottom_hud, text="⏭ Next [N]", font=("Helvetica", 10),
            bg="#374151", fg="#F3F4F6", padx=10, pady=8, bd=0,
            command=self.next_sentence
        ).pack(side=tk.LEFT, padx=4, pady=8)

        # Volume Controls
        tk.Button(
            self.bottom_hud, text="🔊 Vol +", font=("Helvetica", 10),
            bg="#374151", fg="#F3F4F6", padx=8, pady=8, bd=0, command=self.volume_up
        ).pack(side=tk.LEFT, padx=4, pady=8)

        tk.Button(
            self.bottom_hud, text="🔉 Vol -", font=("Helvetica", 10),
            bg="#374151", fg="#F3F4F6", padx=8, pady=8, bd=0, command=self.volume_down
        ).pack(side=tk.LEFT, padx=4, pady=8)

        # Live Subtitle / Spoken Sentence Label in Bottom HUD
        self.subtitle_lbl = tk.Label(
            self.bottom_hud, text="Press Space or click 'Scan & Read Book' to capture page text.",
            font=("Helvetica", 11, "italic"), bg="#111620", fg="#FBBF24",
            anchor="w", justify=tk.LEFT
        )
        self.subtitle_lbl.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=16, pady=8)

    def toggle_fullscreen(self):
        self.is_fullscreen = not self.is_fullscreen
        self.root.attributes("-fullscreen", self.is_fullscreen)
        if self.is_fullscreen:
            self.fs_btn.config(text="✕ Exit Fullscreen [Esc]")
        else:
            self.fs_btn.config(text="⛶ Toggle Fullscreen [F]")

    def exit_fullscreen(self):
        if self.is_fullscreen:
            self.is_fullscreen = False
            self.root.attributes("-fullscreen", False)
            self.fs_btn.config(text="⛶ Toggle Fullscreen [F]")

    def cycle_reading_mode(self):
        if self.reading_mode == config.READING_MODE_PREFERRED:
            self.reading_mode = config.READING_MODE_ORIGINAL
        else:
            self.reading_mode = config.READING_MODE_PREFERRED
        self.memory.reading_mode = self.reading_mode
        self.memory.save_session()
        self.mode_btn.config(text=f"Mode: {self.reading_mode.capitalize()}")

    def on_language_changed(self, event=None):
        raw = self.lang_var.get()
        if "(" in raw and ")" in raw:
            code = raw.split("(")[-1].split(")")[0]
            if code in config.SUPPORTED_LANGUAGES:
                self.preferred_lang = code
                self.memory.preferred_language = code
                self.memory.save_session()

    def update_video_stream(self):
        """Pulls frame from CameraManager, renders fullscreen HUD overlays and updates display."""
        if not self.running:
            return

        frame = self.camera.capture_frame()
        if frame is not None:
            # 1. Analyze Page Alignment
            analysis = self.alignment.analyze_frame(frame)
            disp_frame = frame.copy()
            h, w = disp_frame.shape[:2]

            # 2. Draw Target ROI Box with Rounded Corner Accents
            tx1, ty1 = int(w * config.ROI_MARGIN_X), int(h * config.ROI_MARGIN_Y)
            tx2, ty2 = int(w * (1.0 - config.ROI_MARGIN_X)), int(h * (1.0 - config.ROI_MARGIN_Y))

            box_color = (46, 204, 113) if analysis["is_aligned"] else (39, 174, 96)  # BGR
            if analysis["ready_for_capture"]:
                box_color = (0, 255, 128)
            elif not analysis["is_aligned"]:
                box_color = (0, 165, 255)

            # Draw outer framing box
            cv2.rectangle(disp_frame, (tx1, ty1), (tx2, ty2), box_color, 2)

            # Corner brackets for HUD aesthetic
            corner_len = 28
            thickness = 4
            # Top-Left
            cv2.line(disp_frame, (tx1, ty1), (tx1 + corner_len, ty1), box_color, thickness)
            cv2.line(disp_frame, (tx1, ty1), (tx1, ty1 + corner_len), box_color, thickness)
            # Top-Right
            cv2.line(disp_frame, (tx2, ty1), (tx2 - corner_len, ty1), box_color, thickness)
            cv2.line(disp_frame, (tx2, ty1), (tx2, ty1 + corner_len), box_color, thickness)
            # Bottom-Left
            cv2.line(disp_frame, (tx1, ty2), (tx1 + corner_len, ty2), box_color, thickness)
            cv2.line(disp_frame, (tx1, ty2), (tx1, ty2 - corner_len), box_color, thickness)
            # Bottom-Right
            cv2.line(disp_frame, (tx2, ty2), (tx2 - corner_len, ty2), box_color, thickness)
            cv2.line(disp_frame, (tx2, ty2), (tx2, ty2 - corner_len), box_color, thickness)

            # Center target crosshair
            cx, cy = int((tx1 + tx2) / 2), int((ty1 + ty2) / 2)
            cv2.drawMarker(disp_frame, (cx, cy), box_color, markerType=cv2.MARKER_CROSS, markerSize=16, thickness=1)

            # 3. Dynamic Spoken Guidance Banner on Top of Frame
            guidance_msg = analysis.get("guidance", "")
            if guidance_msg:
                self.last_guidance_text = guidance_msg
                self.last_guidance_color = (0, 165, 255)
            elif analysis["ready_for_capture"]:
                self.last_guidance_text = "Page Aligned & Steady ✓ (Ready to Scan)"
                self.last_guidance_color = (46, 204, 113)
            elif analysis["is_aligned"]:
                self.last_guidance_text = "Page Centered — Hold steady..."
                self.last_guidance_color = (0, 220, 255)

            # Draw semi-transparent HUD banner at top of video
            overlay = disp_frame.copy()
            cv2.rectangle(overlay, (0, 0), (w, 40), (15, 20, 28), -1)
            cv2.addWeighted(overlay, 0.75, disp_frame, 0.25, 0, disp_frame)

            cv2.putText(
                disp_frame, f"ALIGNMENT: {self.last_guidance_text}", (20, 26),
                cv2.FONT_HERSHEY_DUPLEX, 0.65, self.last_guidance_color, 1, cv2.LINE_AA
            )

            # 4. Live Reading Subtitle Overlay if Reading
            if self.is_reading and self.current_speaking_sentence:
                overlay2 = disp_frame.copy()
                cv2.rectangle(overlay2, (0, h - 55), (w, h), (10, 15, 25), -1)
                cv2.addWeighted(overlay2, 0.85, disp_frame, 0.15, 0, disp_frame)

                sub_text = self.current_speaking_sentence
                if len(sub_text) > 75:
                    sub_text = sub_text[:72] + "..."
                cv2.putText(
                    disp_frame, f"🔊 {sub_text}", (20, h - 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2, cv2.LINE_AA
                )

            # 5. Dynamically Scale to Fullscreen Window Dimensions
            win_w = max(640, self.video_container.winfo_width())
            win_h = max(480, self.video_container.winfo_height())

            # Maintain aspect ratio
            img_aspect = float(w) / float(h)
            win_aspect = float(win_w) / float(win_h)

            if win_aspect > img_aspect:
                target_h = win_h
                target_w = int(win_h * img_aspect)
            else:
                target_w = win_w
                target_h = int(win_w / img_aspect)

            scaled_frame = cv2.resize(disp_frame, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
            rgb_frame = cv2.cvtColor(scaled_frame, cv2.COLOR_BGR2RGB)

            img_pil = Image.fromarray(rgb_frame)
            img_tk = ImageTk.PhotoImage(image=img_pil)

            self.video_label.img_tk = img_tk
            self.video_label.config(image=img_tk)

        self.root.after(33, self.update_video_stream)

    def trigger_scan_and_read(self):
        """Runs page capture, OCR, translation, and sentence-by-sentence reading."""
        if self.is_reading:
            return

        threading.Thread(target=self._run_scan_pipeline, daemon=True).start()

    def _run_scan_pipeline(self):
        self.status_badge.config(text="● PROCESSING", fg="#F59E0B")
        self.subtitle_lbl.config(text="📸 Capturing high-resolution page & extracting text...", fg="#F59E0B")

        # 1. Capture High-Res Image
        high_res = self.camera.capture_page()
        if high_res is None:
            self.status_badge.config(text="● CAMERA ERROR", fg="#EF4444")
            self.subtitle_lbl.config(text="Camera capture failed. Please check connection.", fg="#EF4444")
            return

        # 2. Preprocess Page
        processed = self.processor.process_captured_page(high_res)

        # 3. Multilingual OCR
        ocr_res = self.ocr.extract_text(processed["enhanced"], target_lang=self.preferred_lang)
        raw_text = ocr_res.get("text", "").strip()

        if not raw_text:
            self.status_badge.config(text="● NO TEXT", fg="#EF4444")
            self.subtitle_lbl.config(text="No legible text detected. Ensure book page is aligned under light.", fg="#EF4444")
            self.speech.speak("Could not detect legible text. Please align the book page.", blocking=False)
            return

        # 4. Language Detection
        detected = self.lang_detector.detect_language(raw_text)
        src_lang = detected["lang"]

        # 5. Translation Determination
        if self.reading_mode == config.READING_MODE_ORIGINAL or src_lang == self.preferred_lang:
            display_sentences = list(ocr_res["sentences"])
            target_speak_lang = src_lang
        else:
            self.subtitle_lbl.config(text=f"🌐 Translating {detected['name']} → {config.SUPPORTED_LANGUAGES[self.preferred_lang]['name']}...", fg="#38BDF8")
            display_sentences = self.translator.translate_sentences(
                ocr_res["sentences"],
                source_lang=src_lang,
                target_lang=self.preferred_lang,
                mode=self.reading_mode
            )
            target_speak_lang = self.preferred_lang

        self.current_sentences = display_sentences
        self.current_sentence_idx = 0
        self.is_reading = True
        self.pause_requested = False
        self.status_badge.config(text="● READING", fg="#10B981")

        # 6. Audio Playback Loop with Live Subtitles
        for idx, sentence in enumerate(self.current_sentences):
            if not self.is_reading or not self.running:
                break

            while self.pause_requested and self.is_reading:
                time.sleep(0.15)

            self.current_sentence_idx = idx
            self.current_speaking_sentence = sentence
            self.subtitle_lbl.config(
                text=f"[{idx + 1}/{len(self.current_sentences)}] {sentence}",
                fg="#FBBF24"
            )

            self.speech.speak(sentence, lang=target_speak_lang, blocking=True)

        self.is_reading = False
        self.current_speaking_sentence = ""
        self.status_badge.config(text="● READY", fg="#10B981")
        self.subtitle_lbl.config(text="✓ Finished reading page. Turn page and press Space to read next.", fg="#10B981")

    def toggle_pause(self):
        if not self.is_reading:
            return
        self.pause_requested = not self.pause_requested
        if self.pause_requested:
            self.speech.stop()
            self.status_badge.config(text="● PAUSED", fg="#F59E0B")
            self.subtitle_lbl.config(text="⏸ Reading Paused. Press P or Space to resume.", fg="#F59E0B")
        else:
            self.status_badge.config(text="● READING", fg="#10B981")

    def next_sentence(self):
        if self.is_reading:
            self.speech.stop()
            self.current_sentence_idx += 1

    def repeat_sentence(self):
        if self.is_reading:
            self.speech.stop()
            self.current_sentence_idx = max(0, self.current_sentence_idx - 1)

    def volume_up(self):
        self.speech.increase_volume()
        self.subtitle_lbl.config(text=f"🔊 Volume: {self.speech.volume}%", fg="#38BDF8")

    def volume_down(self):
        self.speech.decrease_volume()
        self.subtitle_lbl.config(text=f"🔉 Volume: {self.speech.volume}%", fg="#38BDF8")

    def on_close(self):
        self.running = False
        self.is_reading = False
        self.speech.stop()
        self.camera.release()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = VisionVoiceFullscreenGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
