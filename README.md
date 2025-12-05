# Insight Server Control System

A comprehensive control system for Insight rover, featuring real-time video streaming, gimbal control, and telemetry.

## Features

- **Flask-based Web Dashboard**: A user-friendly web interface for controlling the rover and viewing the video feed.
- **Real-time Video Streaming**: Low-latency video streaming using GStreamer (RTSP to MJPEG).
- **SIYI Gimbal Control**: Full control over SIYI gimbals using the TCP protocol (Yaw/Pitch/Roll).
- **Rover Control**: Serial communication for controlling rover movement (Left/Right motor control).
- **Joystick Support**: Integrated joystick support for intuitive gimbal control.
- **Dual Camera Support**: Switch between SIYI A8 Mini (RTSP) and Raspberry Pi Camera (CSI/USB).
- **Tilt Servo Control**: Control a tilt servo using the right joystick when in Pi Camera mode.
- **Web Configuration**: dedicated page to toggle camera modes.
- **Automatic Recording**: Starts recording on the SIYI camera when the rover is armed.
- **WebSocket Telemetry**: Real-time data for battery, attitude, and connection status.

## Getting Started

1.  **Prerequisites**:
    - Python 3.x
    - GStreamer installed on the system.
    - Required Python packages: `flask`, `flask-socketio`, `gevent`, `pyserial`.

2.  **Installation**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Running the Server**:
    ```bash
    python server.py
    ```

4.  **Accessing the Dashboard**:
    Open your web browser and navigate to `http://localhost:5000`.

## Version

Current Version: **v0.3 Beta**
