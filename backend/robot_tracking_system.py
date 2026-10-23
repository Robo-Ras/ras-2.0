"""
Sistema de Rastreamento de Objetos com YOLO
- Funciona com qualquer câmera de sensors.py (C270, D435, simulada)
- Distância do objeto: profundidade da câmera (D435) ou, sem profundidade (C270),
  a leitura do LiDAR 2D na mesma direção do objeto
"""

import math
import os
import time
import uuid

import cv2
import numpy as np
from filterpy.kalman import KalmanFilter

# Configurações do sistema
MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "yolov8n.pt")
DETECTION_INTERVAL = 3
MIN_DIST = 0.25
MAX_DIST = 8.0
MAX_MISSED = 10
TRACKER_DIST_THRESHOLD_PIX = 120
LIDAR_BEARING_WINDOW = math.radians(3)


class TrackedObject:
    """Objeto rastreado com filtro de Kalman"""

    def __init__(self, bbox, cls, conf, class_name, camera_name=""):
        cx = (bbox[0] + bbox[2]) / 2.0
        cy = (bbox[1] + bbox[3]) / 2.0

        # Filtro de Kalman para suavização
        self.kf = KalmanFilter(dim_x=4, dim_z=2)
        self.kf.x = np.array([cx, cy, 0., 0.])
        self.kf.F = np.array([[1, 0, 1, 0], [0, 1, 0, 1], [0, 0, 1, 0], [0, 0, 0, 1]])
        self.kf.H = np.array([[1, 0, 0, 0], [0, 1, 0, 0]])
        self.kf.P *= 50
        self.kf.R *= 1
        self.kf.Q *= 0.01

        self.bbox = bbox
        self.cls = cls
        self.conf = conf
        self.class_name = class_name
        self.id = str(uuid.uuid4())[:8]
        self.missed = 0
        self.history = []
        self.camera_name = camera_name
        self.depth = 0.0
        self.position_3d = (0, 0, 0)

    def predict(self):
        """Predição do filtro de Kalman"""
        self.kf.predict()

    def update(self, bbox, conf, camera_name=""):
        """Atualiza o objeto com nova detecção"""
        cx = (bbox[0] + bbox[2]) / 2.0
        cy = (bbox[1] + bbox[3]) / 2.0
        self.kf.update(np.array([cx, cy]))
        self.bbox = bbox
        self.conf = conf
        self.missed = 0
        self.history.append((time.time(), bbox))
        self.history = self.history[-50:]
        if camera_name:
            self.camera_name = camera_name

    def current_center(self):
        """Retorna o centro atual do objeto"""
        return int(self.kf.x[0]), int(self.kf.x[1])

    def to_dict(self):
        """Converte para dicionário para envio via WebSocket"""
        cx, cy = self.current_center()
        x1, y1, x2, y2 = self.bbox

        return {
            'id': self.id,
            'bbox': {'x': int(x1), 'y': int(y1), 'w': int(x2 - x1), 'h': int(y2 - y1)},
            'centroid': {'x': int(cx), 'y': int(cy)},
            'class': self.class_name,
            'class_name': self.class_name,
            'confidence': float(self.conf),
            'camera': self.camera_name,
            'depth': float(self.depth),
            'position_3d': [float(x) for x in self.position_3d],
            'missed': self.missed
        }


def range_at_bearing(scan, bearing, window=LIDAR_BEARING_WINDOW):
    """Menor distância válida do LiDAR em torno de um ângulo (rad, referencial do robô)"""
    if scan is None:
        return 0.0
    angles, ranges = scan
    diff = np.abs(np.arctan2(np.sin(angles - bearing), np.cos(angles - bearing)))
    sel = ranges[(diff <= window) & (ranges > 0)]
    return float(sel.min()) if sel.size else 0.0


