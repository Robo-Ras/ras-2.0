"""Cinemática do robô de 3 rodas omnidirecionais (a 120° entre si) e calibração dos motores.

Tudo que decide QUANTO enviar a cada motor fica aqui; o Arduino só recebe "m1,m2,m3" e aplica como PWM
(arduino_robot_control.ino, que não muda). Por isso os limites de PWM também são impostos aqui:
abaixo de MIN_PWM o motor não gira, e o robô nunca deve passar de MAX_PWM.

Geometria (vista de cima; x = frente, y = esquerda; ângulo 0° = frente, positivo = anti-horário):

            frente (0°)
               M2
              /  \\
     M1 ---- /    \\ ---- M3
   trás-esquerda      trás-direita
      (+120°)            (-120°)

Cada roda empurra o robô ao longo da tangente ao círculo, no sentido horário quando o motor é positivo
(é por isso que "girar horário" é M1 = M2 = M3 > 0). A direção em que o robô anda quando só a roda i é
acionada com valor positivo é d_i = (sen φ_i, -cos φ_i):

    M1 (+120°): d = (+0,866, +0,5)     M2 (0°): d = (0, -1)     M3 (-120°): d = (-0,866, +0,5)

Velocidade de cada roda para andar com (vx, vy) girando rot (horário positivo):  w_i = d_i · (vx, vy) + rot.
Isso reproduz o que o robô faz: "frente" = (+, 0, -) e "lado" = roda da frente com força total e as duas de
trás com metade cada (e não "uma roda parada", que dava diagonal).

Os motores não têm a mesma força (o da frente é bem mais forte; o da esquerda um pouco mais que o da direita).
Para a roda i render w_i, o PWM é proporcional a w_i / ganho_i: o ganho é "quanto de velocidade cada unidade de
PWM dá". Só a razão entre os ganhos importa, e ela não pode passar de 2:1 (MAX_GAIN_RATIO).
"""

import json
import math
import os
from dataclasses import dataclass, field

# Velocidade ("nível"): o padrão do sistema é 60 e a conta de limites é feita nele. No nível 60 os motores trabalham
# entre 50 e 100: o mais forte (o da frente) no MÍNIMO e o mais fraco (o da direita) no MÁXIMO, no máximo 2:1 de
# diferença para não acelerar demais. Em outro nível tudo escala junto (nível 100 = 1,67x: mínimo ~83, máximo ~167).
BASE_LEVEL = 60
LEVEL_MIN, LEVEL_MAX = 60, 100  # abaixo de 60 o motor da frente cairia abaixo do mínimo que gira
PWM_MIN_BASE = 50  # no nível 60: o menor PWM de um motor em uso (o mais forte, com a roda a 100%)
PWM_MAX_BASE = 100  # no nível 60: o maior PWM (o mais fraco com a roda a 100%); nenhum motor passa disso (x o nível)
MAX_GAIN_RATIO = PWM_MAX_BASE / PWM_MIN_BASE  # diferença máxima de força entre motores: 2:1
MIN_RUN_PWM = 50  # abaixo disso o motor não gira (vale em qualquer nível)
# Roda que a conta pede só um pouco (menos que isto) fica parada; mais que isto, recebe pelo menos MIN_RUN_PWM.
# Deixar parada uma roda que devia ajudar faz o robô PIVOTAR (só uma roda empurra); no robô real, a diagonal 9
# (que tinha a roda M1 zerada) girava muito, e a 7 (a roda pequena elevada a 50) saía certa.
ZERO_BAND_PWM = MIN_RUN_PWM / 4
HARD_MAX_PWM = math.ceil(PWM_MAX_BASE * LEVEL_MAX / BASE_LEVEL)  # teto absoluto, até nos comandos brutos (167)

WHEEL_ANGLES_DEG = (120.0, 0.0, -120.0)  # M1 trás-esquerda, M2 frente, M3 trás-direita
WHEEL_DIRS = tuple((math.sin(math.radians(a)), -math.cos(math.radians(a))) for a in WHEEL_ANGLES_DEG)

