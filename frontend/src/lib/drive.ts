// Direções do robô pelo teclado numérico. O frontend só manda a TECLA ("só o valor"); quem calcula quanto vai
// para cada motor é o backend (backend/kinematics.py), com a calibração dos motores.
//
//   7 ↖   8 ↑   9 ↗
//   4 ←   5 ■   6 →      5 para o robô
//   1 ↙   2 ↓   3 ↘      giro no lugar: 'ccw' (anti-horário) e 'cw' (horário)

export type DriveKey = 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 'cw' | 'ccw';

// Nível de velocidade: o padrão é 60 e vai até 100 (abaixo de 60 o motor mais forte não giraria)
export const SPEED_DEFAULT = 60;
export const SPEED_MIN = 60;
export const SPEED_MAX = 100;

export const NUMPAD_ROWS: DriveKey[][] = [
  [7, 8, 9],
  [4, 5, 6],
  [1, 2, 3],
];

export const DRIVE_KEY_LABELS: Record<string, string> = {
  7: 'Frente-esquerda', 8: 'Frente', 9: 'Frente-direita',
  4: 'Esquerda', 5: 'Parar', 6: 'Direita',
  1: 'Trás-esquerda', 2: 'Trás', 3: 'Trás-direita',
  cw: 'Girar horário', ccw: 'Girar anti-horário',
};

// Teclas do teclado: o dígito vale como está (numérico ou fileira de cima); W A S D e setas continuam valendo
export const keyToDrive = (key: string): DriveKey | null => {
  if (/^[1-9]$/.test(key)) return Number(key) as DriveKey;
  switch (key.toLowerCase()) {
    case 'w': case 'arrowup': return 8;
    case 's': case 'arrowdown': return 2;
    case 'a': case 'arrowleft': return 4;
    case 'd': case 'arrowright': return 6;
    case 'q': return 'ccw';
    case 'e': return 'cw';
    case ' ': return 5;
    default: return null;
  }
};

export const clampSpeed = (speed: number) => Math.max(SPEED_MIN, Math.min(SPEED_MAX, speed));
