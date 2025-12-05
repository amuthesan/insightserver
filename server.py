# --- ADD AT THE VERY TOP ---
from gevent import monkey
monkey.patch_all()

import serial
import time
import threading 
import json
import socket
import struct
from flask import Flask, render_template, Response, request, jsonify
from flask_socketio import SocketIO

import subprocess
import atexit
import signal
import os

# --- Hardware Imports (Mockable) ---
try:
    from gpiozero import AngularServo
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    print("⚠️ gpiozero not found. Servo control will be disabled.")

# --- Configuration ---
CONFIG_FILE = 'config.json'
DEFAULT_CONFIG = {"camera_mode": "siyi"}

# Rover Config
SERIAL_PORT = '/dev/ttyS0' 
BAUD_RATE = 115200

# Gimbal Config (SIYI)
GIMBAL_IP = '192.168.144.25'
GIMBAL_PORT = 37260

# Camera Config
CAMERA_RTSP_URL = 'rtsp://192.168.144.25:8554/main.264'

# Servo Config (Pi Cam Tilt)
SERVO_PIN = 18

# --- GStreamer Commands ---
def get_gstreamer_command(mode):
    if mode == 'siyi':
        return [
            'gst-launch-1.0',
            'rtspsrc', f'location={CAMERA_RTSP_URL}', 'latency=0', 'tcp-timeout=5000000',
            '!', 'rtph264depay',
            '!', 'h264parse',
            '!', 'v4l2h264dec',
            '!', 'videoscale',
            '!', 'video/x-raw,width=640,height=360',
            '!', 'v4l2jpegenc',
            '!', 'multipartmux', 'boundary=--frame',
            '!', 'fdsink', 'fd=1'
        ]
    elif mode == 'picam':
        # Using libcamerasrc for modern Pi OS (Pi Cam 3)
        return [
            'gst-launch-1.0',
            'libcamerasrc',
            '!', 'video/x-raw,width=640,height=360,framerate=30/1,format=NV12',
            '!', 'videoconvert',
            '!', 'jpegenc',
            '!', 'multipartmux', 'boundary=--frame',
            '!', 'fdsink', 'fd=1'
        ]
    return []

# --- Global Objects ---
app = Flask(__name__)
socketio = SocketIO(app, async_mode='gevent') 
ser = None
gimbal = None
stream_process = None
connected_clients_count = 0
servo = None
config = {}

# --- Config Management ---
def load_config():
    global config
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
        except:
            config = DEFAULT_CONFIG.copy()
    else:
        config = DEFAULT_CONFIG.copy()
    print(f"Loaded Config: {config}")

def save_config():
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)

# --- Servo Setup ---
def init_servo():
    global servo
    if GPIO_AVAILABLE and config.get('camera_mode') == 'picam':
        try:
            # Standard servo range: -90 to 90 degrees
            servo = AngularServo(SERVO_PIN, min_angle=-90, max_angle=90)
            print(f"✅ Servo initialized on GPIO {SERVO_PIN}")
        except Exception as e:
            print(f"🛑 Error initializing servo: {e}")
            servo = None
    else:
        if servo:
            servo.close()
            servo = None