# Teclado numérico: cada dígito é uma direção (vx frente, vy esquerda). 5 = parar.
#   7 ↖   8 ↑   9 ↗
#   4 ←   5 ■   6 →
#   1 ↙   2 ↓   3 ↘
NUMPAD = {
    7: (1, 1), 8: (1, 0), 9: (1, -1),
    4: (0, 1), 5: (0, 0), 6: (0, -1),
    1: (-1, 1), 2: (-1, 0), 3: (-1, -1),
}

KEYS = ('1', '2', '3', '4', '5', '6', '7', '8', '9', 'cw', 'ccw')
# Direções com valor ajustável à mão (o 5 é parar)
TUNABLE_KEYS = ('8', '9', '6', '3', '2', '1', '4', '7', 'cw', 'ccw')

# Nomes de direção usados pelo resto do sistema (voz, modo autônomo) -> (vx, vy, giro horário)
DIRECTIONS = {
    'forward': (1, 0, 0), 'backward': (-1, 0, 0), 'left': (0, 1, 0), 'right': (0, -1, 0),
    'forward_left': (1, 1, 0), 'forward_right': (1, -1, 0), 'backward_left': (-1, 1, 0), 'backward_right': (-1, -1, 0),
    'rotate_right': (0, 0, 1), 'rotate_left': (0, 0, -1),  # horário / anti-horário no lugar
    'stop': (0, 0, 0),
}

CALIBRATION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'calibracao_robo.json')

# Os motores reais do robô (estimativa inicial: o da frente "por muito" o mais forte, com a diferença máxima de 2:1;
# o da esquerda "um pouco" mais forte que o da direita). A calibração na prática ajusta isso (veja COMO_RODAR.md).
DEFAULT_GAINS = (1.10, 2.00, 1.00)

# Valores acertados no robô de verdade (nível 60), que valem no lugar da conta:
#  - frente: achada na prática (ajuste dos controles até ir quase reta); trás: o INVERSO exato da frente;
#  - giro (Q/E): os três motores com o mesmo valor, 60 (era assim no original e o robô girava certo);
#  - lado (4 e 6): cada um ajustado à mão na prática, o 4 e o 6 NÃO são o inverso um do outro (os motores rendem
#    diferente conforme o sentido), por isso valem os dois valores medidos;
#  - diagonal 9: ajustada na prática; a 1 é o inverso exato dela.
# As diagonais 7 e 3 seguem a cinemática (confirmadas no robô): mexer nos ganhos e correções globais para acertar a
# frente piorou todas as demais, então o ajuste fica só nas teclas abaixo.
TUNED_KEYS = {
    '8': [67, 0, -59], '2': [-67, 0, 59],
    'cw': [60, 60, 60], 'ccw': [-60, -60, -60],
    '9': [50, 50, -97], '1': [-50, -50, 97],
    '4': [63, -95, 50], '6': [-50, 95, -50],
}

# Tecla oposta (o inverso): andar para o lado contrário com os motores girando ao contrário
OPPOSITE_KEY = {'8': '2', '2': '8', '4': '6', '6': '4', '7': '3', '3': '7', '9': '1', '1': '9', 'cw': 'ccw', 'ccw': 'cw'}


