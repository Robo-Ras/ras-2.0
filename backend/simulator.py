"""
Simulador do robô para testar tudo sem hardware
- Mundo 2D (sala com caixas e colunas) com física simples do robô omnidirecional
- Arduino virtual: aceita "m1,m2,m3\\n" igual ao arduino_robot_control.ino
- LiDAR 2D e câmera RGB sintéticos, gerados por raycasting no mundo

Referencial do mundo: x, y em metros; theta em rad (0 = +x, anti-horário positivo)
"""

import math
import threading
import time
from collections import deque

import cv2
import numpy as np

from sensors import CameraBase, LidarBase

# Velocidades do robô simulado com PWM 255
MAX_LINEAR_SPEED = 0.5    # m/s
MAX_ANGULAR_SPEED = 3.0   # rad/s
ROBOT_RADIUS = 0.2        # m

# Vetores de roda dos comandos do frontend (DirectionalControl.tsx):
#   frente = (-s, 0, s), direita = (0, s, -s), giro horário = (s, s, s)
# Qualquer comando é decomposto nesses três movimentos, então o simulador
# obedece exatamente o que os botões da interface dizem fazer.
_PRIMITIVES = np.array([
    [-1.0, 0.0, 1.0],   # frente
    [0.0, 1.0, -1.0],   # direita
    [1.0, 1.0, 1.0],    # giro horário
]).T
_PRIMITIVES_INV = np.linalg.inv(_PRIMITIVES)


def wheels_to_body_velocity(m1, m2, m3):
    """PWM das rodas -> (vx frente m/s, vy esquerda m/s, omega anti-horário rad/s)"""
    forward, right, clockwise = _PRIMITIVES_INV @ np.array([m1, m2, m3], dtype=float) / 255.0
    return forward * MAX_LINEAR_SPEED, -right * MAX_LINEAR_SPEED, -clockwise * MAX_ANGULAR_SPEED


