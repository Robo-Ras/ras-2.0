"""
YOLO com câmera sem profundidade (C270): a distância vem do LiDAR.
Usa a foto de exemplo que vem com o ultralytics (ônibus com pessoas).
"""

import math
import os
import sys
import unittest

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sensors import CameraBase  # noqa: E402

try:
    import ultralytics
    from robot_tracking_system import MODEL_PATH, MultiCameraTracker, range_at_bearing
    SAMPLE = os.path.join(os.path.dirname(ultralytics.__file__), 'assets', 'bus.jpg')
    HAVE_YOLO = os.path.exists(SAMPLE) and os.path.exists(MODEL_PATH)
except ImportError:
    HAVE_YOLO = False


class StillCamera(CameraBase):
    name = 'C270'

    def __init__(self, image):
        super().__init__()
        self.image = image
        self.height, self.width = image.shape[:2]


@unittest.skipUnless(HAVE_YOLO, "ultralytics ou yolov8n.pt indisponível")
class YoloLidarFusionTest(unittest.TestCase):
    def test_detects_people_with_lidar_distance(self):
        image = cv2.resize(cv2.imread(SAMPLE), (640, 480))
        camera = StillCamera(image)
        angles = np.radians(np.arange(-180, 180, 0.5))
        ranges = np.where(angles > 0, 1.5, 3.0)  # esquerda a 1.5 m, direita a 3 m
        scan = (angles, ranges)

        tracker = MultiCameraTracker()
        for _ in range(3):
            frames = {'camera': {'camera': camera, 'color': image, 'depth': None}}
            tracker.process_frame(frames, scan)
        objects = tracker.get_tracked_objects()

        people = [o for o in objects if o['class_name'] == 'person']
        self.assertGreaterEqual(len(people), 2)
        for obj in people:
            cx = obj['bbox']['x'] + obj['bbox']['w'] / 2
            expected = 1.5 if cx < camera.width / 2 else 3.0
            self.assertAlmostEqual(obj['depth'], expected, places=3)
            self.assertAlmostEqual(obj['position_3d'][2], expected, places=3)
        self.assertFalse(np.array_equal(frames['camera']['annotated'], image))

    def test_bearing_lookup(self):
        angles = np.radians(np.array([-10.0, 0.0, 10.0]))
        ranges = np.array([2.0, 0.0, 1.0])
        self.assertEqual(range_at_bearing((angles, ranges), math.radians(10)), 1.0)
        self.assertEqual(range_at_bearing((angles, ranges), 0.0), 0.0)  # só leitura inválida
        self.assertEqual(range_at_bearing(None, 0.0), 0.0)


if __name__ == '__main__':
    unittest.main()