@dataclass
class Calibration:
    # Força relativa de M1 (trás-esquerda), M2 (frente) e M3 (trás-direita): velocidade da roda por unidade de PWM
    ganhos: list = field(default_factory=lambda: list(DEFAULT_GAINS))
    # Correção para andar reto, como fração da velocidade ao andar para frente/trás.
    # Positivo empurra para a DIREITA (use se o robô ainda puxa para a esquerda), negativo para a esquerda.
    correcao_lateral: float = 0.0
    # Giro adicionado ao andar (horário positivo), também como fração. Use se o robô curva em vez de ir reto.
    correcao_giro: float = 0.0
    # Valores de PWM ajustados à mão para uma tecla, no nível 60 (ex.: {"4": [50, -80, 50]}). Valem no lugar da
    # conta daquela tecla (e escalam com a velocidade); as outras teclas continuam pela cinemática.
    teclas: dict = field(default_factory=dict)

    def validate(self):
        if len(self.ganhos) != 3 or any(float(g) <= 0 for g in self.ganhos):
            raise ValueError('ganhos: três valores positivos')
        if max(self.ganhos) / min(self.ganhos) > MAX_GAIN_RATIO + 1e-6:
            raise ValueError(f'ganhos: o motor mais forte pode ser no máximo {MAX_GAIN_RATIO:g}x o mais fraco')
        if not -0.5 <= float(self.correcao_lateral) <= 0.5 or not -0.5 <= float(self.correcao_giro) <= 0.5:
            raise ValueError('correções: entre -0,5 e 0,5')
        clean = {}
        for key, vec in dict(self.teclas).items():
            if str(key) not in TUNABLE_KEYS:  # o 5 (parar) não tem valor
                raise ValueError(f'tecla inválida: {key!r}')
            if len(vec) != 3 or any(not isinstance(v, (int, float)) or isinstance(v, bool) for v in vec):
                raise ValueError(f'tecla {key}: três valores de PWM (M1, M2, M3)')
            vec = [int(round(v)) for v in vec]
            if any(v != 0 and not PWM_MIN_BASE <= abs(v) <= PWM_MAX_BASE for v in vec):
                raise ValueError(f'tecla {key}: cada motor 0 ou entre {PWM_MIN_BASE} e {PWM_MAX_BASE} (nível {BASE_LEVEL})')
            clean[str(key)] = vec
        self.teclas = clean
        self.ganhos = [float(g) for g in self.ganhos]
        self.correcao_lateral = float(self.correcao_lateral)
        self.correcao_giro = float(self.correcao_giro)
        return self

    @classmethod
    def tuned(cls):
        """A calibração do robô de verdade: a cinemática mais as teclas acertadas na prática (frente e trás)."""
        return cls(teclas={k: list(v) for k, v in TUNED_KEYS.items()})

    def to_dict(self):
        return {'ganhos': list(self.ganhos), 'correcao_lateral': self.correcao_lateral,
                'correcao_giro': self.correcao_giro, 'teclas': {k: list(v) for k, v in self.teclas.items()}}

    def save(self, path=None):
        path = path or CALIBRATION_FILE
        tmp = path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
            f.write('\n')
        os.replace(tmp, path)  # troca atômica: nunca fica um arquivo pela metade

    @classmethod
    def load(cls, path=None):
        path = path or CALIBRATION_FILE
        try:
            with open(path, encoding='utf-8') as f:
                data = json.load(f)
            return cls(**{k: data[k] for k in ('ganhos', 'correcao_lateral', 'correcao_giro', 'teclas') if k in data}).validate()
        except (OSError, ValueError, TypeError):
            return cls.tuned()  # sem arquivo (ou inválido): a calibração acertada no robô


def wheel_speeds(vx, vy, rot, cal=None):
    """Velocidade desejada de cada roda (sem PWM) para andar (vx, vy) girando rot, já com as correções."""
    cal = cal or Calibration()
    n = math.hypot(vx, vy)
    if n > 1e-9:
        vx, vy = vx / n, vy / n  # diagonais com o mesmo "tamanho" dos eixos
        vy -= cal.correcao_lateral * abs(vx)  # + = empurra para a direita
        rot += cal.correcao_giro * n
    return [dx * vx + dy * vy + rot for dx, dy in WHEEL_DIRS]


def pwm_limits(level):
    """(mínimo, máximo) de PWM dos motores no nível pedido: 50 e 100 no nível 60, e sobem juntos com o nível."""
    k = clamp_level(level) / BASE_LEVEL
    return PWM_MIN_BASE * k, PWM_MAX_BASE * k


def clamp_level(level):
    return max(LEVEL_MIN, min(LEVEL_MAX, level))


