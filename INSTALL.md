# Installation Guide

This guide details the steps to install and configure the Insight Server Control System on a fresh Raspberry Pi OS installation.

## Quick Install (Automated)

The easiest way to install is using the provided script. This handles dependencies, configuration, and service setup automatically.

1.  **Clone the Repository**:
    ```bash
    git clone https://github.com/amuthesan/insightserver.git fpv_control
    cd fpv_control
    ```

2.  **Run the Installer**:
    ```bash
    ./install.sh
    ```

3.  **Reboot**:
    ```bash
    sudo reboot
    ```

## Updating

To update the system to the latest version:

1.  **Run the Update Script**:
    ```bash
    cd fpv_control
    ./update.sh
    ```
    This will pull the latest code, update dependencies, and restart the service.

---

## Manual Installation

If you prefer to install manually, follow the steps below.

## 1. OS Setup

1.  **Flash Raspberry Pi OS**:
    - Download and flash **Raspberry Pi OS (Legacy, 64-bit) Lite** or **Standard** to your SD card.
    - *Note: The "Lite" version is recommended for headless operation.*

2.  **Enable SSH & WiFi**:
    - Configure SSH and WiFi settings in the Raspberry Pi Imager before flashing, or add a `wpa_supplicant.conf` and empty `ssh` file to the boot partition.

3.  **Update System**:
    ```bash
    sudo apt update && sudo apt upgrade -y
    ```

## 2. System Configuration

### Enable UART (For Rover Control)
The rover control uses the serial port (`/dev/ttyS0` or `/dev/serial0`).

1.  Open boot configuration:
    ```bash
    sudo raspi-config
    ```
2.  Navigate to **Interface Options** -> **Serial Port**.
3.  **Login Shell**: Select **No**.
4.  **Serial Port Hardware**: Select **Yes**.
5.  Finish and Reboot.

### Install System Dependencies
Install GStreamer and other required tools.

```bash
sudo apt install -y python3-pip python3-venv git \
    gstreamer1.0-tools gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav gstreamer1.0-plugins-rtp \
    v4l-utils
```

## 3. Project Setup

1.  **Clone the Repository**:
    ```bash
    git clone <your-repo-url> fpv_control
    cd fpv_control
    ```

2.  **Create Virtual Environment**:
    It is best practice to use a virtual environment.
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install Python Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Download Static Assets**:
    Ensure the static assets are present (they should be in the repo, but if not):
    ```bash
    # Tailwind CSS
    curl -L -o static/tailwind.js https://cdn.tailwindcss.com
    
    # Socket.IO
    curl -o static/socket.io.js https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.5/socket.io.min.js
    ```

## 4. Running the Application

1.  **Manual Start**:
    ```bash
    source venv/bin/activate
    sudo python server.py
    ```
    *Note: `sudo` might be required to access the serial port if your user is not in the `dialout` group.*

2.  **Access the Dashboard**:
    Open a web browser and navigate to:
    `http://<raspberry-pi-ip>:5000`

## 5. Auto-Start Service (Optional)

To run the application automatically on boot:

1.  **Create Service File**:
    ```bash
    sudo nano /etc/systemd/system/fpv-control.service
    ```

2.  **Add Configuration**:
    Replace `/home/pi/fpv_control` with your actual path.
    ```ini
    [Unit]
    Description=FPV Control Server
    After=network.target

    [Service]
    User=root
    WorkingDirectory=/home/pi/fpv_control
    ExecStart=/home/pi/fpv_control/venv/bin/python /home/pi/fpv_control/server.py
    Restart=always

    [Install]
    WantedBy=multi-user.target
    ```

3.  **Enable and Start**:
    ```bash
    sudo systemctl daemon-reload
    sudo systemctl enable fpv-control
    sudo systemctl start fpv-control
    ```