# --- SIYI TCP Protocol ---
class SiyiTCPProtocol:
    CRC16_TAB = [
        0x0, 0x1021, 0x2042, 0x3063, 0x4084, 0x50a5, 0x60c6, 0x70e7,
        0x8108, 0x9129, 0xa14a, 0xb16b, 0xc18c, 0xd1ad, 0xe1ce, 0xf1ef,
        0x1231, 0x210, 0x3273, 0x2252, 0x52b5, 0x4294, 0x72f7, 0x62d6,
        0x9339, 0x8318, 0xb37b, 0xa35a, 0xd3bd, 0xc39c, 0xf3ff, 0xe3de,
        0x2462, 0x3443, 0x420, 0x1401, 0x64e6, 0x74c7, 0x44a4, 0x5485,
        0xa56a, 0xb54b, 0x8528, 0x9509, 0xe5ee, 0xf5cf, 0xc5ac, 0xd58d,
        0x3653, 0x2672, 0x1611, 0x630, 0x76d7, 0x66f6, 0x5695, 0x46b4,
        0xb75b, 0xa77a, 0x9719, 0x8738, 0xf7df, 0xe7fe, 0xd79d, 0xc7bc,
        0x48c4, 0x58e5, 0x6886, 0x78a7, 0x840, 0x1861, 0x2802, 0x3823,
        0xc9cc, 0xd9ed, 0xe98e, 0xf9af, 0x8948, 0x9969, 0xa90a, 0xb92b,
        0x5af5, 0x4ad4, 0x7ab7, 0x6a96, 0x1a71, 0xa50, 0x3a33, 0x2a12,
        0xdbfd, 0xcbdc, 0xfbbf, 0xeb9e, 0x9b79, 0x8b58, 0xbb3b, 0xab1a,
        0x6ca6, 0x7c87, 0x4ce4, 0x5cc5, 0x2c22, 0x3c03, 0xc60, 0x1c41,
        0xedae, 0xfd8f, 0xcdec, 0xddcd, 0xad2a, 0xbd0b, 0x8d68, 0x9d49,
        0x7e97, 0x6eb6, 0x5ed5, 0x4ef4, 0x3e13, 0x2e32, 0x1e51, 0xe70,
        0xff9f, 0xefbe, 0xdfdd, 0xcffc, 0xbf1b, 0xaf3a, 0x9f59, 0x8f78,
        0x9188, 0x81a9, 0xb1ca, 0xa1eb, 0xd10c, 0xc12d, 0xf14e, 0xe16f,
        0x1080, 0xa1, 0x30c2, 0x20e3, 0x5004, 0x4025, 0x7046, 0x6067,
        0x83b9, 0x9398, 0xa3fb, 0xb3da, 0xc33d, 0xd31c, 0xe37f, 0xf35e,
        0x2b1, 0x1290, 0x22f3, 0x32d2, 0x4235, 0x5214, 0x6277, 0x7256,
        0xb5ea, 0xa5cb, 0x95a8, 0x8589, 0xf56e, 0xe54f, 0xd52c, 0xc50d,
        0x34e2, 0x24c3, 0x14a0, 0x481, 0x7466, 0x6447, 0x5424, 0x4405,
        0xa7db, 0xb7fa, 0x8799, 0x97b8, 0xe75f, 0xf77e, 0xc71d, 0xd73c,
        0x26d3, 0x36f2, 0x691, 0x16b0, 0x6657, 0x7676, 0x4615, 0x5634,
        0xd94c, 0xc96d, 0xf90e, 0xe92f, 0x99c8, 0x89e9, 0xb98a, 0xa9ab,
        0x5844, 0x4865, 0x7806, 0x6827, 0x18c0, 0x8e1, 0x3882, 0x28a3,
        0xcb7d, 0xdb5c, 0xeb3f, 0xfb1e, 0x8bf9, 0x9bd8, 0xabbb, 0xbb9a,
        0x4a75, 0x5a54, 0x6a37, 0x7a16, 0xaf1, 0x1ad0, 0x2ab3, 0x3a92,
        0xfd2e, 0xed0f, 0xdd6c, 0xcd4d, 0xbdca, 0xad8b, 0x9de8, 0x8dc9,
        0x7c26, 0x6c07, 0x5c64, 0x4c45, 0x3ca2, 0x2c83, 0x1ce0, 0xcc1,
        0xef1f, 0xff3e, 0xcf5d, 0xdf7c, 0xaf9b, 0xbfba, 0x8fd9, 0x9ff8,
        0x6e17, 0x7e36, 0x4e55, 0x5e74, 0x2e93, 0x3eb2, 0xed1, 0x1ef0
    ]

    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.sock = None
        self.seq = 0
        self.lock = threading.Lock() 
        self.is_recording = False # Internal state tracker

    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.ip, self.port))
            self.sock.settimeout(2.0)
            print(f"✅ Connected to gimbal at {self.ip}:{self.port}")
            return True
        except Exception as e:
            print(f"🛑 Error connecting to gimbal: {e}")
            return False

    def _crc16(self, data):
        crc = 0
        for byte in data:
            temp = (crc >> 8) & 0xFF
            oldcrc16 = self.CRC16_TAB[byte ^ temp]
            crc = (crc << 8) ^ oldcrc16
        return crc & 0xFFFF

    def _get_seq(self):
        with self.lock:
            self.seq = (self.seq + 1) % 65536
            return self.seq

    def _build_packet(self, cmd_id, data):
        stx = b'\x55\x66'
        ctrl = b'\x00'
        data_len = struct.pack('<H', len(data))
        seq = struct.pack('<H', self._get_seq())
        cmd = struct.pack('B', cmd_id)
        packet_no_crc = stx + ctrl + data_len + seq + cmd + data
        crc = struct.pack('<H', self._crc16(packet_no_crc))
        return packet_no_crc + crc

    def send(self, packet):
        try:
            with self.lock:
                self.sock.sendall(packet)
        except Exception as e:
            print(f"Error sending packet: {e}")

    def send_heartbeat(self):
        heartbeat_packet = b'\x55\x66\x01\x01\x00\x00\x00\x00\x00\x59\x8B'
        self.send(heartbeat_packet)

    def send_gimbal_speed(self, yaw_speed, pitch_speed):
        data = struct.pack('<bb', yaw_speed, pitch_speed)
        packet = self._build_packet(0x07, data)
        self.send(packet)
    
    def toggle_recording(self):
        """Sends Command 0x0C with payload 0x02 to toggle video recording."""
        try:
            cmd_id = 0x0C
            data = struct.pack('B', 0x02) # Payload 0x02 = Toggle Record
            packet = self._build_packet(cmd_id, data)
            self.send(packet)
            
            self.is_recording = not self.is_recording
            status = "STARTED" if self.is_recording else "STOPPED"
            print(f"🎥 Camera recording {status}")
        except Exception as e:
            print(f"Error toggling recording: {e}")

    def request_attitude_stream(self):
        data_type = 1
        data_freq = 5
        data = struct.pack('<BB', data_type, data_freq)
        packet = self._build_packet(0x25, data)
        self.send(packet)
        print("Requested 20Hz gimbal attitude stream.")

    def receive_loop(self):
        buffer = b''
        while True:
            try:
                data = self.sock.recv(1024)
                if not data:
                    print("Gimbal disconnected.")
                    break
                buffer += data
                while len(buffer) > 10: 
                    if buffer[0:2] == b'\x55\x66':
                        data_len = struct.unpack('<H', buffer[3:5])[0]
                        packet_len = 10 + data_len
                        if len(buffer) >= packet_len:
                            packet = buffer[0:packet_len]
                            self.parse_packet(packet)
                            buffer = buffer[packet_len:]
                        else:
                            break
                    else:
                        buffer = buffer[1:]
            except socket.timeout:
                continue
            except Exception as e:
                print(f"Error in gimbal receive loop: {e}")
                break

    def parse_packet(self, packet):
        cmd_id = packet[7]
        data_len = struct.unpack('<H', packet[3:5])[0]
        data = packet[8:8 + data_len]
        if cmd_id == 0x0D and data_len >= 6:
            yaw_raw, pitch_raw, roll_raw = struct.unpack('<hhh', data[0:6])
            socketio.emit('gimbal_attitude', {
                'pitch': pitch_raw / 10.0,
                'roll': roll_raw / 10.0,
                'yaw': yaw_raw / 10.0
            })

