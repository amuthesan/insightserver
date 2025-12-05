#!/bin/bash

# Insight Server Control System - Installation Script
# This script automates the setup on Raspberry Pi OS.

set -e # Exit on error

echo "=================================================="
echo "   Insight Server Control System Installer"
echo "=================================================="

# Check if running as root
if [ "$EUID" -eq 0 ]; then
  echo "Please run this script as a normal user (e.g., pi), NOT as root."
  exit 1
fi

USER_NAME=$(whoami)
USER_HOME=$(eval echo ~$USER_NAME)
PROJECT_DIR=$(pwd)
VENV_DIR="$PROJECT_DIR/venv"

echo "Installing for user: $USER_NAME"
echo "Project directory: $PROJECT_DIR"
echo ""

# 1. System Updates
echo "[1/6] Updating system packages..."
sudo apt update && sudo apt upgrade -y

# 2. Install Dependencies
echo "[2/6] Installing system dependencies..."
sudo apt install -y python3-pip python3-venv git \
    gstreamer1.0-tools gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav gstreamer1.0-plugins-rtp \
    v4l-utils libcamera-tools gstreamer1.0-libcamera

# 3. Configure UART (Raspberry Pi specific)
echo "[3/6] Configuring UART..."
# Enable hardware serial, disable console on serial
if command -v raspi-config > /dev/null; then
    sudo raspi-config nonint do_serial 2
    echo "UART configured. A reboot will be required."
else
    echo "Warning: raspi-config not found. Skipping UART configuration."
fi

# 4. Python Environment
echo "[4/6] Setting up Python environment..."
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    echo "Virtual environment created."
fi

source "$VENV_DIR/bin/activate"
pip install --upgrade pip
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    echo "Error: requirements.txt not found!"
    exit 1
fi

# 5. Download Static Assets (if missing)
echo "[5/6] Checking static assets..."
mkdir -p static
if [ ! -f "static/tailwind.js" ]; then
    echo "Downloading Tailwind CSS..."
    curl -L -o static/tailwind.js https://cdn.tailwindcss.com
fi
if [ ! -f "static/socket.io.js" ]; then
    echo "Downloading Socket.IO..."
    curl -o static/socket.io.js https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.5/socket.io.min.js
fi

# 6. Service Setup
echo "[6/6] Configuring systemd service..."
SERVICE_FILE="insight-server.service"

cat <<EOF > $SERVICE_FILE
[Unit]
Description=Insight Server Control System
After=network.target

[Service]
User=$USER_NAME
WorkingDirectory=$PROJECT_DIR
ExecStart=$VENV_DIR/bin/python $PROJECT_DIR/server.py
Restart=always
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

echo "Installing service file to /etc/systemd/system/$SERVICE_FILE..."
sudo mv $SERVICE_FILE /etc/systemd/system/$SERVICE_FILE
sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_FILE
sudo systemctl start $SERVICE_FILE

echo ""
echo "=================================================="
echo "   Installation Complete!"
echo "=================================================="
echo "The service is running. You can check status with:"
echo "  sudo systemctl status insight-server"
echo ""
echo "Access the dashboard at: http://<raspberry-pi-ip>:5000"
echo "NOTE: Please reboot your Raspberry Pi to ensure UART settings take effect."
echo "      sudo reboot"
echo "=================================================="