class SimWorld:
    """Sala retangular com obstáculos; o robô é um círculo"""

    def __init__(self, width=6.0, height=5.0):
        self.width = width
        self.height = height
        self.lock = threading.RLock()

        # Obstáculos: (tipo, geometria, altura m, cor BGR)
        self.boxes = [
            ((1.2, 3.4, 1.9, 4.1), 0.5, (40, 110, 200)),     # caixa laranja
            ((3.8, 0.9, 4.6, 1.5), 0.7, (60, 160, 60)),      # caixa verde
            ((4.4, 3.2, 5.0, 4.4), 0.9, (150, 80, 160)),     # armário roxo
        ]
        self.cylinders = [
            ((2.9, 2.6), 0.18, 1.7, (180, 140, 60)),         # "pessoa" / coluna azul
            ((1.6, 1.4), 0.12, 0.8, (60, 60, 190)),          # lixeira vermelha
        ]
        self.wall_height = 1.2
        self.wall_color = (205, 205, 200)
        self._build_segments()

        self.reset()
        self._thread = None
        self._running = False

    def reset(self, x=0.7, y=0.7, theta=math.radians(30)):
        with self.lock:
            self.x, self.y, self.theta = x, y, theta
            self.wheels = (0, 0, 0)
            self.collisions = 0
            self.distance_travelled = 0.0
            self.trail = deque(maxlen=400)

    def _build_segments(self):
        w, h = self.width, self.height
        segs, heights, colors = [], [], []

        def add_rect(x1, y1, x2, y2, height, color):
            for a, b in (((x1, y1), (x2, y1)), ((x2, y1), (x2, y2)), ((x2, y2), (x1, y2)), ((x1, y2), (x1, y1))):
                segs.append((*a, *b))
                heights.append(height)
                colors.append(color)

        add_rect(0, 0, w, h, self.wall_height, self.wall_color)
        for rect, height, color in self.boxes:
            add_rect(*rect, height, color)

        self.segments = np.array(segs, dtype=np.float64)
        self.segment_heights = np.array(heights)
        self.segment_colors = np.array(colors, dtype=np.float64)
        self.circles = np.array([(cx, cy, r) for (cx, cy), r, _, _ in self.cylinders], dtype=np.float64)
        self.circle_heights = np.array([hgt for _, _, hgt, _ in self.cylinders])
        self.circle_colors = np.array([c for _, _, _, c in self.cylinders], dtype=np.float64)

    # --- física -----------------------------------------------------------

    def set_wheels(self, m1, m2, m3):
        with self.lock:
            self.wheels = (m1, m2, m3)

    def collides(self, x, y, radius=ROBOT_RADIUS):
        if x < radius or y < radius or x > self.width - radius or y > self.height - radius:
            return True
        for (x1, y1, x2, y2), _, _ in self.boxes:
            nx, ny = min(max(x, x1), x2), min(max(y, y1), y2)
            if math.hypot(x - nx, y - ny) < radius:
                return True
        for (cx, cy), r, _, _ in self.cylinders:
            if math.hypot(x - cx, y - cy) < radius + r:
                return True
        return False

    def step(self, dt):
        with self.lock:
            vx, vy, omega = wheels_to_body_velocity(*self.wheels)
            c, s = math.cos(self.theta), math.sin(self.theta)
            nx = self.x + (vx * c - vy * s) * dt
            ny = self.y + (vx * s + vy * c) * dt
            self.theta = math.atan2(math.sin(self.theta + omega * dt), math.cos(self.theta + omega * dt))
            if self.collides(nx, ny):
                if math.hypot(vx, vy) > 1e-6:
                    self.collisions += 1
            else:
                self.distance_travelled += math.hypot(nx - self.x, ny - self.y)
                self.x, self.y = nx, ny
            if not self.trail or math.hypot(self.trail[-1][0] - self.x, self.trail[-1][1] - self.y) > 0.05:
                self.trail.append((self.x, self.y))

    def start_realtime(self, rate_hz=50):
        if self._running:
            return
        self._running = True

        def loop():
            last = time.monotonic()
            while self._running:
                time.sleep(1.0 / rate_hz)
                now = time.monotonic()
                self.step(now - last)
                last = now

        self._thread = threading.Thread(target=loop, name='sim-world', daemon=True)
        self._thread.start()

    def stop_realtime(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=1)

    def pose(self):
        with self.lock:
            return self.x, self.y, self.theta

    # --- raycasting -------------------------------------------------------

    def raycast(self, ox, oy, angles, max_range=12.0):
        """
        Lança raios a partir de (ox, oy) nos ângulos do mundo.
        Retorna (distâncias, alturas, cores BGR) do primeiro objeto atingido.
        """
        dx = np.cos(angles)[:, None]
        dy = np.sin(angles)[:, None]

        # Segmentos: resolve o + t*d = a + u*(b - a)
        ax, ay, bx, by = (self.segments[:, k][None, :] for k in range(4))
        ex, ey = bx - ax, by - ay
        denom = dx * ey - dy * ex
        with np.errstate(divide='ignore', invalid='ignore'):
            t = ((ax - ox) * ey - (ay - oy) * ex) / denom
            u = ((ax - ox) * dy - (ay - oy) * dx) / denom
        t = np.where((np.abs(denom) > 1e-12) & (t > 1e-6) & (u >= 0) & (u <= 1), t, np.inf)

        # Círculos: |o + t*d - c|^2 = r^2
        cx, cy, cr = (self.circles[:, k][None, :] for k in range(3))
        fx, fy = ox - cx, oy - cy
        b = fx * dx + fy * dy
        disc = b * b - (fx * fx + fy * fy - cr * cr)
        with np.errstate(invalid='ignore'):
            tc = -b - np.sqrt(disc)
        tc = np.where((disc >= 0) & (tc > 1e-6), tc, np.inf)

        seg_idx = np.argmin(t, axis=1)
        seg_t = t[np.arange(len(angles)), seg_idx]
        cir_idx = np.argmin(tc, axis=1)
        cir_t = tc[np.arange(len(angles)), cir_idx]

        hit_circle = cir_t < seg_t
        dist = np.where(hit_circle, cir_t, seg_t)
        heights = np.where(hit_circle, self.circle_heights[cir_idx], self.segment_heights[seg_idx])
        colors = np.where(hit_circle[:, None], self.circle_colors[cir_idx], self.segment_colors[seg_idx])
        dist = np.minimum(dist, max_range)
        return dist, heights, colors


