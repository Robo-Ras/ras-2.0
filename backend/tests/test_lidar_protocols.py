"""Drivers de LiDAR testados com pacotes montados byte a byte (sem hardware)"""

import math
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sensors  # noqa: E402


def build_ld06_packet(start_deg, end_deg, distances_mm, speed=3600, timestamp=1234):
    pkt = bytearray([sensors.LD06_HEADER, sensors.LD06_VERLEN])
    pkt += speed.to_bytes(2, 'little')
    pkt += int(start_deg * 100).to_bytes(2, 'little')
    for d in distances_mm:
        pkt += int(d).to_bytes(2, 'little') + bytes([200])
    pkt += int(end_deg * 100).to_bytes(2, 'little')
    pkt += timestamp.to_bytes(2, 'little')
    pkt.append(sensors.ld06_crc(pkt))
    return pkt


def build_rplidar_sample(angle_deg, dist_mm, quality=15, new_scan=False):
    angle_q6 = int(angle_deg * 64)
    s = 1 if new_scan else 0
    return bytes([
        (quality << 2) | ((1 - s) << 1) | s,
        ((angle_q6 & 0x7F) << 1) | 1,
        angle_q6 >> 7,
    ]) + int(dist_mm * 4).to_bytes(2, 'little')


class LD06Test(unittest.TestCase):
    def test_crc_table_matches_ldrobot_datasheet(self):
        self.assertEqual(sensors.LD06_CRC_TABLE[:6], [0x00, 0x4D, 0x9A, 0xD7, 0x79, 0x34])

    def test_parse_packet_with_garbage_and_partial_tail(self):
        pkt = build_ld06_packet(10.0, 21.0, range(1000, 1012))
        data = bytearray(b'\x00\x54\x99') + pkt + pkt[:20]
        packets, rest = sensors.parse_ld06(data)
        self.assertEqual(len(packets), 1)
        self.assertEqual(rest, pkt[:20])
        points = packets[0]['points']
        self.assertEqual(len(points), 12)
        self.assertAlmostEqual(points[0][0], 10.0)
        self.assertAlmostEqual(points[-1][0], 21.0)
        self.assertEqual(points[5][1], 1005)

    def test_packet_crossing_zero_degrees(self):
        packets, _ = sensors.parse_ld06(build_ld06_packet(355.0, 5.0, [500] * 12))
        angles = [p[0] for p in packets[0]['points']]
        self.assertAlmostEqual(angles[0], 355.0)
        self.assertAlmostEqual(angles[-1], 5.0, places=5)

    def test_bad_crc_is_rejected(self):
        pkt = build_ld06_packet(10.0, 21.0, [800] * 12)
        pkt[10] ^= 0xFF
        self.assertEqual(sensors.parse_ld06(pkt)[0], [])


class RPLidarTest(unittest.TestCase):
    def test_parse_samples_and_resync(self):
        data = b'\xFF' + build_rplidar_sample(0.5, 1500, new_scan=True) + build_rplidar_sample(90.25, 320.5)
        samples, rest = sensors.parse_rplidar(bytearray(data))
        self.assertEqual(len(samples), 2)
        self.assertTrue(samples[0][0])
        self.assertAlmostEqual(samples[0][2], 0.5, places=1)
        self.assertAlmostEqual(samples[0][3], 1500)
        self.assertAlmostEqual(samples[1][2], 90.25, places=1)
        self.assertAlmostEqual(samples[1][3], 320.5)
        self.assertEqual(rest, b'')


class LidarFrameTest(unittest.TestCase):
    """O sensor mede no sentido horário; o robô usa anti-horário (esquerda positivo)"""

    def scan_from(self, lidar, points):
        lidar._publish(points)
        return lidar.get_scan()

    def test_clockwise_sensor_to_robot_frame(self):
        angles, ranges = self.scan_from(sensors.LidarBase(), [(0, 1000), (90, 2000), (270, 3000)])
        by_angle = {round(math.degrees(a)): r for a, r in zip(angles, ranges)}
        self.assertAlmostEqual(by_angle[0], 1.0)
        self.assertAlmostEqual(by_angle[-90], 2.0)   # 90° horário = direita
        self.assertAlmostEqual(by_angle[90], 3.0)    # 270° horário = esquerda

    def test_offset_flip_and_invalid_ranges(self):
        lidar = sensors.LidarBase(angle_offset_deg=180, flip=True)
        angles, ranges = self.scan_from(lidar, [(0, 1000), (10, 0), (20, 50000)])
        self.assertAlmostEqual(abs(math.degrees(angles[np.argmax(ranges)])), 180, places=3)
        self.assertEqual(int((ranges == 0).sum()), 2)


if __name__ == '__main__':
    unittest.main()
