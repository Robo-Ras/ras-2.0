"""Lógica de obstáculos, navegação e Arduino simulado (sem hardware)"""

import math
import os
import sys
import json
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from robot_autonomous_control import (  # noqa: E402
    AutonomousNavigator, ObjectTracker, ObstacleDetector, RobotController, merge_obstacles,
)
from simulator import SimArduino, SimLidar, SimWorld, wheels_to_body_velocity  # noqa: E402


def make_scan(default=5.0, **sectors):
    """Scan de 360 pontos; sectors = {'graus_inicio,graus_fim': distância}"""
    angles = np.radians(np.arange(-180, 180, 1.0))
    ranges = np.full(angles.shape, default)
    deg = np.degrees(angles)
    for key, dist in sectors.items():
        lo, hi = (float(v) for v in key.split('_'))
        ranges[(deg >= lo) & (deg <= hi)] = dist
    return angles, ranges


class ObstacleTest(unittest.TestCase):
    def test_scan_sectors(self):
        detector = ObstacleDetector(safe_distance=0.5)
        result = detector.analyze_scan(make_scan(**{'30_40': 0.4, '-5_5': 1.2}))
        self.assertTrue(result['left'])
        self.assertFalse(result['center'])
        self.assertFalse(result['right'])
        self.assertAlmostEqual(result['distances']['left'], 0.4)
        self.assertAlmostEqual(result['distances']['center'], 1.2)
        self.assertAlmostEqual(result['distances']['right'], 5.0)

    def test_behind_robot_is_ignored(self):
        result = ObstacleDetector().analyze_scan(make_scan(**{'150_180': 0.1}))
        self.assertFalse(any(result[s] for s in ('left', 'center', 'right')))

    def test_merge_takes_closest(self):
        a = {'left': False, 'center': True, 'right': False, 'sensor': 'A',
             'distances': {'left': 2.0, 'center': 0.3, 'right': 4.0}}
        b = {'left': True, 'center': False, 'right': False, 'sensor': 'B',
             'distances': {'left': 0.5, 'center': 1.0, 'right': 3.0}}
        merged = merge_obstacles(a, None, b)
        self.assertEqual(merged['distances'], {'left': 0.5, 'center': 0.3, 'right': 3.0})
        self.assertTrue(merged['left'] and merged['center'] and not merged['right'])
        self.assertIsNone(merge_obstacles(None, None))

    def test_realsense_height_and_basic_tracker(self):
        depth = np.full((480, 640), 4.0, dtype=np.float32)
        depth[150:330, 40:180] = 0.6  # caixa à esquerda a 60 cm
        height = ObstacleDetector().analyze_height(depth)
        self.assertTrue(height['left'])
        self.assertFalse(height['right'])
        json.dumps(height)  # vai pelo WebSocket: nada de numpy.bool_ (quebrava com a D435 real)

        # O tracker básico (código original) só enxerga objetos entre ~0.7 m e 2 m
        depth[150:330, 40:180] = 1.2

        tracker = ObjectTracker()
        for _ in range(5):
            tracker.update(depth)
        tracked = tracker.get_tracked_objects()
        self.assertEqual(len(tracked), 1)
        self.assertAlmostEqual(tracked[0]['depth'], 1.2, places=2)
        self.assertEqual(set(tracked[0]['bbox']), {'x', 'y', 'w', 'h'})