def compose(vx, vy, rot, level=BASE_LEVEL, cal=None):
    """PWM (m1, m2, m3) inteiros para andar (vx, vy) girando rot, na velocidade `level` (padrão 60).

    - Roda a 100% (|w| = 1): o motor mais fraco recebe o PWM máximo do nível (100 no 60) e os outros menos,
      na proporção dos ganhos (o mais forte recebe 50 no nível 60).
    - Nenhum motor passa do máximo do nível; se a conta pedir mais, tudo diminui junto (a direção se mantém).
    - Valor abaixo de 50 não gira de verdade: vira 0 só se for quase nada (menos de ZERO_BAND_PWM = 12,5) e 50
      nos demais (uma roda que precisa ajudar não pode ficar parada, senão o robô pivota).
    """
    cal = cal or Calibration()
    level = clamp_level(level)
    pwm_min, pwm_max = pwm_limits(level)
    gmin = min(cal.ganhos)
    raw = [w * pwm_max * gmin / g for w, g in zip(wheel_speeds(vx, vy, rot, cal), cal.ganhos)]
    peak = max(abs(r) for r in raw)
    if peak < 1e-9:
        return (0, 0, 0)
    if peak > pwm_max:
        raw = [r * pwm_max / peak for r in raw]
    out = []
    for r in raw:
        pwm = abs(r)
        if pwm < ZERO_BAND_PWM:
            pwm = 0
        elif pwm < MIN_RUN_PWM:
            pwm = MIN_RUN_PWM
        out.append(int(round(math.copysign(pwm, r))) if pwm else 0)
    return tuple(out)


# direção por nome -> tecla (a voz e o modo autônomo usam os nomes; valem o mesmo valor da tecla)
NAME_TO_KEY = {
    'forward': '8', 'backward': '2', 'left': '4', 'right': '6',
    'forward_left': '7', 'forward_right': '9', 'backward_left': '1', 'backward_right': '3',
    'rotate_right': 'cw', 'rotate_left': 'ccw',
}


def _from_override(vec, level):
    """Valor ajustado à mão (nível 60) levado para o nível pedido: escala junto, sem passar do teto e sem ficar
    abaixo do mínimo que gira."""
    k = clamp_level(level) / BASE_LEVEL
    out = []
    for v in vec:
        if v == 0:
            out.append(0)
            continue
        scaled = int(round(abs(v) * k))
        out.append(int(math.copysign(max(MIN_RUN_PWM, min(HARD_MAX_PWM, scaled)), v)))
    return tuple(out)


def numpad_vector(key, level=BASE_LEVEL, cal=None):
    """PWM da direção de uma tecla do teclado numérico (1-9; 5 = parar), ou do giro ('cw' / 'ccw')."""
    cal = cal or Calibration()
    if str(key) in cal.teclas:
        return _from_override(cal.teclas[str(key)], level)
    if key in ('cw', 'ccw'):
        return compose(0, 0, 1 if key == 'cw' else -1, level, cal)
    vx, vy = NUMPAD[int(key)]
    return compose(vx, vy, 0, level, cal)


def direction_vector(direction, level=BASE_LEVEL, cal=None):
    """PWM de uma direção pelo nome ('forward', 'left', 'rotate_right'...), ou None se não existe."""
    if direction == 'stop':
        return (0, 0, 0)
    if direction not in NAME_TO_KEY:
        return None
    return numpad_vector(NAME_TO_KEY[direction], level, cal)


def key_table(level=BASE_LEVEL, cal=None):
    """PWM de cada tecla ajustável, como o sistema está usando agora (conta ou ajuste à mão)."""
    return {key: list(numpad_vector(int(key) if key.isdigit() else key, level, cal)) for key in TUNABLE_KEYS}


def clamp_pwm(value):
    """Teto absoluto de PWM em qualquer comando enviado ao Arduino (inclusive os brutos do painel)."""
    return max(-HARD_MAX_PWM, min(HARD_MAX_PWM, int(value)))