def object_distance(bbox, camera, depth, lidar_scan):
    """Distância (m) do objeto: profundidade da câmera se houver, senão LiDAR"""
    x1, y1, x2, y2 = bbox
    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

    if depth is not None:
        h, w = depth.shape[:2]
        # mediana de uma janela central (um único pixel é muito ruidoso)
        rx, ry = max(2, (x2 - x1) // 6), max(2, (y2 - y1) // 6)
        patch = depth[max(0, cy - ry):min(h, cy + ry), max(0, cx - rx):min(w, cx + rx)]
        valid = patch[(patch > 0) & np.isfinite(patch)]
        return float(np.median(valid)) if valid.size else 0.0

    return range_at_bearing(lidar_scan, camera.bearing_of_pixel(cx))


class MultiCameraTracker:
    """Sistema de tracking YOLO sobre os frames das câmeras do robô"""

    def __init__(self, model_path=MODEL_PATH):
        # ultralytics demora para importar; só carrega quando o YOLO é ligado
        from ultralytics import YOLO
        if not os.path.exists(model_path):
            model_path = os.path.basename(model_path)  # ultralytics baixa automaticamente
        self.model = YOLO(model_path)
        self.trackers = []
        self.frame_idx = 0

    def process_frame(self, frames, lidar_scan=None):
        """
        frames: {nome: {'camera': CameraBase, 'color': BGR, 'depth': metros ou None}}
        Retorna o mesmo dicionário com 'annotated' em cada câmera
        """
        detecting = self.frame_idx % DETECTION_INTERVAL == 0
        all_detections = []

        for camera_name, data in frames.items():
            data['annotated'] = data['color'].copy()
            if not detecting:
                continue
            try:
                results = self.model(data['color'], verbose=False)
            except Exception as e:
                print(f"    Erro na detecção YOLO para {camera_name}: {e}")
                continue
            for r in results:
                for box in r.boxes:
                    x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].cpu().numpy())
                    cls = int(box.cls[0])
                    all_detections.append({
                        'bbox': (x1, y1, x2, y2),
                        'cls': cls,
                        'class_name': self.model.names[cls],
                        'conf': float(box.conf[0]),
                        'camera_name': camera_name,
                        'camera': data['camera'],
                        'depth': data['depth'],
                    })

        if detecting:
            self._update_trackers(all_detections, lidar_scan)
        else:
            for tr in self.trackers:
                tr.predict()

        # Remove trackers perdidos
        self.trackers = [t for t in self.trackers if t.missed <= MAX_MISSED]

        for camera_name, data in frames.items():
            self._draw_annotations(camera_name, data['annotated'])

        self.frame_idx += 1
        return frames

    def _update_trackers(self, detections, lidar_scan):
        """Atualiza trackers com novas detecções"""
        assigned = set()

        for det in detections:
            dbox = det['bbox']
            camera_name = det['camera_name']
            cx = (dbox[0] + dbox[2]) // 2
            cy = (dbox[1] + dbox[3]) // 2

            dist = object_distance(dbox, det['camera'], det['depth'], lidar_scan)
            if dist and not (MIN_DIST <= dist <= MAX_DIST):
                continue
            pos_3d = det['camera'].deproject(cx, cy, dist) if dist else (0, 0, 0)

            # Encontra tracker mais próximo da mesma câmera
            best = None
            best_dist = TRACKER_DIST_THRESHOLD_PIX
            for tr in self.trackers:
                if tr.camera_name != camera_name or id(tr) in assigned:
                    continue
                tx, ty = tr.current_center()
                d = math.hypot(tx - cx, ty - cy)
                if d < best_dist:
                    best_dist = d
                    best = tr

            if best is None:
                best = TrackedObject(dbox, det['cls'], det['conf'], det['class_name'], camera_name)
                self.trackers.append(best)
            else:
                best.update(dbox, det['conf'], camera_name)
            best.depth = dist
            best.position_3d = pos_3d
            assigned.add(id(best))

        # Marca não atribuídos
        for tr in self.trackers:
            if id(tr) not in assigned:
                tr.missed += 1

    def _draw_annotations(self, camera_name, annotated):
        """Desenha anotações nos frames"""
        for tr in self.trackers:
            if tr.camera_name != camera_name or tr.missed > 3:
                continue

            x1, y1, x2, y2 = map(int, tr.bbox)
            cx, cy = tr.current_center()
            dist_text = f" {tr.depth:.2f}m" if tr.depth else ""
            label = f"{tr.class_name} #{tr.id} {tr.conf:.2f}{dist_text}"

            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(annotated, label, (x1, max(10, y1 - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            if tr.depth:
                x3d, y3d, z3d = tr.position_3d
                cv2.putText(annotated, f"X:{x3d:.2f} Y:{y3d:.2f} Z:{z3d:.2f}m", (x1, y2 + 15),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 200, 200), 1)

            cv2.circle(annotated, (cx, cy), 4, (0, 0, 255), -1)

    def get_tracked_objects(self):
        """Retorna lista de objetos rastreados"""
        return [tr.to_dict() for tr in self.trackers if tr.missed < 5]

    def cleanup(self):
        """Esquece os objetos rastreados (as câmeras são do SensorManager)"""
        self.trackers = []