# --- Background Threads ---
def heartbeat_loop(gimbal_obj):
    while True:
        try:
            gimbal_obj.send_heartbeat()
            socketio.sleep(2) 
        except Exception as e:
            break

def read_serial_thread():
    global ser
    buffer = ""
    while True:
        if ser:
            try:
                byte_in = ser.read(1)
                if byte_in:
                    try:
                        char_in = byte_in.decode('utf-8')
                        if char_in == '{': buffer = '{'
                        elif buffer:
                            buffer += char_in
                            if char_in == '}':
                                try:
                                    data = json.loads(buffer)
                                    if data.get("T") == 1001:
                                        roll = data.get("r", 0.0)
                                        pitch = data.get("p", 0.0)
                                        voltage = data.get("v", 0.0)
                                        percent = max(0, min(100, ((voltage - 10.5) / 2.1) * 100))
                                        socketio.emit('imu_data', {
                                            'roll': roll,
                                            'pitch': pitch,
                                            'voltage': voltage,
                                            'battery_percent': percent
                                        })
                                    buffer = ""
                                except json.JSONDecodeError: buffer = "" 
                    except UnicodeDecodeError: buffer = ""
            except Exception:
                ser.close()
                ser = None
        else:
            socketio.sleep(2) 
            init_serial()

def init_serial():
    global ser
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        print(f"✅ Opened rover serial port {SERIAL_PORT}.")
        return True
    except Exception as e:
        print(f"🛑 Error opening serial port: {e}")
        return False

# --- GStreamer ---
def start_streamer():
    global stream_process
    
    # Stop existing stream if any
    if stream_process:
        stream_process.terminate()
        stream_process.wait()
        stream_process = None

    mode = config.get('camera_mode', 'siyi')
    command = get_gstreamer_command(mode)
    print(f"Starting GStreamer in [{mode}] mode...")
    
    try:
        stream_process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=10**8)
        print(f"GStreamer started PID: {stream_process.pid}")
        def log_errors():
            if stream_process and stream_process.stderr:
                for line in stream_process.stderr: print(f"[gst] {line.decode().strip()}")
        socketio.start_background_task(log_errors)
    except Exception as e:
        print(f"🛑 GStreamer failed: {e}")

