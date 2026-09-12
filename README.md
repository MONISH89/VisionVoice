# VisionVoice — Smart Voice-Controlled Assistive Reading Assistant

VisionVoice is an intelligent, completely hands-free assistive reading device designed for physical books. It combines computer vision, real-time page alignment analysis, multilingual OCR, script identification, machine translation, text-to-speech, speech recognition, and persistent reading memory into a standalone, voice-operated reading device.

---

## 📸 System Architecture & Pipeline

```
                                  [ POWER ON ]
                                       │
                             [ WAIT "Hey VisionVoice" ]
                                       │
                         [ PROMPT: Language & Mode ]
                         (EN, TA, KN, TE, ML, HI / Orig vs Trans)
                                       │
                             [ "Start Reading" ]
                                       │
                      ┌────────────────┴────────────────┐
                      │    Real-time Camera Stream      │
                      │  - Page Alignment Analyzer      │
                      │  - Spoken Direction Guidance    │
                      │  - Motion Stability Detector    │
                      └────────────────┬────────────────┘
                                       │ (Page Aligned & Stable)
                          [ Automatic High-Res Capture ]
                                       │
                      ┌────────────────┴────────────────┐
                      │    Computer Vision Pipeline     │
                      │  - 4-Corner Contour Detection   │
                      │  - Perspective Transformation   │
                      │  - Contrast & CLAHE Enhancement │
                      └────────────────┬────────────────┘
                                       │
                         [ Multilingual Tesseract OCR ]
                                       │
                         [ Language Identification ]
                                       │
                      ┌────────────────┴────────────────┐
                      │    Translation & Book Memory    │
                      │  - Book Signature Fingerprint   │
                      │  - Restore / Create Book Record │
                      │  - Translate to Preferred Lang  │
                      └────────────────┬────────────────┘
                                       │
                      ┌────────────────┴────────────────┐
                      │    Active Reading (TTS Queue)   │
                      │  - Sentence-by-Sentence Audio   │
                      │  - Voice Controls:              │
                      │    "Stop", "Repeat", "Continue" │
                      │    "Repeat from beginning"      │
                      │    "Increase/Decrease volume"   │
                      │  - Physical Vol+/Vol- Buttons   │
                      └────────────────┬────────────────┘
                                       │ (Page End)
                       [ "Finished reading. Turn page" ]
                                       │
                      (Camera detects page turn motion)
                                       │
                             [ Next Page Auto-Scan ]
```

---

## 🛠️ Physical Prototype Hardware Specifications & Pinout

### Physical Prototype Architecture
- **Power Supply**: 2 × 3.7 V Lithium-ion batteries in series (~7.4 V nominal) → Step-down 5 V Buck Converter → 5 V Regulated Input to Raspberry Pi.
- **Main Processing Unit**: Raspberry Pi 4 Model B (Headless: no HDMI, monitor, keyboard, or mouse).
- **Camera**: Camera Module (focused on physical book stand).
- **Audio Output**: USB PnP Sound Device routed via `aplay -D plughw:3,0` (ALSA Card 3, Device 0).
- **Audio Input**: USB PnP Sound Device microphone configured via `sr.Microphone(device_index=2)` with single-owner serialized access.
- **Physical Controls**: 3 push buttons (Internal Pull-Up) & 1 Status LED.

### Raspberry Pi GPIO Pin Connections (BCM Numbering)

| Component / Function | BCM Pin | Physical Pin | Mode / Electrical Configuration |
| :--- | :--- | :--- | :--- |
| **Main / Interaction Button** | `GPIO 17` | Pin 11 | Short press = Action/Pause/Resume; Long press (>2.5s) = Safe Poweroff (Pull-Up to 3.3V) |
| **Volume Up Button** | `GPIO 27` | Pin 13 | Increases audio volume (Pull-Up to 3.3V) |
| **Volume Down Button** | `GPIO 22` | Pin 15 | Decreases audio volume (Pull-Up to 3.3V) |
| **Status LED (+)** | `GPIO 24` | Pin 18 | Current limiting resistor in series to GND (Pin 20) |
| **Common GND (-)** | `GND` | Pin 9 / 14 / 20 | Common Ground |

### Status LED (GPIO24) State Indications

| System State | Visual Indication Pattern | Meaning / Activity |
| :--- | :--- | :--- |
| `WAIT_WAKE_WORD` / `WAIT_START_READING` | **Solid ON** | Ready and waiting for user command / wake word. |
| `LISTENING` / `ASK_PREFERENCES` | **Steady Pulse (0.3s ON / 0.3s OFF)** | Actively listening for user voice response. |
| `ALIGNING_PAGE` | **Medium Blink (0.2s ON / 0.2s OFF)** | Analyzing real-time camera page alignment. |
| `PROCESSING_PAGE` | **Rapid Flash (0.07s ON / 0.07s OFF)** | Perspective unwarping & Tesseract OCR extraction. |
| `READING` | **Solid ON** | Active sentence-by-sentence TTS audio reading. |
| `ERROR` | **3 Rapid Bursts + 0.5s Pause** | System error or camera/OCR recovery warning. |

> **Note**: Fully headless operation. Status signals run strictly on physical GPIO24 without requiring an HDMI monitor, display, keyboard, or mouse.

---

## 🌐 Supported Languages

VisionVoice supports the following 6 languages out of the box with multilingual OCR, script detection, translation, and TTS audio synthesis:

