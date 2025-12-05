#!/bin/bash

# Insight Server Control System - Update Script
# This script pulls the latest code and updates dependencies.

set -e # Exit on error

echo "=================================================="
echo "   Insight Server Update Utility"
echo "=================================================="

PROJECT_DIR=$(pwd)
VENV_DIR="$PROJECT_DIR/venv"

# 1. Pull Latest Code
echo "[1/3] Pulling latest changes from git..."
git pull

# 2. Update Dependencies
echo "[2/3] Updating system dependencies..."
sudo apt install -y libcamera-tools gstreamer1.0-libcamera python3-lgpio

echo "[2.5/3] Updating Python dependencies..."
if [ -d "$VENV_DIR" ]; then
    source "$VENV_DIR/bin/activate"
    pip install -r requirements.txt
else
    echo "Warning: Virtual environment not found at $VENV_DIR"
    echo "Skipping dependency update."
fi

# 3. Restart Service
echo "[3/3] Restarting service..."
if systemctl is-active --quiet insight-server; then
    sudo systemctl restart insight-server
    echo "Service restarted successfully."
else
    echo "Service 'insight-server' is not running or not installed."
    echo "You may need to run ./install.sh first."
fi

echo ""
echo "=================================================="
echo "   Update Complete!"
echo "=================================================="
