"""
Sistema de Controle Autônomo do RAS (robô tri-omni)
- Câmera RGB USB Logitech C270 (frontal)
- LiDAR 2D (RPLIDAR ou LD06/LD19) para obstáculos ao redor do robô
- Intel RealSense L515 (opcional, ainda suportado enquanto estiver no robô)
- Modo --sim: robô, Arduino, câmera e LiDAR simulados para testar sem hardware

Uso:
  python3 robot_autonomous_control.py            # hardware real (detecção automática)
  python3 robot_autonomous_control.py --sim      # tudo simulado
  python3 robot_autonomous_control.py --help     # todas as opções
"""

import argparse
import asyncio
import base64
import json
import math
import signal
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np
import serial
import serial.tools.list_ports
import websockets
from scipy.spatial import distance

import sensors

SIM_PORT = 'SIM'


class ObjectTracker:
    """Rastreia objetos detectados pela profundidade (L515)"""

    def __init__(self, max_disappeared=10, min_area=5000, max_distance=2.0, min_distance=0.5):
        self.next_object_id = 0
        self.objects = {}
        self.disappeared = {}
        self.centroids = {}
        self.max_disappeared = max_disappeared
        self.min_area = min_area
        self.max_distance = max_distance
        self.min_distance = min_distance
        self.frame_counter = 0
        self.stable_frames = 3
        self.candidate_objects = {}

    def detect_objects(self, depth_meters):
        """Detecta objetos usando dados de profundidade (metros)"""
        if depth_meters is None:
            return []

        valid_mask = (depth_meters > self.min_distance) & (depth_meters < self.max_distance)

        if not np.any(valid_mask):
            return []

        depth_normalized = ((depth_meters - self.min_distance) /
                            (self.max_distance - self.min_distance) * 255).clip(0, 255).astype(np.uint8)
        depth_normalized[~valid_mask] = 0

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        depth_clean = cv2.morphologyEx(depth_normalized, cv2.MORPH_CLOSE, kernel)
        depth_clean = cv2.morphologyEx(depth_clean, cv2.MORPH_OPEN, kernel)

        _, binary = cv2.threshold(depth_clean, 30, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        detected = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < self.min_area:
                continue

            x, y, w, h = cv2.boundingRect(contour)
            roi = depth_meters[y:y+h, x:x+w]
            valid_depths = roi[roi > 0]

            if len(valid_depths) < 100:
                continue
            if valid_depths.std() > 0.3:
                continue

            bbox_area = w * h
            fill_ratio = area / bbox_area if bbox_area > 0 else 0
            if fill_ratio < 0.3:
                continue

            cx = x + w // 2
            cy = y + h // 2
            avg_depth = np.median(valid_depths)

            detected.append({
                'bbox': (x, y, x+w, y+h),
                'centroid': (cx, cy),
                'depth': float(avg_depth),
                'area': float(area)
            })

        return detected

    def update(self, depth_meters):
        """Atualiza rastreamento com novo frame"""
        self.frame_counter += 1
        detections = self.detect_objects(depth_meters)

        if len(detections) == 0:
            for object_id in list(self.disappeared.keys()):
                self.disappeared[object_id] += 1
                if self.disappeared[object_id] > self.max_disappeared:
                    del self.objects[object_id]
                    del self.disappeared[object_id]
                    del self.centroids[object_id]
            return

        input_centroids = np.array([d['centroid'] for d in detections])

        if len(self.objects) == 0:
            for detection in detections:
                self._add_candidate(detection)
        else:
            object_ids = list(self.objects.keys())
            object_centroids = np.array([self.centroids[oid] for oid in object_ids])

            D = distance.cdist(object_centroids, input_centroids)
            rows = D.min(axis=1).argsort()
            cols = D.argmin(axis=1)[rows]

            used_rows = set()
            used_cols = set()

            for (row, col) in zip(rows, cols):
                if row in used_rows or col in used_cols:
                    continue
                if D[row, col] > 100:
                    continue

                object_id = object_ids[row]
                detection = detections[col]

                self.objects[object_id] = detection
                self.centroids[object_id] = detection['centroid']
                self.disappeared[object_id] = 0

                used_rows.add(row)
                used_cols.add(col)

            unused_rows = set(range(D.shape[0])) - used_rows
            for row in unused_rows:
                object_id = object_ids[row]
                self.disappeared[object_id] += 1

                if self.disappeared[object_id] > self.max_disappeared:
                    del self.objects[object_id]
                    del self.disappeared[object_id]
                    del self.centroids[object_id]

            unused_cols = set(range(D.shape[1])) - used_cols
            for col in unused_cols:
                self._add_candidate(detections[col])

    def _add_candidate(self, detection):
        """Só registra um objeto depois de aparecer em stable_frames frames"""
        centroid = detection['centroid']
        if centroid not in self.candidate_objects:
            self.candidate_objects[centroid] = {'count': 1, 'data': detection}
        else:
            self.candidate_objects[centroid]['count'] += 1
            if self.candidate_objects[centroid]['count'] >= self.stable_frames:
                self._register(detection)
                del self.candidate_objects[centroid]

    def _register(self, detection):
        """Registra novo objeto"""
        self.objects[self.next_object_id] = detection
        self.centroids[self.next_object_id] = detection['centroid']
        self.disappeared[self.next_object_id] = 0
        self.next_object_id += 1

    def get_tracked_objects(self):
        """Retorna objetos rastreados (mesmo formato do YOLO, usado pelo frontend)"""
        tracked = []
        for obj_id, obj in self.objects.items():
            x1, y1, x2, y2 = obj['bbox']
            cx, cy = self.centroids[obj_id]
            tracked.append({
                'id': str(obj_id),
                'bbox': {'x': int(x1), 'y': int(y1), 'w': int(x2 - x1), 'h': int(y2 - y1)},
                'centroid': {'x': int(cx), 'y': int(cy)},
                'depth': obj['depth'],
                'area': obj['area']
            })
        return tracked


class ObstacleDetector:
    """Detecta obstáculos usando dados dos sensores"""

    # Setores do LiDAR 2D em graus (0 = frente, positivo = esquerda)
    SCAN_SECTORS = {'left': (20, 70), 'center': (-20, 20), 'right': (-70, -20)}

    def __init__(self, safe_distance=0.5, height_threshold=1.5, corridor_half_width=0.3):
        self.safe_distance = safe_distance
        self.height_threshold = height_threshold
        # Meia largura do robô (raio ~0.2 m) + margem: só o que está nessa faixa bloqueia a frente
        self.corridor_half_width = corridor_half_width

    def analyze_scan(self, scan, max_range=10.0):
        """
        Analisa uma volta do LiDAR 2D: menor distância em cada setor frontal e
        'path_distance', a distância até o primeiro ponto no corredor à frente do robô
        """
        if scan is None:
            return None

        angles, ranges = scan
        degrees = np.degrees(angles)
        result = {'distances': {}, 'sensor': 'LIDAR2D'}
        for sector, (lo, hi) in self.SCAN_SECTORS.items():
            sel = ranges[(degrees >= lo) & (degrees <= hi) & (ranges > 0)]
            dist = float(sel.min()) if sel.size else max_range
            result[sector] = dist < self.safe_distance
            result['distances'][sector] = dist

        valid = ranges > 0
        ahead = ranges[valid] * np.cos(angles[valid])
        lateral = ranges[valid] * np.sin(angles[valid])
        in_path = ahead[(ahead > 0) & (np.abs(lateral) < self.corridor_half_width)]
        result['path_distance'] = float(in_path.min()) if in_path.size else max_range
        return result

    def analyze_height(self, depth_meters):
        """Analisa altura dos obstáculos usando a profundidade da câmera (metros)"""
        if depth_meters is None:
            return None

        height, width = depth_meters.shape

        roi_top = int(height * 0.3)
        roi_bottom = int(height * 0.7)
        roi = depth_meters[roi_top:roi_bottom, :]

        third = width // 3
        left_region = roi[:, :third]
        center_region = roi[:, third:2*third]
        right_region = roi[:, 2*third:]

        def check_height_region(region):
            valid = region[(region > 0.1) & (region < 3.0)]
            if len(valid) > 100:
                min_dist = np.min(valid)
                return {
                    'blocked': min_dist < 0.8,
                    'distance': float(min_dist)
                }
            return {'blocked': False, 'distance': 3.0}

        left_status = check_height_region(left_region)
        center_status = check_height_region(center_region)
        right_status = check_height_region(right_region)

        return {
            'left': left_status['blocked'],
            'center': center_status['blocked'],
            'right': right_status['blocked'],
            'distances': {
                'left': left_status['distance'],
                'center': center_status['distance'],
                'right': right_status['distance']
            },
            'sensor': 'L515'
        }


def merge_obstacles(*sources):
    """Combina setores de vários sensores ficando com a menor distância de cada um"""
    sources = [s for s in sources if s]
    if not sources:
        return None
    merged = {'distances': {}, 'sensor': '+'.join(s.get('sensor', s.get('type', '?')) for s in sources)}
    for sector in ('left', 'center', 'right'):
        merged[sector] = any(s.get(sector) for s in sources)
        merged['distances'][sector] = min(s['distances'][sector] for s in sources)
    # Câmeras não têm corredor; para elas o setor central faz esse papel
    merged['path_distance'] = min(s.get('path_distance', s['distances']['center']) for s in sources)
    return merged


class AutonomousNavigator:
    """Navegação autônoma: anda, escaneia girando e desvia pelo lado mais livre"""

    def __init__(self):
        self.current_state = 'moving_forward'
        self.base_speed = 100
        self.rotation_counter = 0
        self.rotation_steps_45deg = 2
        self.rotation_direction = None  # 'left' ou 'right'

        # Controle de exploração: andar e girar para observar
        self.forward_counter = 0
        self.forward_steps = 15  # Quantos passos andar reto antes de escanear
        self.scan_counter = 0
        self.scan_steps = 6  # Quantos passos girar para escanear ao redor

        # Distância de segurança mínima (metros)
        self.safe_distance = 0.8

    def analyze_depth_distances(self, obstacles):
        """
        Analisa as distâncias esquerda/centro/direita
        Se esquerda está mais perto: gira sentido horário (direita) para se afastar
        Se direita está mais perto: gira sentido anti-horário (esquerda) para se afastar
        Retorna: 'left', 'right', ou None (sem obstáculos)
        """
        if not obstacles or 'distances' not in obstacles:
            return None

        distances = obstacles['distances']
        left_dist = distances.get('left', 3.0)
        center_dist = distances.get('center', 3.0)
        right_dist = distances.get('right', 3.0)

        # LiDAR 2D informa o corredor à frente; sem ele, qualquer setor perto bloqueia
        path_dist = obstacles.get('path_distance', min(left_dist, center_dist, right_dist))
        if path_dist > self.safe_distance:
            return None

        # Gira para o lado com mais espaço
        if left_dist < right_dist:
            return 'right'
        elif right_dist < left_dist:
            return 'left'

        # Se ambos igualmente pertos, default para direita
        return 'right'

    def decide_movement(self, obstacles):
        """
        Decide próximo movimento: alterna entre andar reto e girar para escanear
        Retorna (direção, velocidade, info)
        """
        detection_info = {
            'state': self.current_state,
            'forward_counter': self.forward_counter,
            'scan_counter': self.scan_counter
        }

        # Estado: girando para escanear ambiente
        if self.current_state == 'scanning':
            self.scan_counter += 1
            speed = int(self.base_speed * 0.5)  # Gira devagar

            if self.scan_counter < self.scan_steps:
                return 'rotate_right', speed, detection_info
            # Terminou o scan, volta a andar reto (passando pela checagem de obstáculos)
            self.scan_counter = 0
            self.forward_counter = 0
            self.current_state = 'moving_forward'

        # Estado: desviando de obstáculo
        if self.current_state == 'avoiding':
            self.rotation_counter += 1
            speed = int(self.base_speed * 0.6)

            command = 'rotate_left' if self.rotation_direction == 'left' else 'rotate_right'
            if self.rotation_counter < self.rotation_steps_45deg:
                return command, speed, detection_info
            # Ainda bloqueado: continua girando para o mesmo lado (evita oscilar esq/dir)
            if self.analyze_depth_distances(obstacles):
                self.rotation_counter = 0
                return command, speed, detection_info
            # Terminou o desvio, volta a andar reto (passando pela checagem de obstáculos)
            self.rotation_counter = 0
            self.rotation_direction = None
            self.current_state = 'moving_forward'

        # Estado: andando reto (com desvio de obstáculos)
        self.forward_counter += 1

        # Obstáculo tem prioridade sobre o escaneamento
        avoidance_direction = self.analyze_depth_distances(obstacles)
        if avoidance_direction:
            self.current_state = 'avoiding'
            self.rotation_counter = 0
            self.rotation_direction = avoidance_direction
            command = 'rotate_left' if avoidance_direction == 'left' else 'rotate_right'
            return command, int(self.base_speed * 0.6), detection_info

        if self.forward_counter >= self.forward_steps:
            self.current_state = 'scanning'
            self.scan_counter = 0
            return 'rotate_right', int(self.base_speed * 0.5), detection_info

        return 'forward', self.base_speed, detection_info


class RobotController:
    """Controla o robô via Arduino (ou Arduino simulado na porta 'SIM')"""

    def __init__(self, sim_world=None):
        self.serial_port = None
        self.port_name = None
        self.speed = 150
        self.sim_world = sim_world
        self.reserved_ports = set()  # portas em uso por outros sensores (LiDAR)

    def connect(self, port):
        """Conecta ao Arduino"""
        try:
            self.disconnect()

            if port in (SIM_PORT, f'/dev/{SIM_PORT}'):
                if self.sim_world is None:
                    raise IOError("porta SIM só existe com --sim")
                from simulator import SimArduino
                self.serial_port = SimArduino(self.sim_world)
            else:
                if port in self.reserved_ports:
                    raise IOError(f"{port} está sendo usada pelo LiDAR")
                self.serial_port = serial.Serial(port, 9600, timeout=1)
            self.port_name = port
            print(f"✓ Conectado ao Arduino na porta {port}")
            return True
        except Exception as e:
            print(f"✗ Erro ao conectar: {e}")
            self.serial_port = None
            return False

    def disconnect(self):
        if self.serial_port:
            try:
                self.send_command(0, 0, 0)
                self.serial_port.close()
            except Exception:
                pass
            print(f"✗ Arduino desconectado ({self.port_name})")
        self.serial_port = None
        self.port_name = None

    def is_connected(self):
        """Verifica se está conectado"""
        return self.serial_port is not None and self.serial_port.is_open

    def send_command(self, m1, m2, m3):
        """Envia comando direto para os motores"""
        if not self.is_connected():
            return False

        try:
            m1, m2, m3 = (max(-255, min(255, int(v))) for v in (m1, m2, m3))
            command = f"{m1},{m2},{m3}\n"
            print(f"📤 ENVIANDO PARA ARDUINO: {command.strip()}")
            self.serial_port.write(command.encode())
            return True
        except Exception as e:
            print(f"✗ Erro ao enviar comando: {e}")
            return False

    def move(self, direction, speed):
        """Move o robô em uma direção"""

        commands = {
            'forward': (-speed, 0, speed),           # Frente: M1=-speed, M2=0, M3=+speed
            'backward': (speed, 0, -speed),          # Trás: M1=+speed, M2=0, M3=-speed
            'left': (0, -speed, speed),              # Esquerda: M1=0, M2=-speed, M3=+speed
            'right': (0, speed, -speed),             # Direita: M1=0, M2=+speed, M3=-speed
            'rotate_right': (speed, speed, speed),   # Rotação horária in-place
            'rotate_left': (-speed, -speed, -speed), # Rotação anti-horária in-place
            'stop': (0, 0, 0)
        }

        if direction in commands:
            m1, m2, m3 = commands[direction]
            return self.send_command(m1, m2, m3)
        return False

    def get_available_ports(self):
        """Lista portas seriais disponíveis (sem as do LiDAR)"""
        ports = []
        try:
            ports = [p.device for p in serial.tools.list_ports.comports()
                     if p.device not in self.reserved_ports and 'ttyS' not in p.device]
        except Exception as e:
            print(f"✗ Erro ao listar portas: {e}")
        if self.sim_world is not None:
            ports.insert(0, SIM_PORT)
        return ports


class SensorManager:
    """Câmera principal (C270), L515 opcional e LiDAR 2D"""

    def __init__(self, camera=None, l515=None, lidar=None):
        self.camera = camera
        self.l515 = l515
        self.lidar = lidar

    def start(self):
        for attr in ('camera', 'l515', 'lidar'):
            sensor = getattr(self, attr)
            if sensor is None:
                continue
            try:
                ok = sensor.start()
            except Exception as e:
                print(f"✗ Falha ao iniciar {sensor.name}: {e}")
                ok = False
            if not ok:
                setattr(self, attr, None)

        print(f"\n{'='*50}")
        print("SENSORES:")
        print(f"  Câmera: {self.camera.name if self.camera else '✗ OFFLINE'}")
        print(f"  L515:   {'✓ FUNCIONANDO' if self.l515 else '✗ OFFLINE'}")
        print(f"  LiDAR:  {self.lidar.name + ' em ' + str(self.lidar.port) if self.lidar else '✗ OFFLINE'}")
        print(f"{'='*50}\n")

    def capture(self):
        """Lê um frame de cada câmera: {nome: {'camera', 'color', 'depth'}}"""
        frames = {}
        for key, cam in (('camera', self.camera), ('l515', self.l515)):
            if cam is None:
                continue
            color, depth = cam.read()
            if color is not None:
                frames[key] = {'camera': cam, 'color': color, 'depth': depth}
        return frames

    def get_scan(self):
        return self.lidar.get_scan() if self.lidar else None

    def status(self):
        def st(sensor):
            return sensor.status() if sensor else {'online': False}
        return {'camera': st(self.camera), 'l515': st(self.l515), 'lidar': st(self.lidar)}

    def stop(self):
        for sensor in (self.camera, self.l515, self.lidar):
            if sensor:
                try:
                    sensor.stop()
                except Exception:
                    pass


def encode_jpeg(image, quality=80):
    _, buffer = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return base64.b64encode(buffer).decode('utf-8')


def scan_to_message(scan, max_points=360):
    """Reduz a volta do LiDAR para enviar ao frontend (ângulos em graus)"""
    if scan is None:
        return None
    angles, ranges = scan
    step = max(1, len(angles) // max_points)
    return {
        'angles': np.round(np.degrees(angles[::step]), 1).tolist(),
        'ranges': np.round(ranges[::step], 3).tolist(),
    }


class WebSocketServer:
    """Servidor WebSocket para comunicação com interface web"""

    def __init__(self, robot_controller, sensor_manager, obstacle_detector, navigator):
        self.robot = robot_controller
        self.sensors = sensor_manager
        self.detector = obstacle_detector
        self.navigator = navigator

        # YOLO é carregado só quando ligado na interface
        self.yolo_tracker = None
        self.use_yolo = False
        self.basic_tracker = ObjectTracker()
        # Uma thread só para sensores/visão: não trava o loop do WebSocket
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='perception')

        self.clients = set()
        self.autonomous_mode = False
        self.running = True
        self.tablet_connected = False
        self.robot_moving = False
        self.last_move_time = 0  # Para detectar timeout de movimento manual
        self.last_navigation = None

    async def register(self, websocket):
        """Registra novo cliente e envia o estado atual para ele"""
        self.clients.add(websocket)
        print(f"✓ Cliente conectado. Total: {len(self.clients)}")
        for message in (
            {'type': 'ports_list', 'ports': self.robot.get_available_ports()},
            {'type': 'serial_status', 'connected': self.robot.is_connected(), 'port': self.robot.port_name,
             'initial': True},
            {'type': 'autonomous_status', 'enabled': self.autonomous_mode},
            {'type': 'yolo_status', 'enabled': self.use_yolo, 'initial': True},
        ):
            await websocket.send(json.dumps(message))

    async def unregister(self, websocket):
        """Remove cliente"""
        self.clients.discard(websocket)
        print(f"✗ Cliente desconectado. Total: {len(self.clients)}")
        if not self.clients:
            # Ninguém mais controlando: por segurança para o robô
            self.autonomous_mode = False
            self.robot.move('stop', 0)
            self.robot_moving = False

    async def send_to_all(self, message):
        """Envia mensagem para todos os clientes"""
        if self.clients:
            payload = json.dumps(message)
            await asyncio.gather(
                *[client.send(payload) for client in list(self.clients)],
                return_exceptions=True
            )

    async def handle_client(self, websocket):
        """Gerencia comunicação com cliente"""
        await self.register(websocket)
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    print(f"⚠ Mensagem inválida ignorada: {message[:80]!r}")
                    continue
                await self.process_command(data)
        except websockets.ConnectionClosed:
            pass
        finally:
            await self.unregister(websocket)

    def _convert_tracking_to_obstacles(self, tracked_objects, frame_width=640):
        """Converte objetos rastreados do YOLO em formato de obstáculos"""
        obstacles = {
            'type': 'yolo',
            'sensor': 'YOLO',
            'left': False,
            'center': False,
            'right': False,
            'distances': {'left': 10.0, 'center': 10.0, 'right': 10.0}
        }

        # Divide frame em 3 setores
        left_sector = frame_width // 3
        right_sector = 2 * frame_width // 3

        for obj in tracked_objects or []:
            bbox = obj.get('bbox', {})
            center_x = bbox.get('x', 0) + bbox.get('w', 0) // 2
            depth = obj.get('depth') or 10.0

            if center_x < left_sector:
                sector = 'left'
            elif center_x < right_sector:
                sector = 'center'
            else:
                sector = 'right'

            if depth < obstacles['distances'][sector]:
                obstacles['distances'][sector] = depth
                # Marca como obstáculo se estiver perto (< 1.5m)
                if depth < 1.5:
                    obstacles[sector] = True

        return obstacles

    async def process_command(self, data):
        """Processa comandos recebidos"""
        cmd_type = data.get('type')

        if cmd_type == 'discover_ports':
            ports = self.robot.get_available_ports()
            await self.send_to_all({'type': 'ports_list', 'ports': ports})

        elif cmd_type == 'connect_serial':
            port = data.get('port')
            success = self.robot.connect(port)
            await self.send_to_all({
                'type': 'serial_status',
                'connected': success,
                'port': port if success else None
            })

        elif cmd_type == 'disconnect_serial':
            self.autonomous_mode = False
            self.robot.disconnect()
            self.robot_moving = False
            await self.send_to_all({'type': 'serial_status', 'connected': False, 'port': None})
            await self.send_to_all({'type': 'autonomous_status', 'enabled': False})

        elif cmd_type == 'move':
            now = asyncio.get_running_loop().time()
            if 'm1' in data and 'm2' in data and 'm3' in data:
                print(f"🎮 COMANDO RECEBIDO DO FRONTEND: M1={data['m1']}, M2={data['m2']}, M3={data['m3']}")
                self.robot.send_command(data['m1'], data['m2'], data['m3'])
                is_moving = any([data['m1'] != 0, data['m2'] != 0, data['m3'] != 0])
            else:
                direction = data.get('direction')
                self.robot.move(direction, data.get('speed', 150))
                is_moving = direction != 'stop'
            self.robot_moving = is_moving
            if is_moving:
                self.last_move_time = now

        elif cmd_type == 'set_autonomous':
            self.autonomous_mode = data.get('enabled', False)
            if 'speed' in data:
                self.navigator.base_speed = data['speed']
            if not self.autonomous_mode:
                self.robot.move('stop', 0)
                self.robot_moving = False
            await self.send_to_all({'type': 'autonomous_status', 'enabled': self.autonomous_mode})

        elif cmd_type == 'set_autonomous_speed':
            self.navigator.base_speed = data.get('speed', 100)

        elif cmd_type == 'toggle_yolo':
            await self.set_yolo(data.get('enabled', False))

        elif cmd_type == 'robot_face_heartbeat':
            self.tablet_connected = True

    async def set_yolo(self, enabled):
        if enabled and self.sensors.camera is None and self.sensors.l515 is None:
            await self.send_to_all({'type': 'yolo_status', 'enabled': False,
                                    'error': 'Nenhuma câmera disponível'})
            return

        if enabled and self.yolo_tracker is None:
            try:
                from robot_tracking_system import MultiCameraTracker
                print("⏳ Carregando modelo YOLO...")
                loop = asyncio.get_running_loop()
                self.yolo_tracker = await loop.run_in_executor(self.executor, MultiCameraTracker)
                print("✓ YOLO carregado")
            except Exception as e:
                print(f"✗ Falha ao carregar YOLO: {e}")
                await self.send_to_all({'type': 'yolo_status', 'enabled': False,
                                        'error': f'Falha ao carregar YOLO: {e}'})
                return

        self.use_yolo = enabled
        if not enabled and self.yolo_tracker:
            self.yolo_tracker.cleanup()
        await self.send_to_all({'type': 'yolo_status', 'enabled': self.use_yolo})

    def perceive(self):
        """Lê todos os sensores e monta a parte de visão/obstáculos da mensagem (roda em thread)"""
        message = {}
        frames = self.sensors.capture()
        scan = self.sensors.get_scan()

        ground_obstacles = self.detector.analyze_scan(scan)
        if ground_obstacles:
            message['ground_obstacles'] = ground_obstacles
        lidar_msg = scan_to_message(scan)
        if lidar_msg:
            message['lidar_scan'] = lidar_msg

        height_obstacles = None
        if self.use_yolo and self.yolo_tracker:
            try:
                self.yolo_tracker.process_frame(frames, scan)
                tracked = self.yolo_tracker.get_tracked_objects()
                message['tracked_objects'] = tracked
                message['tracking_mode'] = 'yolo'
                main = frames.get('camera') or frames.get('l515')
                width = main['color'].shape[1] if main else 640
                height_obstacles = self._convert_tracking_to_obstacles(
                    [o for o in tracked if o['camera'] == ('camera' if 'camera' in frames else 'l515')], width)
            except Exception as e:
                print(f"❌ Erro no YOLO tracking: {e}")
                import traceback
                traceback.print_exc()
                message['tracking_mode'] = 'error'
        else:
            message['tracking_mode'] = 'basic'
            for data in frames.values():
                data['annotated'] = data['color']
            l515 = frames.get('l515')
            if l515 is not None and l515['depth'] is not None:
                self.basic_tracker.update(l515['depth'])
                tracked = self.basic_tracker.get_tracked_objects()
                annotated = l515['color'].copy()
                for obj in tracked:
                    b = obj['bbox']
                    cv2.rectangle(annotated, (b['x'], b['y']), (b['x'] + b['w'], b['y'] + b['h']), (0, 255, 0), 2)
                    cv2.putText(annotated, f"ID:{obj['id']} {obj['depth']:.2f}m", (b['x'], b['y'] - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                l515['annotated'] = annotated
                message['tracked_objects'] = tracked

        l515 = frames.get('l515')
        if l515 is not None and l515['depth'] is not None and height_obstacles is None:
            height_obstacles = self.detector.analyze_height(l515['depth'])
        if height_obstacles:
            message['height_obstacles'] = height_obstacles

        # Câmera principal = C270; se só houver L515, ela vira a principal
        if 'camera' in frames:
            message['camera_image'] = encode_jpeg(frames['camera']['annotated'])
            if l515 is not None:
                message['l515_image'] = encode_jpeg(l515['annotated'])
        elif l515 is not None:
            message['camera_image'] = encode_jpeg(l515['annotated'])
            message['l515_image'] = message['camera_image']

        message['sensors_status'] = self.sensors.status()
        return message

    async def sensor_loop(self):
        """Loop principal de leitura dos sensores"""
        print("\n🔄 Iniciando loop de sensores...")
        loop = asyncio.get_running_loop()
        last_tablet_check = loop.time()

        while self.running:
            try:
                loop_start = loop.time()

                if loop_start - last_tablet_check > 5:
                    self.tablet_connected = False
                    last_tablet_check = loop_start

                # Detecta timeout de movimento manual (0.3s sem comando = parado)
                if not self.autonomous_mode and self.robot_moving:
                    if loop_start - self.last_move_time > 0.3:
                        self.robot_moving = False

                message = {
                    'type': 'sensor_data',
                    'timestamp': loop_start,
                    'tablet_connected': self.tablet_connected,
                }
                message.update(await loop.run_in_executor(self.executor, self.perceive))

                # NAVEGAÇÃO AUTÔNOMA
                if self.autonomous_mode and self.robot.is_connected():
                    obstacles = merge_obstacles(message.get('ground_obstacles'), message.get('height_obstacles'))
                    direction, speed, nav_info = self.navigator.decide_movement(obstacles)

                    if direction == 'stop' or speed <= 0:
                        self.robot.move('stop', 0)
                        self.robot_moving = False
                    else:
                        self.robot.move(direction, speed)
                        self.robot_moving = True

                    self.last_navigation = {
                        'active': True,
                        'direction': direction,
                        'speed': speed,
                        'info': nav_info,
                        'detection': {
                            'mode': nav_info['state'],
                            'sensor': obstacles.get('sensor') if obstacles else None,
                            'obstacles': {k: obstacles[k] for k in ('left', 'center', 'right')} if obstacles else None,
                            'distances': obstacles['distances'] if obstacles else None,
                        },
                        'reason': nav_info['state'],
                    }
                    message['navigation'] = self.last_navigation
                    message['navigation_status'] = self.last_navigation
                elif self.last_navigation:
                    self.last_navigation = None
                    message['navigation_status'] = {'active': False}

                message['robot_moving'] = self.robot_moving
                await self.send_to_all(message)

                elapsed = loop.time() - loop_start
                await asyncio.sleep(max(0.01, 0.1 - elapsed))

            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"❌ Erro no loop de sensores: {e}")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(0.5)

    async def start_server(self, host='127.0.0.1', port=8765, ready=None):
        """Inicia servidor WebSocket"""
        print(f"\n🚀 Iniciando servidor WebSocket em {host}:{port}")
        sensor_task = asyncio.create_task(self.sensor_loop())
        try:
            async with websockets.serve(self.handle_client, host, port, max_size=2**22) as server:
                print("✓ Servidor WebSocket ativo!")
                if ready is not None:
                    ready.set_result(server)
                await asyncio.Future()
        finally:
            self.running = False
            sensor_task.cancel()


def build_system(args):
    """Monta sensores, robô e servidor a partir das opções de linha de comando"""
    world = None
    camera = l515 = lidar = None
    lidar_kwargs = {'angle_offset_deg': args.lidar_offset, 'flip': args.lidar_flip}

    if args.sim:
        from simulator import SimCamera, SimLidar, SimWorld
        world = SimWorld()
        world.start_realtime()
        lidar = SimLidar(world)
        camera = SimCamera(world)
        camera.lidar = lidar
    else:
        if args.camera == 'auto' or args.camera == 'usb':
            device = args.camera_device
            if device is not None and device.isdigit():
                device = int(device)
            camera = sensors.UsbCamera(device=device, hfov_deg=args.camera_fov)
            if args.camera == 'auto' and device is None and not sensors.find_usb_cameras():
                camera = None

        if args.l515 != 'off':
            devices = sensors.RealSenseCamera.list_devices()
            if any('L515' in name for name, _ in devices) or args.l515 == 'on':
                l515 = sensors.RealSenseCamera('L515')

        if args.lidar != 'none':
            kind, port = args.lidar, args.lidar_port
            if kind == 'auto':
                if port:
                    kind = sensors.probe_lidar_port(port)
                else:
                    kind, port = sensors.autodetect_lidar()
            elif port is None:
                print(f"⚠ --lidar {kind} precisa de --lidar-port; procurando automaticamente")
                _, port = sensors.autodetect_lidar()
            if kind and port:
                if args.lidar_baud:
                    lidar_kwargs['baudrate'] = args.lidar_baud
                lidar = sensors.make_lidar(kind, port, **lidar_kwargs)
            else:
                print("⚠ Nenhum LiDAR 2D encontrado")

    sensor_manager = SensorManager(camera, l515, lidar)
    robot = RobotController(sim_world=world)
    if lidar is not None and lidar.port and lidar.port != 'SIM':
        robot.reserved_ports.add(lidar.port)
    server = WebSocketServer(robot, sensor_manager, ObstacleDetector(), AutonomousNavigator())
    return server, world


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Backend do robô RAS (WebSocket na porta 8765)")
    parser.add_argument('--sim', action='store_true', help="simula robô, Arduino, câmera e LiDAR")
    parser.add_argument('--host', default='127.0.0.1', help="use 0.0.0.0 para acessar de outro aparelho (tablet)")
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--camera', choices=['auto', 'usb', 'none'], default='auto',
                        help="câmera RGB principal (C270)")
    parser.add_argument('--camera-device', help="ex.: /dev/video2 ou 2 (padrão: procura a C270)")
    parser.add_argument('--camera-fov', type=float, default=60.0, help="campo de visão horizontal em graus")
    parser.add_argument('--l515', choices=['auto', 'on', 'off'], default='auto')
    parser.add_argument('--lidar', choices=['auto', 'ld06', 'rplidar', 'rplidar-c1', 'none'], default='auto')
    parser.add_argument('--lidar-port', help="ex.: /dev/ttyUSB1")
    parser.add_argument('--lidar-baud', type=int)
    parser.add_argument('--lidar-offset', type=float, default=0.0,
                        help="graus para alinhar o 0° do LiDAR com a frente do robô")
    parser.add_argument('--lidar-flip', action='store_true', help="LiDAR montado de cabeça para baixo")
    parser.add_argument('--no-auto-connect', action='store_true',
                        help="no --sim, não conecta o Arduino simulado sozinho")
    return parser.parse_args(argv)


def main(argv=None):
    """Função principal"""
    args = parse_args(argv)
    print("\n" + "="*70)
    print("  SISTEMA DE NAVEGAÇÃO AUTÔNOMA - ROBÔ TRI-OMNI (RAS 2.0)")
    print("  " + ("MODO SIMULAÇÃO" if args.sim else "C270 + LiDAR 2D (+ L515 opcional)"))
    print("="*70)

    # SIGTERM (ex.: start.sh encerrando) vira Ctrl+C, para sempre parar os motores ao sair
    signal.signal(signal.SIGTERM, signal.default_int_handler)

    server, world = build_system(args)
    server.sensors.start()
    if args.sim and not args.no_auto_connect:
        server.robot.connect(SIM_PORT)

    try:
        print(f"\n{'='*70}")
        print("✓ Sistema pronto para uso!")
        print("  - Interface: http://localhost:8080")
        print("  - Use os controles para mover o robô manualmente")
        print("  - Ative o modo autônomo para navegação com desvio")
        print(f"{'='*70}\n")
        asyncio.run(server.start_server(args.host, args.port))
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrompido pelo usuário")
    finally:
        print("\n🧹 Limpando recursos...")
        if server.robot.is_connected():
            server.robot.move('stop', 0)
        server.sensors.stop()
        if world:
            world.stop_realtime()
        print("✓ Sistema encerrado\n")


if __name__ == "__main__":
    main()