def generate_frames():
    global stream_process
    if not stream_process: return
    try:
        while True:
            chunk = stream_process.stdout.read(4096)
            if not chunk: break
            yield chunk
    except Exception: pass

# --- Routes & Events ---
@app.route('/')
def index(): return render_template('dashboard.html')

@app.route('/config')
def config_page():
    return render_template('config.html', mode=config.get('camera_mode', 'siyi'))

@app.route('/api/config', methods=['POST'])
def update_config():
    data = request.json
    if 'camera_mode' in data:
        config['camera_mode'] = data['camera_mode']
        save_config()
        
        # Re-init hardware based on new config
        init_servo()
        start_streamer()
        
        return jsonify({"status": "ok", "mode": config['camera_mode']})
    return jsonify({"status": "error"}), 400

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=--frame')

@app.route('/joystick_debug')
def joystick_debug():
    return render_template('joystick_debug.html')

@socketio.on('connect')
def handle_connect():
    global connected_clients_count, ser
    connected_clients_count += 1
    if ser:
        socketio.emit('serial_status', {'status': 'connected'})
        if connected_clients_count == 1:
            try: ser.write(b'{"T": 131, "cmd": 1}\n')
            except: pass
    else:
        socketio.emit('serial_status', {'status': 'disconnected'})

@socketio.on('disconnect')
def handle_disconnect():
    global connected_clients_count, ser, gimbal
    connected_clients_count -= 1
    if connected_clients_count == 0:
        if ser:
            try: ser.write(b'{"T": 131, "cmd": 0}\n')
            except: pass
        if gimbal:
            try: gimbal.send_gimbal_speed(0, 0)
            except: pass

@socketio.on('control')
def handle_control(data):
    global ser
    if ser:
        try:
            cmd = json.dumps({"T": 1, "L": data['L'], "R": data['R']}) + '\n'
            ser.write(cmd.encode('utf-8'))
        except: pass

@socketio.on('joystick_command')
def handle_joystick(data):
    global gimbal, servo
    mode = config.get('camera_mode', 'siyi')
    
    yaw_val = data.get('yaw', 0.0)
    pitch_val = data.get('pitch', 0.0)

    if mode == 'siyi' and gimbal:
        try:
            gimbal.send_gimbal_speed(int(yaw_val*100), int(pitch_val*100))
        except: pass
        
    elif mode == 'picam' and servo:
        # Map pitch (-1.0 to 1.0) to servo angle (-90 to 90)
        # Invert pitch if needed based on mechanical setup
        angle = pitch_val * 90 
        try:
            servo.angle = angle
        except: pass

@socketio.on('set_arm_state')
def handle_arm_state(data):
    global gimbal
    if not gimbal: return
    is_armed = data.get('state', False)
    
    # Auto-Recording Logic (Only for SIYI for now)
    if is_armed and not gimbal.is_recording:
        print("ARMED: Starting Recording")
        gimbal.toggle_recording()
    elif not is_armed and gimbal.is_recording:
        print("DISARMED: Stopping Recording")
        gimbal.toggle_recording()

def cleanup():
    global ser, gimbal, stream_process, servo
    if stream_process: stream_process.terminate()
    if ser: ser.write(b'{"T": 131, "cmd": 0}\n')
    if gimbal: gimbal.send_gimbal_speed(0, 0)
    if servo: servo.close()

    print("🚀 Server started at http://0.0.0.0:5000")
    socketio.run(app, host='0.0.0.0', port=5000)

# --- System Monitoring ---
def get_cpu_temp():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            temp = float(f.read()) / 1000.0
            return temp
    except:
        return 0.0 # Fallback/Mock

def system_monitor_thread():
    while True:
        temp = get_cpu_temp()
        socketio.emit('system_data', {'cpu_temp': temp})
        socketio.sleep(2)

if __name__ == '__main__':
    atexit.register(cleanup)
    signal.signal(signal.SIGTERM, lambda s, f: cleanup())
    
    load_config()
    init_servo()
    
    if init_serial():
        socketio.start_background_task(read_serial_thread)
    
    socketio.start_background_task(system_monitor_thread) # Start monitoring
    
    try:
        gimbal = SiyiTCPProtocol(GIMBAL_IP, GIMBAL_PORT)
        if gimbal.connect():
            gimbal.request_attitude_stream()
            socketio.start_background_task(gimbal.receive_loop)
            socketio.start_background_task(heartbeat_loop, gimbal)
    except: gimbal = None

    start_streamer()
    print("🚀 Server started at http://0.0.0.0:5000")
    socketio.run(app, host='0.0.0.0', port=5000)