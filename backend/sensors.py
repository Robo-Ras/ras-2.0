"""
Sensores do robô
- Câmera RGB USB (Logitech C270 ou qualquer webcam UVC)
- Intel RealSense L515 (opcional, RGB + profundidade)
- LiDAR 2D: Slamtec RPLIDAR (A1/A2/C1) ou LDROBOT LD06/LD19

Convenção de ângulos do LiDAR (referencial do robô):
  0 rad = frente, positivo = esquerda (anti-horário), faixa [-pi, pi]
"""

import glob
import importlib.util
import math
import os
import sys
import sysconfig
import threading
import time

import cv2
import numpy as np
import serial
import serial.tools.list_ports

# ---------------------------------------------------------------------------
# RealSense
# ---------------------------------------------------------------------------

# O suporte ao L515 foi removido na librealsense 2.55+, então o pyrealsense2 do pip
# (2.56) não enxerga o L515. Usamos a build local 2.54 quando ela existir.
REALSENSE_BUILD_DIR = os.environ.get(
    'RAS_REALSENSE_DIR',
    os.path.expanduser('~/librealsense/build/wrappers/python'),
)


def load_pyrealsense2():
    """Importa o pyrealsense2, preferindo a build local (compatível com L515)"""
    if 'pyrealsense2' in sys.modules:
        return sys.modules['pyrealsense2']

    so_path = os.path.join(REALSENSE_BUILD_DIR, 'pyrealsense2' + sysconfig.get_config_var('EXT_SUFFIX'))
    if os.path.exists(so_path):
        spec = importlib.util.spec_from_file_location('pyrealsense2', so_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        sys.modules['pyrealsense2'] = module
        return module

    import pyrealsense2
    return pyrealsense2


# ---------------------------------------------------------------------------
# Câmeras
# ---------------------------------------------------------------------------

class CameraBase:
    """Interface comum: read() -> (imagem BGR, profundidade em metros ou None)"""

    name = 'camera'
    kind = 'none'
    has_depth = False
    hfov_deg = 60.0

    def __init__(self):
        self.online = False
        self.width = 640
        self.height = 480

    def start(self):
        raise NotImplementedError

    def read(self):
        raise NotImplementedError

    def stop(self):
        self.online = False

    def bearing_of_pixel(self, x):
        """Ângulo (rad, positivo = esquerda) de uma coluna da imagem"""
        f = (self.width / 2) / math.tan(math.radians(self.hfov_deg) / 2)
        return math.atan2((self.width / 2) - x, f)

    def deproject(self, x, y, dist):
        """Ponto 3D (X direita, Y baixo, Z frente) a partir do pixel e da distância"""
        f = (self.width / 2) / math.tan(math.radians(self.hfov_deg) / 2)
        return ((x - self.width / 2) * dist / f, (y - self.height / 2) * dist / f, dist)

    def status(self):
        return {'name': self.name, 'kind': self.kind, 'online': self.online, 'depth': self.has_depth}


def find_usb_cameras():
    """Lista webcams V4L2 como [(device, nome, 'vid:pid')], C270 primeiro"""
    cameras = []
    for path in sorted(glob.glob('/sys/class/video4linux/video*')):
        try:
            # Cada webcam cria vários /dev/videoN; só o index 0 é o de captura
            with open(os.path.join(path, 'index')) as f:
                if f.read().strip() != '0':
                    continue
            with open(os.path.join(path, 'name')) as f:
                name = f.read().strip()
            usb_dir = os.path.realpath(os.path.join(path, 'device', '..'))
            with open(os.path.join(usb_dir, 'idVendor')) as f:
                vid = f.read().strip()
            with open(os.path.join(usb_dir, 'idProduct')) as f:
                pid = f.read().strip()
        except OSError:
            continue
        if vid == '8086' or 'RealSense' in name:
            continue  # L515/D435 também aparecem como webcam; são tratadas pelo RealSenseCamera
        cameras.append(('/dev/' + os.path.basename(path), name, f'{vid}:{pid}'))

    def is_c270(cam):
        return cam[2] == '046d:0825' or 'C270' in cam[1]

    cameras.sort(key=lambda cam: not is_c270(cam))
    return cameras


class UsbCamera(CameraBase):
    """Webcam UVC via OpenCV (Logitech C270: 640x480, ~60° de campo horizontal)"""

    kind = 'usb'

    def __init__(self, device=None, width=640, height=480, fps=30, hfov_deg=60.0):
        super().__init__()
        self.device = device
        self.width = width
        self.height = height
        self.fps = fps
        self.hfov_deg = hfov_deg
        self.cap = None
        self.name = 'C270'

    def start(self):
        device = self.device
        if device is None:
            found = find_usb_cameras()
            if not found:
                print("✗ Nenhuma webcam USB encontrada")
                return False
            device, label, usb_id = found[0]
            self.name = 'C270' if usb_id == '046d:0825' or 'C270' in label else label.split(':')[0]
            print(f"  Webcam selecionada: {label} ({usb_id}) em {device}")

        self.cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
        if not self.cap.isOpened():
            print(f"✗ Não foi possível abrir a webcam {device}")
            self.cap = None
            return False

        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        ok, frame = self.cap.read()
        if not ok:
            print(f"✗ Webcam {device} abriu mas não entregou frames")
            self.stop()
            return False

        self.height, self.width = frame.shape[:2]
        self.online = True
        print(f"✓ Câmera {self.name} iniciada: {self.width}x{self.height}")
        return True

    def read(self):
        if not self.cap:
            return None, None
        ok, frame = self.cap.read()
        if not ok:
            return None, None
        return frame, None

    def stop(self):
        super().stop()
        if self.cap:
            self.cap.release()
            self.cap = None


class RealSenseCamera(CameraBase):
    """Intel RealSense L515 (ou D435) com profundidade alinhada à imagem colorida"""

    kind = 'realsense'
    has_depth = True
    hfov_deg = 70.0

    # Tentadas em ordem: (profundidade WxH, cor WxH)
    PROFILES = [((640, 480), (640, 480)), ((320, 240), (640, 480)), None]

    def __init__(self, model='L515', serial_number=None):
        super().__init__()
        self.name = model
        self.serial_number = serial_number
        self.rs = None
        self.pipeline = None
        self.align = None
        self.depth_scale = 0.00025
        self.intrinsics = None

    @staticmethod
    def list_devices():
        try:
            rs = load_pyrealsense2()
            return [
                (dev.get_info(rs.camera_info.name), dev.get_info(rs.camera_info.serial_number))
                for dev in rs.context().devices
            ]
        except Exception as e:
            print(f"⚠ RealSense indisponível: {e}")
            return []

    def start(self):
        self.rs = rs = load_pyrealsense2()

        if self.serial_number is None:
            for name, serial_number in self.list_devices():
                if self.name in name:
                    self.serial_number = serial_number
                    break
            else:
                print(f"✗ {self.name} não encontrado")
                return False

        for profile in self.PROFILES:
            try:
                self.pipeline = rs.pipeline()
                config = rs.config()
                config.enable_device(self.serial_number)
                if profile:
                    (dw, dh), (cw, ch) = profile
                    config.enable_stream(rs.stream.depth, dw, dh, rs.format.z16, 30)
                    config.enable_stream(rs.stream.color, cw, ch, rs.format.bgr8, 30)
                started = self.pipeline.start(config)
                break
            except Exception as e:
                print(f"  {self.name}: perfil {profile} falhou ({e})")
                self.pipeline = None
        else:
            return False

        self.align = rs.align(rs.stream.color)
        self.depth_scale = started.get_device().first_depth_sensor().get_depth_scale()
        color_profile = started.get_stream(rs.stream.color).as_video_stream_profile()
        self.intrinsics = color_profile.get_intrinsics()
        self.width, self.height = self.intrinsics.width, self.intrinsics.height
        self.hfov_deg = math.degrees(2 * math.atan(self.width / (2 * self.intrinsics.fx)))
        self.online = True
        print(f"✓ {self.name} iniciado (S/N {self.serial_number}), escala {self.depth_scale}")
        return True

    def read(self):
        if not self.pipeline:
            return None, None
        try:
            frames = self.align.process(self.pipeline.wait_for_frames(timeout_ms=1000))
            color_frame = frames.get_color_frame()
            depth_frame = frames.get_depth_frame()
            if not color_frame or not depth_frame:
                return None, None
            color = np.asanyarray(color_frame.get_data())
            depth = np.asanyarray(depth_frame.get_data()).astype(np.float32) * self.depth_scale
            return color, depth
        except Exception as e:
            print(f"Erro ao ler {self.name}: {e}")
            return None, None

    def deproject(self, x, y, dist):
        if self.intrinsics is None:
            return super().deproject(x, y, dist)
        return tuple(self.rs.rs2_deproject_pixel_to_point(self.intrinsics, [x, y], dist))

    def stop(self):
        super().stop()
        if self.pipeline:
            try:
                self.pipeline.stop()
            except Exception:
                pass
            self.pipeline = None


# ---------------------------------------------------------------------------
# LiDAR 2D
# ---------------------------------------------------------------------------

class LidarBase:
    """Lê o LiDAR numa thread e guarda a última volta completa"""

    name = 'lidar'
    kind = 'none'

    def __init__(self, angle_offset_deg=0.0, flip=False, max_range=12.0):
        self.angle_offset = math.radians(angle_offset_deg)
        self.flip = flip
        self.max_range = max_range
        self.online = False
        self.port = None
        self._lock = threading.Lock()
        self._scan = None
        self._scan_time = 0.0
        self._thread = None
        self._running = False
        self.scans_received = 0

    def start(self):
        raise NotImplementedError

    def _run(self):
        raise NotImplementedError

    def _start_thread(self):
        self._running = True
        self._thread = threading.Thread(target=self._run, name=f'{self.name}-reader', daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        self.online = False

    def _publish(self, points):
        """
        points: lista de (ângulo em graus no sentido horário do sensor, distância mm).
        Converte para o referencial do robô e guarda como a volta mais recente.
        """
        if not points:
            return
        raw = np.array(points, dtype=np.float32)
        angles = np.radians(raw[:, 0])
        angles = angles if self.flip else -angles
        angles = np.arctan2(np.sin(angles + self.angle_offset), np.cos(angles + self.angle_offset))
        ranges = raw[:, 1] / 1000.0
        ranges[(ranges <= 0.02) | (ranges > self.max_range)] = 0.0
        order = np.argsort(angles)
        with self._lock:
            self._scan = (angles[order], ranges[order])
            self._scan_time = time.monotonic()
            self.scans_received += 1

    def get_scan(self, max_age=1.0):
        """(ângulos rad, distâncias m; 0 = sem leitura) ou None se o scan for velho"""
        with self._lock:
            if self._scan is None or time.monotonic() - self._scan_time > max_age:
                return None
            return self._scan

    def status(self):
        return {'name': self.name, 'kind': self.kind, 'online': self.online and self.get_scan() is not None,
                'port': self.port}


# --- LD06 / LD19 (LDROBOT) -------------------------------------------------

LD06_HEADER = 0x54
LD06_VERLEN = 0x2C
LD06_PACKET_SIZE = 47
LD06_POINTS = 12


def _crc8_table(poly=0x4D):
    table = []
    for byte in range(256):
        crc = byte
        for _ in range(8):
            crc = ((crc << 1) ^ poly) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
        table.append(crc)
    return table


LD06_CRC_TABLE = _crc8_table()


def ld06_crc(data):
    crc = 0
    for b in data:
        crc = LD06_CRC_TABLE[(crc ^ b) & 0xFF]
    return crc


def parse_ld06(buffer):
    """
    Extrai pacotes do LD06 de um bytearray.
    Retorna (lista de pacotes, bytes restantes). Cada pacote:
    {'speed': graus/s, 'start': graus, 'end': graus, 'points': [(graus, mm, intensidade)]}
    """
    packets = []
    i = 0
    n = len(buffer)
    while i + LD06_PACKET_SIZE <= n:
        if buffer[i] != LD06_HEADER or buffer[i + 1] != LD06_VERLEN:
            i += 1
            continue
        pkt = buffer[i:i + LD06_PACKET_SIZE]
        if ld06_crc(pkt[:-1]) != pkt[-1]:
            i += 1
            continue

        speed = pkt[2] | (pkt[3] << 8)
        start = (pkt[4] | (pkt[5] << 8)) / 100.0
        end = (pkt[42] | (pkt[43] << 8)) / 100.0
        span = (end - start) % 360.0
        step = span / (LD06_POINTS - 1)
        points = []
        for k in range(LD06_POINTS):
            off = 6 + 3 * k
            dist = pkt[off] | (pkt[off + 1] << 8)
            points.append(((start + step * k) % 360.0, dist, pkt[off + 2]))
        packets.append({'speed': speed, 'start': start, 'end': end, 'points': points})
        i += LD06_PACKET_SIZE
    return packets, buffer[i:]


class LD06Lidar(LidarBase):
    """LDROBOT LD06/LD19: transmite sozinho a 230400 baud, sem comandos"""

    name = 'LD06'
    kind = 'ld06'

    def __init__(self, port, baudrate=230400, **kwargs):
        super().__init__(**kwargs)
        self.port = port
        self.baudrate = baudrate
        self.serial = None

    def start(self):
        try:
            self.serial = serial.Serial(self.port, self.baudrate, timeout=0.2)
        except Exception as e:
            print(f"✗ LD06: não abriu {self.port}: {e}")
            return False
        self.online = True
        self._start_thread()
        print(f"✓ LiDAR LD06 lendo em {self.port}")
        return True

    def _run(self):
        buffer = bytearray()
        points = []
        last_start = None
        while self._running:
            try:
                buffer += self.serial.read(512)
            except Exception as e:
                print(f"✗ LD06 desconectado: {e}")
                self.online = False
                break
            packets, buffer = parse_ld06(buffer)
            for pkt in packets:
                # Nova volta quando o ângulo inicial "dá a volta" em 360°
                if last_start is not None and pkt['start'] < last_start:
                    self._publish(points)
                    points = []
                last_start = pkt['start']
                points.extend((a, d) for a, d, _ in pkt['points'])
        try:
            self.serial.close()
        except Exception:
            pass


# --- RPLIDAR (Slamtec) -----------------------------------------------------

RPLIDAR_SYNC = 0xA5
RPLIDAR_STOP = b'\xA5\x25'
RPLIDAR_RESET = b'\xA5\x40'
RPLIDAR_SCAN = b'\xA5\x20'
RPLIDAR_GET_HEALTH = b'\xA5\x52'
RPLIDAR_DESCRIPTOR_SIZE = 7
RPLIDAR_SAMPLE_SIZE = 5


def parse_rplidar(buffer):
    """
    Extrai amostras do modo SCAN padrão (5 bytes cada).
    Retorna (lista de (nova_volta, qualidade, graus, mm), bytes restantes)
    """
    samples = []
    i = 0
    n = len(buffer)
    while i + RPLIDAR_SAMPLE_SIZE <= n:
        b0, b1, b2, b3, b4 = buffer[i:i + RPLIDAR_SAMPLE_SIZE]
        start_flag = b0 & 0x1
        inv_start = (b0 >> 1) & 0x1
        if start_flag == inv_start or not (b1 & 0x1):
            i += 1  # perdeu sincronismo, avança byte a byte
            continue
        angle = ((b2 << 7) | (b1 >> 1)) / 64.0
        dist = (b3 | (b4 << 8)) / 4.0
        samples.append((bool(start_flag), b0 >> 2, angle, dist))
        i += RPLIDAR_SAMPLE_SIZE
    return samples, buffer[i:]


class RPLidar(LidarBase):
    """Slamtec RPLIDAR A1/A2 (115200 baud) ou C1 (460800 baud)"""

    name = 'RPLIDAR'
    kind = 'rplidar'

    def __init__(self, port, baudrate=115200, **kwargs):
        super().__init__(**kwargs)
        self.port = port
        self.baudrate = baudrate
        self.serial = None

    def start(self):
        try:
            self.serial = serial.Serial(self.port, self.baudrate, timeout=1)
            self.serial.dtr = False  # no adaptador USB do A1, DTR baixo liga o motor
            self.serial.write(RPLIDAR_STOP)
            time.sleep(0.05)
            self.serial.reset_input_buffer()
            self.serial.write(RPLIDAR_SCAN)
            descriptor = self.serial.read(RPLIDAR_DESCRIPTOR_SIZE)
            if len(descriptor) != RPLIDAR_DESCRIPTOR_SIZE or descriptor[:2] != b'\xA5\x5A':
                raise IOError(f"resposta inválida ao SCAN: {descriptor.hex()}")
        except Exception as e:
            print(f"✗ RPLIDAR: falha em {self.port}: {e}")
            if self.serial:
                self.serial.close()
            return False
        self.online = True
        self._start_thread()
        print(f"✓ LiDAR RPLIDAR lendo em {self.port}")
        return True

    def _run(self):
        buffer = bytearray()
        points = []
        while self._running:
            try:
                buffer += self.serial.read(max(RPLIDAR_SAMPLE_SIZE, self.serial.in_waiting))
            except Exception as e:
                print(f"✗ RPLIDAR desconectado: {e}")
                self.online = False
                break
            samples, buffer = parse_rplidar(buffer)
            for new_scan, quality, angle, dist in samples:
                if new_scan:
                    self._publish(points)
                    points = []
                if quality > 0:
                    points.append((angle, dist))
        try:
            self.serial.write(RPLIDAR_STOP)
            self.serial.dtr = True
            self.serial.close()
        except Exception:
            pass


def probe_lidar_port(port):
    """Tenta descobrir qual LiDAR está numa porta: 'ld06', 'rplidar' ou None"""
    try:
        with serial.Serial(port, 230400, timeout=0.3) as ser:
            data = ser.read(LD06_PACKET_SIZE * 6)
            if parse_ld06(bytearray(data))[0]:
                return 'ld06'
    except Exception:
        return None

    for baud in (115200, 460800):
        try:
            with serial.Serial(port, baud, timeout=0.3) as ser:
                ser.reset_input_buffer()
                ser.write(RPLIDAR_GET_HEALTH)
                if ser.read(RPLIDAR_DESCRIPTOR_SIZE)[:2] == b'\xA5\x5A':
                    return 'rplidar' if baud == 115200 else 'rplidar-c1'
        except Exception:
            pass
    return None


def autodetect_lidar(exclude=()):
    """Procura um LiDAR em todas as portas seriais USB. Retorna (tipo, porta) ou (None, None)"""
    for port in serial.tools.list_ports.comports():
        # Arduinos com USB nativo aparecem como ttyACM; LiDARs usam conversores (ttyUSB)
        if port.device in exclude or 'ttyACM' in port.device or 'ttyS' in port.device:
            continue
        kind = probe_lidar_port(port.device)
        if kind:
            print(f"  LiDAR {kind} detectado em {port.device}")
            return kind, port.device
    return None, None


def make_lidar(kind, port, **kwargs):
    if kind == 'ld06':
        return LD06Lidar(port, **kwargs)
    if kind == 'rplidar':
        return RPLidar(port, **kwargs)
    if kind == 'rplidar-c1':
        return RPLidar(port, baudrate=460800, **kwargs)
    raise ValueError(f"LiDAR desconhecido: {kind}")
