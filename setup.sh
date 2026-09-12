#!/usr/bin/env bash
# ==============================================================================
# VisionVoice — Automated Raspberry Pi Setup & Systemd Auto-Boot Configuration
# ==============================================================================

set -e

# Detect actual Linux user and project directory path
ACTUAL_USER="${SUDO_USER:-$USER}"
ACTUAL_GROUP="$(id -gn "$ACTUAL_USER" 2>/dev/null || echo "$ACTUAL_USER")"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VENV_DIR="$SCRIPT_DIR/.venv"

echo "=========================================================="
echo "    VisionVoice System & Auto-Boot Installation Setup"
echo "=========================================================="
echo "Target User:        $ACTUAL_USER"
echo "Target Group:       $ACTUAL_GROUP"
echo "Project Location:   $SCRIPT_DIR"
echo "Virtualenv Path:    $VENV_DIR"
echo "=========================================================="

# 1. Update APT Package Repositories
echo "[1/6] Updating APT package repositories..."
sudo apt update -y

# 2. Install System-level Computer Vision & OCR Dependencies
echo "[2/6] Installing Tesseract OCR & Indic Language Packs..."
sudo apt install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-tam \
    tesseract-ocr-kan \
    tesseract-ocr-tel \
    tesseract-ocr-mal \
    tesseract-ocr-hin

# 3. Install Audio, Multimedia Tools & Hardware Drivers (ALSA, SoX, PortAudio)
echo "[3/6] Installing Audio & Multimedia Packages..."
sudo apt install -y \
    alsa-utils \
    mpg123 \
    sox \
    libsox-fmt-all \
    espeak \
    espeak-ng \
    ffmpeg \
    portaudio19-dev \
    libasound2-dev \
    libatlas-base-dev \
    python3-venv \
    python3-pip \
    python3-numpy \
    python3-opencv \
    python3-rpi.gpio \
    python3-picamera2 || true

# Add user to required hardware groups
echo "Configuring hardware permissions for user '$ACTUAL_USER'..."
sudo usermod -a -G audio,video,gpio,i2c,spi "$ACTUAL_USER" 2>/dev/null || true

# 4. Create / Configure Python Virtual Environment
echo "[4/6] Setting up Python virtual environment at $VENV_DIR..."
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR" --system-site-packages
fi

# Upgrade pip & install Python requirements into virtual environment
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -r "$SCRIPT_DIR/requirements.txt"

# 5. Setup Project Directories and Permissions
echo "[5/6] Creating data, logs, and captures directories..."
mkdir -p "$SCRIPT_DIR/data/books"
mkdir -p "$SCRIPT_DIR/data/sessions"
mkdir -p "$SCRIPT_DIR/captures"
mkdir -p "$SCRIPT_DIR/logs"
mkdir -p "$SCRIPT_DIR/debug"

# Ensure user owns the repository files
sudo chown -R "$ACTUAL_USER:$ACTUAL_GROUP" "$SCRIPT_DIR"
chmod -R 775 "$SCRIPT_DIR"

# 6. Generate and Install Systemd Auto-Boot Service
echo "[6/6] Configuring systemd auto-boot service at /etc/systemd/system/visionvoice.service..."
SERVICE_FILE="/etc/systemd/system/visionvoice.service"

sudo bash -c "cat > '$SERVICE_FILE'" <<EOF
[Unit]
Description=VisionVoice Smart Hands-Free Assistive Reading Assistant
After=network.target sound.target alsa-restore.service systemd-udevd.service
Wants=sound.target

[Service]
Type=simple
User=$ACTUAL_USER
Group=$ACTUAL_GROUP
WorkingDirectory=$SCRIPT_DIR
ExecStart=$VENV_DIR/bin/python main.py
Restart=always
RestartSec=3s
Environment=PYTHONUNBUFFERED=1
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
echo "✓ Generated /etc/systemd/system/visionvoice.service successfully!"

echo "=========================================================="
echo "    VisionVoice Auto-Boot Service Setup Complete!"
echo "=========================================================="
echo ""
echo "To enable VisionVoice to start automatically on boot:"
echo "    sudo systemctl daemon-reload"
echo "    sudo systemctl enable visionvoice.service"
echo "    sudo systemctl start visionvoice.service"
echo ""
echo "To check service status and logs for debugging:"
echo "    systemctl status visionvoice.service"
echo "    journalctl -u visionvoice.service -f"
echo "=========================================================="
