#!/usr/bin/env python3
"""Arduino falso: imita o arduino_robot_control.ino numa porta serial virtual (pty).

Uso:
    ros2 run omni_drive_controller fake_arduino.py            # cria /tmp/ttyFakeArduino
    ros2 launch omni_drive_controller omni_drive.launch.py port:=/tmp/ttyFakeArduino

Mostra cada comando recebido, igual o Serial Monitor mostraria.
"""
import argparse
import os
import pty
import select
import sys
import time
import tty


def parse(line):
    """Mesmo parse do sketch: "m1,m2,m3" -> (m1, m2, m3) ou None."""
    parts = line.split(',', 2)
    if len(parts) != 3 or not parts[0]:
        return None

    def to_int(s):  # String.toInt() do Arduino: lê o prefixo numérico, senão 0
        s = s.strip()
        num = ''
        for i, ch in enumerate(s):
            if ch.isdigit() or (i == 0 and ch in '+-'):
                num += ch
            else:
                break
        try:
            return max(-255, min(255, int(num)))
        except ValueError:
            return 0

    return tuple(to_int(p) for p in parts)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--link', default='/tmp/ttyFakeArduino', help='symlink para a porta virtual')
    ap.add_argument('--quiet', action='store_true', help='não mostra comandos repetidos')
    args = ap.parse_args()

    master, slave = pty.openpty()
    tty.setraw(slave)  # sem eco/conversões até alguém abrir a porta
    slave_name = os.ttyname(slave)
    if os.path.islink(args.link):
        os.unlink(args.link)
    os.symlink(slave_name, args.link)
    print(f'Arduino falso em {args.link} -> {slave_name}  (Ctrl+C para sair)', flush=True)

    os.write(master, b'Sistema iniciado. Aguardando comandos...\r\n')
    buf = b''
    last = None
    count = 0
    t0 = time.time()
    try:
        while True:
            r, _, _ = select.select([master], [], [], 1.0)
            if not r:
                continue
            try:
                data = os.read(master, 1024)
            except OSError:
                continue
            buf += data
            while b'\n' in buf:
                raw, buf = buf.split(b'\n', 1)
                line = raw.decode(errors='replace').strip()
                if not line:
                    continue
                cmd = parse(line)
                if cmd is None:
                    print(f'[{time.time() - t0:7.2f}s] ignorado: {line!r}', flush=True)
                    continue
                count += 1
                if not (args.quiet and cmd == last):
                    print(f'[{time.time() - t0:7.2f}s] #{count:5d}  M1={cmd[0]:5d}  M2={cmd[1]:5d}  '
                          f'M3={cmd[2]:5d}', flush=True)
                last = cmd
                os.write(master, f'Comando recebido - M1: {cmd[0]}, M2: {cmd[1]}, '
                                 f'M3: {cmd[2]}\r\n'.encode())
    except KeyboardInterrupt:
        pass
    finally:
        if os.path.islink(args.link):
            os.unlink(args.link)
    return 0


if __name__ == '__main__':
    sys.exit(main())