class SimArduino:
    """Imita o objeto serial.Serial conectado ao arduino_robot_control.ino"""

    def __init__(self, world):
        self.world = world
        self.is_open = True
        self.port = 'SIM'
        self.received = deque(maxlen=200)
        self._buffer = b''
        self._replies = deque()
        self._replies.append(b'Sistema iniciado. Aguardando comandos...\r\n')

    def write(self, data):
        if not self.is_open:
            raise IOError("porta fechada")
        self._buffer += data
        while b'\n' in self._buffer:
            line, self._buffer = self._buffer.split(b'\n', 1)
            self._handle(line.decode(errors='ignore').strip())
        return len(data)

    def _handle(self, command):
        # Mesmas regras do parseCommand(): precisa de duas vírgulas e algo antes da primeira
        if command.startswith(',') or command.count(',') < 2:
            return
        first, second, rest = command.split(',', 2)
        m1, m2, m3 = (max(-255, min(255, _arduino_to_int(v))) for v in (first, second, rest))
        self.received.append((m1, m2, m3))
        self.world.set_wheels(m1, m2, m3)
        self._replies.append(f'Comando recebido - M1: {m1}, M2: {m2}, M3: {m3}\r\n'.encode())

    def readline(self):
        return self._replies.popleft() if self._replies else b''

    def close(self):
        self.is_open = False
        self.world.set_wheels(0, 0, 0)


def _arduino_to_int(text):
    """String.toInt() do Arduino: lê o número no início, ignora o resto, 0 se não houver"""
    text = text.strip()
    sign, i = 1, 0
    if text and text[0] in '+-':
        sign = -1 if text[0] == '-' else 1
        i = 1
    digits = ''
    while i < len(text) and text[i].isdigit():
        digits += text[i]
        i += 1
    return sign * int(digits) if digits else 0


class SimLidar(LidarBase):
    """LiDAR 2D de 360 pontos/volta a 10 Hz no centro do robô"""

    name = 'LiDAR simulado'
    kind = 'sim'

    def __init__(self, world, points=360, rate_hz=10, noise_m=0.01, **kwargs):
        super().__init__(**kwargs)
        self.world = world
        self.points = points
        self.rate_hz = rate_hz
        self.noise = noise_m
        self.port = 'SIM'
        self.rng = np.random.default_rng(0)

    def start(self):
        self.online = True
        self._start_thread()
        print("✓ LiDAR simulado iniciado")
        return True

    def scan_now(self):
        x, y, theta = self.world.pose()
        # O sensor real gira no sentido horário; geramos no mesmo formato dele
        raw_deg = np.arange(self.points) * (360.0 / self.points)
        world_angles = theta - np.radians(raw_deg)
        dist, _, _ = self.world.raycast(x, y, world_angles, self.max_range)
        dist = dist + self.rng.normal(0, self.noise, dist.shape)
        self._publish(list(zip(raw_deg, np.clip(dist, 0, None) * 1000.0)))

    def _run(self):
        while self._running:
            self.scan_now()
            time.sleep(1.0 / self.rate_hz)