| Language | Code | Tesseract OCR Lang | TTS Synthesis Code | Speech Recognition |
| :--- | :--- | :--- | :--- | :--- |
| **English** | `en` | `eng` | `en` | `en-US` |
| **Tamil** | `ta` | `tam` | `ta` | `ta-IN` |
| **Kannada** | `kn` | `kan` | `kn` | `kn-IN` |
| **Telugu** | `te` | `tel` | `te` | `te-IN` |
| **Malayalam** | `ml` | `mal` | `ml` | `ml-IN` |
| **Hindi** | `hi` | `hin` | `hi` | `hi-IN` |

---

## 🚀 Quick Start Guide

### 1. Automated Installation on Raspberry Pi
Run the automated installation script to set up all system dependencies, Tesseract Indic packs, ALSA tools, and Python packages:
```bash
git clone https://github.com/nithish/VisionVoice.git
cd VisionVoice
chmod +x setup.sh
./setup.sh
```

### 2. Manual Dependencies Installation
If installing packages manually:
```bash
sudo apt update
sudo apt install -y python3-opencv tesseract-ocr tesseract-ocr-tam tesseract-ocr-kan \
    tesseract-ocr-tel tesseract-ocr-mal tesseract-ocr-hin mpg123 sox alsa-utils espeak \
    portaudio19-dev libasound2-dev

pip3 install -r requirements.txt
```

### 3. Systemd Auto-Boot Configuration (Automatic Startup on Power-On)
To enable VisionVoice to automatically boot and run on power-on without requiring a monitor, keyboard, or mouse:
```bash
sudo systemctl daemon-reload
sudo systemctl enable visionvoice.service
sudo systemctl start visionvoice.service
```

#### Service Management & Debugging Commands:
- **Check service status**:
  ```bash
  systemctl status visionvoice.service
  ```
- **Live log stream (real-time debugging)**:
  ```bash
  journalctl -u visionvoice.service -f
  ```
- **Stop or restart service**:
  ```bash
  sudo systemctl stop visionvoice.service
  sudo systemctl restart visionvoice.service
  ```

### 4. 🌐 Real-Time Web Command Center & Telemetry Dashboard
To launch the browser-based glassmorphic dashboard featuring live camera MJPEG feed, dynamic alignment HUD, synchronized karaoke sentence reader, multilingual translation studio, book memory library, and hardware diagnostics:
```bash
python3 dashboard.py
# or
python3 main.py --dashboard
```
Access locally at **`http://localhost:8050`** or remotely across the local WiFi network at **`http://<pi_ip>:8050`**.

### 5. Master Demonstration Runner
To run the automated showcase demonstrating all 9 core subsystems end-to-end:
```bash
python3 demo.py
# Or for specific language showcase (en, ta, hi, kn, te, ml):
python3 demo.py --lang ta
```

### 6. Interactive Desktop Visual GUI Application
To run VisionVoice with a visual interface featuring a live camera alignment view, OCR text display, translation options, and on-screen controls:
```bash
python3 gui_app.py
# or
python3 main.py --gui
```

### 6. Independent Hardware Diagnostic Test Mode
To verify all physical hardware components (Camera, Microphone index 2, eSpeak-ng, ALSA `plughw:3,0`, GPIO buttons, and LED) independently without starting the main reading assistant:
```bash
python3 hardware_test.py
# or
python3 main.py --test
```

### 7. Interactive Simulation Mode (For Desktop Testing without Pi Hardware)
```bash
python3 simulate.py
```

---

## 🗣️ Voice Commands Reference

| Voice Command | Action |
| :--- | :--- |
| **"Hey VisionVoice"** | Wakes device from idle and prompts for reading preferences. |
| **"Start reading"** | Begins real-time camera alignment check and automatic page capture. |
| **"Stop reading"** | Pauses audio playback immediately and preserves current book, page, and sentence progress. |
| **"Next sentence"** / **"Skip"** | Skips immediately to the next sentence on the page. |
| **"Continue reading"** | Resumes paused reading session from exact saved position. |
| **"Repeat"** | Re-reads the current sentence. |
| **"Repeat from beginning"** | Restarts the current book from Page 1, Sentence 1. |
| **"Increase volume"** | Increases playback volume by 10%. |
| **"Decrease volume"** | Decreases playback volume by 10%. |

---

## 📂 Project Directory Structure

```
VisionVoice/
│
├── main.py                # Finite State Machine master controller
├── config.py              # Central application configuration
├── camera.py              # Picamera2 & OpenCV VideoCapture stream manager
├── alignment.py           # Real-time page alignment with spoken guidance
├── page_processor.py      # 4-corner unwarp & CLAHE OCR enhancement
├── ocr.py                 # Multilingual Tesseract OCR extraction engine
├── language.py            # Automatic Unicode script detection
├── translator.py          # Original vs Preferred language translation
├── speech.py              # Multilingual Text-to-Speech & sentence queue
├── voice_control.py       # Wake-word & speech recognition listener
├── memory.py              # Book signature fingerprinting & reading progress
├── buttons.py             # Physical GPIO button & LED indicator controller
│
├── simulate.py            # Interactive CLI hardware simulation testbench
├── test_suite.py          # Automated unit test suite
├── setup.sh               # Raspberry Pi automated installation script
├── requirements.txt       # Python package dependencies
├── visionvoice.service    # Systemd auto-boot service
│
├── data/
│   ├── books/             # Persistent JSON book records
│   └── sessions/          # Active reading session progress
│
├── captures/              # Storage for page captures & corrected images
└── logs/                  # System execution logs
```

---

## 📄 License
MIT License. Built for hands-free assistive reading.