class NavigatorTest(unittest.TestCase):
    def obstacles(self, left, center, right):
        return {'distances': {'left': left, 'center': center, 'right': right}}

    def test_free_path_goes_forward(self):
        nav = AutonomousNavigator()
        self.assertEqual(nav.decide_movement(self.obstacles(3, 3, 3))[0], 'forward')

    def test_obstacle_straight_ahead_is_avoided(self):
        # Antes só esquerda/direita eram olhados e o robô batia de frente; gira para o lado mais livre
        nav = AutonomousNavigator()
        self.assertEqual(nav.decide_movement(self.obstacles(2.0, 0.4, 2.5))[0], 'rotate_right')
        nav = AutonomousNavigator()
        self.assertEqual(nav.decide_movement(self.obstacles(2.5, 0.4, 2.0))[0], 'rotate_left')

    def test_side_walls_outside_corridor_do_not_block(self):
        detector, nav = ObstacleDetector(), AutonomousNavigator()
        # corredor de 1 m de largura: paredes a 0.5 m de cada lado, livre à frente
        angles = np.radians(np.arange(-180, 180, 1.0))
        with np.errstate(divide='ignore'):
            ranges = np.minimum(np.abs(0.5 / np.sin(angles)), 6.0)
        obstacles = detector.analyze_scan((angles, ranges))
        self.assertGreater(obstacles['path_distance'], 5.0)
        self.assertEqual(nav.decide_movement(obstacles)[0], 'forward')

    def test_keeps_turning_same_way_while_blocked(self):
        nav = AutonomousNavigator()
        blocked = dict(self.obstacles(0.9, 0.5, 1.0), path_distance=0.5)
        moves = {nav.decide_movement(blocked)[0] for _ in range(20)}
        self.assertEqual(moves, {'rotate_right'})

    def test_turns_away_from_closer_side(self):
        nav = AutonomousNavigator()
        self.assertEqual(nav.decide_movement(self.obstacles(0.5, 2, 3))[0], 'rotate_right')
        nav = AutonomousNavigator()
        self.assertEqual(nav.decide_movement(self.obstacles(3, 2, 0.5))[0], 'rotate_left')

    def test_scan_cycle(self):
        nav = AutonomousNavigator()
        moves = [nav.decide_movement(self.obstacles(3, 3, 3))[0] for _ in range(nav.forward_steps + nav.scan_steps)]
        self.assertEqual(moves[:nav.forward_steps - 1], ['forward'] * (nav.forward_steps - 1))
        self.assertIn('rotate_right', moves[nav.forward_steps - 1:])
        self.assertEqual(moves[-1], 'forward')


class SimArduinoTest(unittest.TestCase):
    def test_parses_like_the_sketch(self):
        world = SimWorld()
        arduino = SimArduino(world)
        arduino.write(b'-100,0,')
        self.assertEqual(world.wheels, (0, 0, 0))          # espera o \n
        arduino.write(b'100\n300,-999,12abc\n,1,2\n1,2\n')
        self.assertEqual(list(arduino.received), [(-100, 0, 100), (255, -255, 12)])
        self.assertEqual(world.wheels, (255, -255, 12))
        self.assertIn(b'Sistema iniciado', arduino.readline())
        arduino.close()
        self.assertEqual(world.wheels, (0, 0, 0))

    def test_robot_controller_directions(self):
        world = SimWorld()
        robot = RobotController(sim_world=world)
        self.assertIn('SIM', robot.get_available_ports())
        self.assertTrue(robot.connect('/dev/SIM'))
        expected = {
            'forward': (1, 0, 0), 'backward': (-1, 0, 0), 'left': (0, 1, 0), 'right': (0, -1, 0),
            'rotate_left': (0, 0, 1), 'rotate_right': (0, 0, -1),
        }
        for direction, signs in expected.items():
            robot.move(direction, 120)
            vel = wheels_to_body_velocity(*world.wheels)
            self.assertEqual(tuple(int(np.sign(round(v, 6))) for v in vel), signs, direction)
        robot.disconnect()
        self.assertFalse(robot.is_connected())

    def test_sim_port_needs_sim_mode(self):
        self.assertFalse(RobotController().connect('SIM'))


class ClosedLoopTest(unittest.TestCase):
    """Roda o navegador contra o mundo simulado, mais rápido que o tempo real"""

    def run_autonomy(self, seconds, start):
        world = SimWorld()
        world.reset(*start)
        lidar = SimLidar(world)
        robot = RobotController(sim_world=world)
        robot.connect('SIM')
        detector, nav = ObstacleDetector(), AutonomousNavigator()
        positions = []
        for _ in range(int(seconds * 10)):          # loop de controle a 10 Hz
            lidar.scan_now()
            direction, speed, _ = nav.decide_movement(detector.analyze_scan(lidar.get_scan()))
            robot.move(direction, speed)
            for _ in range(5):
                world.step(0.02)
            positions.append(world.pose()[:2])
        return world, positions

    def test_explores_without_collisions(self):
        for start in ((0.7, 0.7, math.radians(30)), (3.0, 4.5, math.radians(-90)), (5.4, 2.4, math.pi)):
            world, positions = self.run_autonomy(180, start)
            self.assertEqual(world.collisions, 0, f"bateu partindo de {start}")
            self.assertGreater(world.distance_travelled, 5.0, f"ficou parado partindo de {start}")
            cells = {(int(x / 0.5), int(y / 0.5)) for x, y in positions}
            self.assertGreater(len(cells), 8, f"não explorou partindo de {start}")


if __name__ == '__main__':
    unittest.main()
