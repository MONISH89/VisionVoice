# VisionVoice — Smart Voice-Controlled Assistive Reading Assistant

VisionVoice is an intelligent, completely hands-free assistive reading platform designed for physical books and documents. It combines computer vision, real-time page alignment analysis, multilingual OCR, script identification, neural machine translation, text-to-speech audio synthesis, speech recognition, and persistent reading memory into a powerful, accessible reading assistant.

---

## 📸 System Architecture & Pipeline

```
                                  [ POWER ON / START ]
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
                             [ Multilingual OCR Engine ]
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
                          └────────────────┬────────────────┘
                                           │ (Page End)
                           [ "Finished reading. Turn page" ]
                                           │
                          (Camera detects page turn motion)
                                           │
                                 [ Next Page Auto-Scan ]
```

---

## 🌐 Supported Languages

VisionVoice supports 6 languages out of the box with multilingual OCR, script detection, neural translation, and TTS audio synthesis:

| Language | Code | Native Name | OCR Language | TTS Synthesis Code | Speech Recognition |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **English** | `en` | English | `eng` | `en` | `en-US` |
| **Tamil** | `ta` | தமிழ் | `tam` | `ta` | `ta-IN` |
| **Hindi** | `hi` | हिन्दी | `hin` | `hi` | `hi-IN` |
| **Kannada** | `kn` | ಕನ್ನಡ | `kan` | `kn` | `kn-IN` |
| **Telugu** | `te` | తెలుగు | `tel` | `te` | `te-IN` |
| **Malayalam** | `ml` | മലയാളം | `mal` | `ml` | `ml-IN` |

---

## ⚡ Deploying to Vercel (Fast & Serverless)

VisionVoice is fully optimized for **1-click serverless deployment on Vercel** with maximum edge efficiency, zero cold-start latency, and browser webcam/mic capabilities!

### Option 1: Deploy with Vercel CLI (Fastest)

```bash
# 1. Install Vercel CLI globally (if not already installed)
npm install -g vercel

# 2. Deploy directly from project directory
vercel --prod
```

### Option 2: Deploy via GitHub / Vercel Dashboard

1. Push this repository to **GitHub** (or GitLab / Bitbucket).
2. Go to [vercel.com/new](https://vercel.com/new) and import your repository.
3. Vercel automatically detects `vercel.json`, `api/index.py`, and `requirements.txt`.
4. Click **Deploy**. Your VisionVoice web command center is live in ~20 seconds!

### ✨ Vercel Serverless Features

| Feature | Cloud & Browser Implementation |
| :--- | :--- |
| **Edge API Backend** | FastAPI ASGI handler in `api/index.py` (< 20ms response time) |
| **Device Camera / Webcam** | Direct WebRTC `navigator.mediaDevices.getUserMedia` with HUD bounding box |
| **Instant Photo Upload** | Drag & drop book photos or use mobile camera roll for scanning |
| **Multilingual Translation** | Neural Google Translate API across EN, TA, HI, KN, TE, ML |
| **Audio Speech Synthesis** | High-fidelity in-browser Web Speech API + Cloud MP3 audio stream |
| **Hands-Free Mic Control** | Live speech recognition (`webkitSpeechRecognition`) in any browser |
| **Book Memory Persistence** | Auto-synchronized `localStorage` + Serverless session bookmarks |

---

## 🖥️ Local Installation & Running

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Launch Real-Time Web Command Center
```bash
python3 dashboard_server.py
```
Open **`http://localhost:8050`** in any web browser.

### 3. Run Automated Unit Test Suite
```bash
python3 -m unittest test_suite.py
```

### 4. Run Demonstration Showcase
```bash
python3 demo.py
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
├── api/
│   └── index.py           # Vercel Serverless FastAPI API entrypoint
├── web/
│   ├── index.html         # Web Command Center dashboard
│   ├── css/
│   │   └── dashboard.css  # Dark glassmorphic design system
│   └── js/
│       └── dashboard.js   # Real-time WebRTC webcam, audio, & telemetry logic
│
├── main.py                # Finite State Machine master controller
├── config.py              # Central application configuration
├── camera.py              # Camera stream manager
├── alignment.py           # Real-time page alignment with spoken guidance
├── page_processor.py      # 4-corner unwarp & CLAHE OCR enhancement
├── ocr.py                 # Multilingual OCR extraction engine
├── language.py            # Automatic Unicode script detection
├── translator.py          # Original vs Preferred language translation
├── speech.py              # Multilingual Text-to-Speech & sentence queue
├── voice_control.py       # Wake-word & speech recognition listener
├── memory.py              # Book signature fingerprinting & reading progress
│
├── vercel.json            # Vercel serverless routing and edge CDN config
├── .vercelignore          # Exclusions for ultra-fast Vercel deployment
├── requirements.txt       # Python package dependencies
├── test_suite.py          # Automated unit test suite
└── demo.py                # Demonstration script
```

---

## 📄 License
MIT License. Built for hands-free assistive reading.
