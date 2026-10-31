// Valores dos 3 motores (M1, M2, M3) para cada direção. É a única definição:
// o painel (DirectionalControl) e a página do celular (/controle) usam as mesmas.
// Frente/trás foram invertidos após o teste no robô real.

export type Direction = 'forward' | 'backward' | 'left' | 'right' | 'clockwise' | 'counterclockwise';

export const driveVector = (direction: Direction, speed: number): [number, number, number] => {
  const turn = Math.round(speed * 0.6); // giro no lugar usa 60% da velocidade
  switch (direction) {
    case 'forward':
      return [speed, 0, -speed];
    case 'backward':
      return [-speed, 0, speed];
    case 'right':
      return [0, speed, -speed];
    case 'left':
      return [0, -speed, speed];
    case 'clockwise':
      return [turn, turn, turn];
    case 'counterclockwise':
      return [-turn, -turn, -turn];
  }
};
