#!/bin/bash

# Insight Server Diagnostic Tool
# Checks for camera detection and GStreamer plugins.

echo "=================================================="
echo "   Insight Server Diagnostics"
echo "=================================================="

echo ""
echo "[1/4] Checking for libcamera devices..."
if command -v libcamera-hello &> /dev/null; then
    libcamera-hello --list-cameras
else
    echo "⚠️ libcamera-hello not found. Is libcamera-tools installed?"
fi

echo ""
echo "[2/4] Checking GStreamer libcamerasrc..."
if gst-inspect-1.0 libcamerasrc &> /dev/null; then
    echo "✅ libcamerasrc plugin found."
else
    echo "🛑 libcamerasrc plugin NOT found!"
fi

echo ""
echo "[3/4] Checking Service Status..."
systemctl status insight-server --no-pager

echo ""
echo "[4/4] Last 50 lines of server.log..."
if [ -f "server.log" ]; then
    tail -n 50 server.log
else
    echo "⚠️ server.log not found."
fi

echo ""
echo "=================================================="
echo "   Diagnostics Complete"
echo "=================================================="
