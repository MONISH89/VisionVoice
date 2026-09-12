import os
import sys

# Base Directory Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
BOOKS_DIR = os.path.join(DATA_DIR, "books")
SESSIONS_DIR = os.path.join(DATA_DIR, "sessions")
CAPTURES_DIR = os.path.join(BASE_DIR, "captures")
LOGS_DIR = os.path.join(BASE_DIR, "logs")

DEBUG_DIR = os.path.join(BASE_DIR, "debug")

# Ensure required directories exist
for directory in [DATA_DIR, BOOKS_DIR, SESSIONS_DIR, CAPTURES_DIR, LOGS_DIR, DEBUG_DIR]:
    os.makedirs(directory, exist_ok=True)

# Application Information
APP_NAME = "VisionVoice"
VERSION = "1.0.0"

# Supported Languages Mapping
# Format: code -> { name, tesseract_lang, tts_lang, speech_rec_lang, keywords }
SUPPORTED_LANGUAGES = {
    "en": {
        "name": "English",
        "tesseract": "eng",
        "tts": "en",
        "speech_rec": "en-US",
        "keywords": ["english", "eng"]
    },
    "ta": {
        "name": "Tamil",
        "tesseract": "tam",
        "tts": "ta",
        "speech_rec": "ta-IN",
        "keywords": ["tamil", "tam"]
    },
    "kn": {
        "name": "Kannada",
        "tesseract": "kan",
        "tts": "kn",
        "speech_rec": "kn-IN",
        "keywords": ["kannada", "kan"]
    },
    "te": {
        "name": "Telugu",
        "tesseract": "tel",
        "tts": "te",
        "speech_rec": "te-IN",
        "keywords": ["telugu", "tel"]
    },
    "ml": {
        "name": "Malayalam",
        "tesseract": "mal",
        "tts": "ml",
        "speech_rec": "ml-IN",
        "keywords": ["malayalam", "mal"]
    },
    "hi": {
        "name": "Hindi",
        "tesseract": "hin",
        "tts": "hi",
        "speech_rec": "hi-IN",
        "keywords": ["hindi", "hin"]
    }
}

DEFAULT_LANGUAGE = "en"

# Reading Mode Constants
READING_MODE_ORIGINAL = "original"
READING_MODE_PREFERRED = "preferred"

# Camera & Vision Settings
CAMERA_INDEX = 0
CAPTURE_RESOLUTION = (1920, 1080)   # High resolution for OCR capture
PREVIEW_RESOLUTION = (640, 480)     # Low resolution for real-time alignment
CAMERA_FPS = 30

# Page Alignment ROI (Region of Interest - box in normalized coordinates 0.0 - 1.0)
ROI_MARGIN_X = 0.12   # 12% margin left & right
ROI_MARGIN_Y = 0.10   # 10% margin top & bottom
ROI_TARGET_ASPECT = 1.414  # Standard book/A4 page aspect ratio height/width

# Alignment Tolerance Thresholds
ALIGNMENT_CENTER_TOLERANCE_X = 0.10  # Max center offset X fraction
ALIGNMENT_CENTER_TOLERANCE_Y = 0.12  # Max center offset Y fraction
ALIGNMENT_MIN_AREA_RATIO = 0.25      # Page must occupy at least 25% of frame
ALIGNMENT_MAX_AREA_RATIO = 0.85      # Page must occupy at most 85% of frame
ALIGNMENT_MAX_TILT_ANGLE = 12.0      # Max degrees rotation allowed

# Stability & Auto-Capture Thresholds
STABILITY_FRAMES_REQUIRED = 5       # Consecutive stable frames before auto-capture
MOTION_PIXEL_THRESHOLD = 15.0        # Mean pixel change threshold for motion
GUIDANCE_COOLDOWN_SEC = 3.5          # Minimum seconds between spoken directional guidance
ALIGNMENT_TIMEOUT_SEC = 30.0         # Max seconds to wait for alignment before reverting to standby
MAX_CAMERA_READ_RETRIES = 10         # Max consecutive camera frame read retries before error state
MAX_OCR_RETRIES = 3                  # Max OCR attempts on empty/illegible page before reverting to standby
PROMPT_LISTEN_TIMEOUT_SEC = 7.0      # Max seconds to wait for user voice response to setup prompts
MAX_TTS_PLAYBACK_TIMEOUT_SEC = 60.0  # Max seconds before terminating stuck audio playback process

# Audio & ALSA Hardware Settings (USB PnP Sound Device)
ALSA_CARD_INDEX = 3
ALSA_PLAYBACK_DEVICE = "plughw:3,0"    # Explicit hardware routing: Card 3, Device 0
MIC_DEVICE_INDEX = 2                 # Detected USB PnP Sound Device: Audio (hw:3,0) index 2
DEFAULT_VOLUME = 80                  # Range 0 to 100
VOLUME_STEP = 10                     # Volume change step
TTS_SPEECH_RATE = 1.0                # 1.0 standard speed

# Voice Commands
WAKE_WORD_PHRASES = ["hey visionvoice", "hey vision voice", "vision voice", "visionvoice"]
CMD_START_READING = ["start reading", "start", "read"]
CMD_STOP_READING = ["stop reading", "stop", "pause"]
CMD_NEXT_SENTENCE = ["next sentence", "next", "skip sentence", "skip"]
CMD_REPEAT = ["repeat sentence", "repeat", "say again", "again"]
CMD_REPEAT_FROM_BEGINNING = ["repeat from beginning", "restart", "start from beginning"]
CMD_CONTINUE_READING = ["continue reading", "continue", "resume"]
CMD_INCREASE_VOLUME = ["increase volume", "volume up", "louder"]
CMD_DECREASE_VOLUME = ["decrease volume", "volume down", "quieter"]

# GPIO Pins (Raspberry Pi - BCM Numbering)
# Hardware Prototype Pinout:
# GPIO17 -> Main / Interaction button
# GPIO27 -> Volume UP button
# GPIO22 -> Volume DOWN button
# GPIO24 -> Status LED
PIN_MAIN_BTN = 17        # Physical Main / Interaction button pin (BCM GPIO17)
PIN_POWER_BTN = 17       # Alias for backward compatibility
PIN_VOL_UP_BTN = 27      # Physical Volume Up button pin (BCM GPIO27)
PIN_VOL_DOWN_BTN = 22    # Physical Volume Down button pin (BCM GPIO22)
PIN_STATUS_LED = 24      # System Status LED pin (BCM GPIO24)

# Development & Fallback Controls
SHOW_DEV_PREVIEW = False     # Set to True to display OpenCV window on desktop
LOG_LEVEL = "INFO"