class SimCamera(CameraBase):
    """Câmera frontal sintética (estilo C270: 640x480, 60° horizontal, sem profundidade)"""

    name = 'Câmera simulada'
    kind = 'sim'

    def __init__(self, world, width=640, height=480, hfov_deg=60.0, camera_height=0.35, fps=15):
        super().__init__()
        self.world = world
        self.width = width
        self.height = height
        self.hfov_deg = hfov_deg
        self.camera_height = camera_height
        self.period = 1.0 / fps
        self._last = 0.0
        self.lidar = None  # opcional, só para desenhar no mini-mapa

    def start(self):
        self.online = True
        print("✓ Câmera simulada iniciada")
        return True

    def read(self):
        wait = self.period - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()
        return self.render(), None

    def render(self):
        w, h = self.width, self.height
        x, y, theta = self.world.pose()
        f = (w / 2) / math.tan(math.radians(self.hfov_deg) / 2)
        cols = np.arange(w)
        offsets = np.arctan2((w / 2) - cols, f)
        dist, heights, colors = self.world.raycast(x, y, theta + offsets)
        depth = np.maximum(dist * np.cos(offsets), 0.05)

        horizon = h / 2
        top = horizon - f * (heights - self.camera_height) / depth
        bottom = horizon + f * self.camera_height / depth

        rows = np.arange(h)[:, None]
        img = np.empty((h, w, 3), dtype=np.uint8)
        # teto e chão com gradiente
        sky = np.linspace(235, 190, h // 2)[:, None, None] * np.array([1.0, 0.97, 0.9])
        floor = np.linspace(110, 170, h - h // 2)[:, None, None] * np.array([0.75, 0.8, 0.85])
        img[:h // 2] = sky.astype(np.uint8)
        img[h // 2:] = floor.astype(np.uint8)

        shade = np.clip(1.15 - depth / 7.0, 0.35, 1.0)[:, None]
        col_colors = (colors * shade).astype(np.uint8)
        mask = (rows >= top[None, :]) & (rows <= bottom[None, :])
        img[mask] = np.broadcast_to(col_colors[None, :, :], (h, w, 3))[mask]

        # linha de base dos objetos para dar noção de profundidade
        base = np.clip(bottom.astype(int), 0, h - 1)
        img[base, cols] = (img[base, cols] * 0.4).astype(np.uint8)

        cv2.putText(img, 'SIMULACAO', (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 220), 2)
        self._draw_minimap(img)
        return img

    def _draw_minimap(self, img):
        world = self.world
        scale = 26
        mw, mh = int(world.width * scale), int(world.height * scale)
        ox, oy = img.shape[1] - mw - 10, 10

        def to_px(px, py):
            return int(ox + px * scale), int(oy + mh - py * scale)

        cv2.rectangle(img, (ox, oy), (ox + mw, oy + mh), (40, 40, 40), -1)
        for (x1, y1, x2, y2), _, color in world.boxes:
            cv2.rectangle(img, to_px(x1, y2), to_px(x2, y1), color, -1)
        for (cx, cy), r, _, color in world.cylinders:
            cv2.circle(img, to_px(cx, cy), max(2, int(r * scale)), color, -1)

        x, y, theta = world.pose()
        if self.lidar:
            scan = self.lidar.get_scan()
            if scan is not None:
                angles, ranges = scan
                for a, r in zip(angles[::3], ranges[::3]):
                    if r > 0:
                        cv2.circle(img, to_px(x + r * math.cos(theta + a), y + r * math.sin(theta + a)), 1,
                                   (0, 255, 255), -1)
        trail = list(world.trail)
        for p, q in zip(trail, trail[1:]):
            cv2.line(img, to_px(*p), to_px(*q), (120, 200, 120), 1)
        cv2.circle(img, to_px(x, y), int(ROBOT_RADIUS * scale), (255, 255, 255), 1)
        cv2.line(img, to_px(x, y), to_px(x + 0.35 * math.cos(theta), y + 0.35 * math.sin(theta)), (0, 0, 255), 2)
        cv2.rectangle(img, (ox, oy), (ox + mw, oy + mh), (200, 200, 200), 1)
