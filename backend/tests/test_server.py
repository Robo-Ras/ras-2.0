"""
Sobe o backend em modo --sim e conversa com ele pelo WebSocket,
mandando exatamente as mensagens que o frontend manda
"""

import asyncio
import base64
import json
import math
import os
import sys
import unittest

import cv2
import numpy as np
import websockets

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import robot_autonomous_control as rac  # noqa: E402


class Client:
    def __init__(self, ws):
        self.ws = ws

    async def send(self, **message):
        await self.ws.send(json.dumps(message))

    async def wait_for(self, msg_type, predicate=lambda m: True, timeout=10):
        async def loop():
            while True:
                message = json.loads(await self.ws.recv())
                if message.get('type') == msg_type and predicate(message):
                    return message
        return await asyncio.wait_for(loop(), timeout)


class SimServerTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        args = rac.parse_args(['--sim'])
        self.server, self.world = rac.build_system(args)
        self.server.sensors.start()
        self.server.robot.connect(rac.SIM_PORT)
        ready = asyncio.get_running_loop().create_future()
        self.task = asyncio.create_task(self.server.start_server('127.0.0.1', 0, ready))
        ws_server = await ready
        self.port = ws_server.sockets[0].getsockname()[1]

    async def asyncTearDown(self):
        self.task.cancel()
        try:
            await self.task
        except asyncio.CancelledError:
            pass
        self.server.sensors.stop()
        self.server.executor.shutdown(wait=True)
        self.world.stop_realtime()

    def connect(self):
        return websockets.connect(f'ws://127.0.0.1:{self.port}', max_size=2**22)

    async def test_initial_state_and_sensor_stream(self):
        async with self.connect() as ws:
            c = Client(ws)
            ports = await c.wait_for('ports_list')
            self.assertIn('SIM', ports['ports'])
            serial_status = await c.wait_for('serial_status')
            self.assertTrue(serial_status['connected'])

            data = await c.wait_for('sensor_data', lambda m: 'camera_image' in m and 'lidar_scan' in m)
            image = cv2.imdecode(np.frombuffer(base64.b64decode(data['camera_image']), np.uint8), cv2.IMREAD_COLOR)
            self.assertEqual(image.shape, (480, 640, 3))
            self.assertGreaterEqual(len(data['lidar_scan']['angles']), 300)
            self.assertEqual(len(data['lidar_scan']['angles']), len(data['lidar_scan']['ranges']))
            for sector in ('left', 'center', 'right'):
                self.assertIn(sector, data['ground_obstacles']['distances'])
            self.assertTrue(data['sensors_status']['camera']['online'])
            self.assertTrue(data['sensors_status']['lidar']['online'])
            self.assertFalse(data['sensors_status']['realsense']['online'])
            self.assertEqual(data['tracking_mode'], 'basic')

    async def test_manual_drive_moves_simulated_robot(self):
        async with self.connect() as ws:
            c = Client(ws)
            await c.wait_for('sensor_data')
            x0, y0, theta = self.world.pose()
            await c.send(type='move', m1=-150, m2=0, m3=150)     # botão "frente"
            moving = await c.wait_for('sensor_data', lambda m: m['robot_moving'])
            self.assertTrue(moving['robot_moving'])
            await asyncio.sleep(0.6)
            await c.send(type='move', m1=0, m2=0, m3=0)
            x1, y1, _ = self.world.pose()
            travelled = math.hypot(x1 - x0, y1 - y0)
            self.assertGreater(travelled, 0.1)
            heading = math.atan2(y1 - y0, x1 - x0)
            self.assertLess(abs(math.atan2(math.sin(heading - theta), math.cos(heading - theta))), 0.2)
            await asyncio.sleep(0.2)
            self.assertEqual(self.world.wheels, (0, 0, 0))

    async def test_autonomous_mode_and_stop(self):
        async with self.connect() as ws:
            c = Client(ws)
            await c.send(type='set_autonomous', enabled=True, speed=120)
            status = await c.wait_for('autonomous_status', lambda m: m['enabled'])
            self.assertTrue(status['enabled'])
            nav = await c.wait_for('sensor_data', lambda m: m.get('navigation_status', {}).get('active'))
            detection = nav['navigation_status']['detection']
            self.assertIn(nav['navigation_status']['direction'], ('forward', 'rotate_left', 'rotate_right'))
            self.assertEqual(detection['sensor'], 'LIDAR2D')
            self.assertEqual(set(detection['obstacles']), {'left', 'center', 'right'})

            await asyncio.sleep(2)
            self.assertGreater(self.world.distance_travelled, 0.05)
            self.assertEqual(self.world.collisions, 0)

            await c.send(type='set_autonomous', enabled=False)      # parada de emergência
            await c.wait_for('autonomous_status', lambda m: not m['enabled'])
            await c.wait_for('sensor_data', lambda m: m.get('navigation_status', {}).get('active') is False)
            self.assertEqual(self.world.wheels, (0, 0, 0))

    async def test_serial_disconnect_and_reconnect(self):
        async with self.connect() as ws:
            c = Client(ws)
            await c.send(type='disconnect_serial')
            status = await c.wait_for('serial_status', lambda m: not m['connected'])
            self.assertIsNone(status['port'])
            await c.send(type='connect_serial', port='/dev/ttyNAOEXISTE')
            self.assertFalse((await c.wait_for('serial_status', lambda m: 'connected' in m))['connected'])
            await c.send(type='connect_serial', port='/dev/SIM')
            self.assertTrue((await c.wait_for('serial_status', lambda m: m['connected']))['connected'])

    async def test_bad_messages_do_not_kill_server(self):
        async with self.connect() as ws:
            await ws.send('isto não é json')
            await ws.send(json.dumps({'type': 'comando_desconhecido'}))
            await Client(ws).wait_for('sensor_data')

    async def test_tablet_and_last_client_disconnect_stops_robot(self):
        async with self.connect() as ws:
            c = Client(ws)
            await c.send(type='robot_face_heartbeat')
            await c.wait_for('sensor_data', lambda m: m['tablet_connected'])
            await c.send(type='move', m1=100, m2=100, m3=100)
            await c.wait_for('sensor_data', lambda m: m['robot_moving'])
        await asyncio.sleep(0.3)
        self.assertEqual(self.world.wheels, (0, 0, 0))

    async def test_hold_move_stops_when_not_renewed(self):
        async with self.connect() as ws:
            c = Client(ws)
            await c.wait_for('sensor_data')
            # celular segurando: renova por ~0.5 s e some (dedo solto / Wi-Fi caiu)
            for _ in range(5):
                await c.send(type='move', m1=-100, m2=0, m3=100, hold=True)
                await asyncio.sleep(0.1)
            self.assertNotEqual(self.world.wheels, (0, 0, 0))
            await asyncio.sleep(rac.HOLD_TIMEOUT_S + 0.5)
            self.assertEqual(self.world.wheels, (0, 0, 0))

    async def test_move_without_hold_keeps_going(self):
        async with self.connect() as ws:
            c = Client(ws)
            await c.wait_for('sensor_data')
            await c.send(type='move', m1=-100, m2=0, m3=100)   # botão do painel: sem trava
            await asyncio.sleep(rac.HOLD_TIMEOUT_S + 0.5)
            self.assertNotEqual(self.world.wheels, (0, 0, 0))
            await c.send(type='move', m1=0, m2=0, m3=0)

    async def test_lite_client_gets_no_images(self):
        async with self.connect() as full, self.connect() as lite:
            await Client(lite).send(type='set_lite', enabled=True)
            data_full = await Client(full).wait_for('sensor_data', lambda m: 'camera_image' in m and 'lidar_scan' in m)
            self.assertIn('camera_image', data_full)
            data_lite = await Client(lite).wait_for('sensor_data', lambda m: 'robot_moving' in m)
            for key in rac.LITE_DROPPED_KEYS:
                self.assertNotIn(key, data_lite)
            self.assertIn('sensors_status', data_lite)

    async def test_voice_command_moves_then_stops(self):
        async with self.connect() as ws:
            c = Client(ws)
            await c.wait_for('sensor_data')
            x0, y0, _ = self.world.pose()
            await c.send(type='voice_command', command='frente', text='vai pra frente', source='jose')
            ack = await c.wait_for('voice_command')
            self.assertEqual((ack['command'], ack['status'], ack['source']), ('frente', 'ok', 'jose'))
            self.assertTrue(ack['running'])
            await c.wait_for('sensor_data', lambda m: m['robot_moving'])
            done = await c.wait_for('voice_command_done')
            self.assertEqual(done['command'], 'frente')
            self.assertEqual(self.world.wheels, (0, 0, 0))
            x1, y1, _ = self.world.pose()
            self.assertGreater(math.hypot(x1 - x0, y1 - y0), 0.1)

    async def test_voice_stop_interrupts_move(self):
        async with self.connect() as ws:
            c = Client(ws)
            await c.send(type='voice_command', command='volta_completa', text='volta completa')
            await c.wait_for('sensor_data', lambda m: m['robot_moving'])
            await c.send(type='voice_command', command='parar', text='para')
            ack = await c.wait_for('voice_command', lambda m: m['command'] == 'parar')
            self.assertFalse(ack['running'])
            await asyncio.sleep(0.2)
            self.assertEqual(self.world.wheels, (0, 0, 0))
            await c.send(type='voice_command', command='me_segue', text='me segue')
            ack = await c.wait_for('voice_command', lambda m: m['command'] == 'me_segue')
            self.assertEqual(ack['status'], 'not_implemented')


if __name__ == '__main__':
    unittest.main()
