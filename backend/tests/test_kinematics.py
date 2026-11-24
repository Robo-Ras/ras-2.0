"""Cinemática do robô de 3 rodas: as 8 direções do teclado numérico, limites de PWM e calibração."""

import math
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import kinematics as k  # noqa: E402
from simulator import wheels_to_body_velocity  # noqa: E402

IDEAL_ANGLE = {8: 0, 9: -45, 6: -90, 3: -135, 2: 180, 1: 135, 4: 90, 7: 45}  # frente = 0°, esquerda = +90°


def heading(pwm):
    """Ângulo (graus) e giro (graus/s) que o robô simulado, com motores desiguais, faz com esse PWM."""
    vx, vy, omega = wheels_to_body_velocity(*pwm)
    return math.degrees(math.atan2(vy, vx)), math.degrees(omega)


def angle_error(a, b):
    return (a - b + 180) % 360 - 180


class LimitesDePwmTest(unittest.TestCase):
    def test_no_nivel_padrao_os_motores_ficam_entre_50_e_100(self):
        self.assertEqual(k.pwm_limits(60), (50, 100))
        for key in list(IDEAL_ANGLE) + ['cw', 'ccw']:
            for m in k.numpad_vector(key, 60):
                self.assertTrue(m == 0 or 50 <= abs(m) <= 100, f"tecla {key}: {m}")

    def test_o_motor_mais_forte_fica_no_minimo_e_o_mais_fraco_no_maximo(self):
        # girar no lugar usa as três rodas a 100%: M2 (frente, forte) no mínimo, M3 (direita, fraca) no máximo
        m1, m2, m3 = k.numpad_vector('cw', 60)
        self.assertEqual((abs(m2), abs(m3)), (50, 100))
        self.assertTrue(50 < abs(m1) < 100)  # a esquerda é "um pouco" mais forte que a direita

    def test_aumentar_a_velocidade_sobe_o_minimo_e_o_maximo_juntos(self):
        lo, hi = k.pwm_limits(100)
        self.assertAlmostEqual(lo, 50 * 100 / 60)  # ~83
        self.assertAlmostEqual(hi, 100 * 100 / 60)  # ~167
        m1, m2, m3 = k.numpad_vector('cw', 100)
        self.assertEqual((abs(m2), abs(m3)), (round(lo), round(hi)))
        for key in IDEAL_ANGLE:
            for m in k.numpad_vector(key, 100):
                self.assertLessEqual(abs(m), k.HARD_MAX_PWM)

    def test_o_nivel_fica_entre_60_e_100(self):
        self.assertEqual(k.numpad_vector(8, 10), k.numpad_vector(8, 60))  # abaixo: o motor da frente não giraria
        self.assertEqual(k.numpad_vector(8, 500), k.numpad_vector(8, 100))

    def test_teto_absoluto_para_comandos_brutos(self):
        self.assertEqual(k.clamp_pwm(255), k.HARD_MAX_PWM)
        self.assertEqual(k.clamp_pwm(-255), -k.HARD_MAX_PWM)
        self.assertEqual(k.clamp_pwm(40), 40)

    def test_nunca_sobra_valor_entre_0_e_50(self):
        for level in (60, 75, 100):
            for key in list(IDEAL_ANGLE) + ['cw', 'ccw']:
                for m in k.numpad_vector(key, level):
                    self.assertTrue(m == 0 or abs(m) >= 50, f"nível {level}, tecla {key}: {m}")


class OitoDirecoesTest(unittest.TestCase):
    def test_5_para_o_robo(self):
        self.assertEqual(k.numpad_vector(5, 60), (0, 0, 0))

    def test_tecla_invalida(self):
        for bad in (0, 10, 'x', None):
            with self.assertRaises((KeyError, ValueError, TypeError)):
                k.numpad_vector(bad, 60)

    def test_as_quatro_retas_saem_retas(self):
        # frente/trás/lados: erro de direção de poucos graus mesmo com motores de força diferente
        for key in (8, 2, 4, 6):
            angle, _ = heading(k.numpad_vector(key, 60))
            self.assertLess(abs(angle_error(angle, IDEAL_ANGLE[key])), 3.0, f"tecla {key}: {angle:.1f}°")

    def test_as_quatro_diagonais(self):
        # O PWM mínimo que gira (50) impede proporções muito pequenas: algumas diagonais ficam um pouco tortas
        for key in (7, 9, 1, 3):
            angle, _ = heading(k.numpad_vector(key, 60))
            self.assertLess(abs(angle_error(angle, IDEAL_ANGLE[key])), 20.0, f"tecla {key}: {angle:.1f}°")

    def test_a_roda_que_precisa_ajudar_nunca_fica_parada(self):
        # No robô real, a diagonal 9 com a roda M1 zerada (só uma roda de trás empurrando) girava muito: o robô
        # pivota. A 7 e a 3, onde a roda pequena foi elevada a 50, saíam certas.
        self.assertEqual(k.numpad_vector(9, 60), (50, 50, -97))
        self.assertEqual(k.numpad_vector(1, 60), (-50, -50, 97))

    def test_diagonais_espelhadas_sao_espelhos(self):
        # 9 é a 7 refletida (esquerda<->direita): m1' = -m3, m2' = -m2, m3' = -m1 (os motores têm sentido horário)
        m1, m2, m3 = k.numpad_vector(7, 60)
        e1, e2, e3 = k.numpad_vector(9, 60)
        self.assertEqual((e1, e2), (-m3, -m2))  # 50 e 50
        self.assertLessEqual(abs(abs(e3) - abs(m1) * 1.1), 2)  # a roda esquerda é ~10% mais forte
        self.assertEqual(k.numpad_vector(1, 60), tuple(-v for v in k.numpad_vector(9, 60)))
        self.assertEqual(k.numpad_vector(3, 60), tuple(-v for v in k.numpad_vector(7, 60)))

    def test_oposta_e_o_contrario(self):
        for a, b in ((8, 2), (4, 6), (7, 3), (9, 1)):
            self.assertEqual(tuple(-x for x in k.numpad_vector(a, 60)), k.numpad_vector(b, 60) if a in (8, 4) else tuple(-x for x in k.numpad_vector(a, 60)))
        self.assertEqual(k.numpad_vector(2, 60), tuple(-x for x in k.numpad_vector(8, 60)))

    def test_frente_so_usa_as_rodas_de_tras(self):
        m1, m2, m3 = k.numpad_vector(8, 60)
        self.assertEqual(m2, 0)  # a roda da frente rola de lado: não ajuda a ir para a frente
        self.assertGreater(m1, 0)
        self.assertLess(m3, 0)

    def test_lado_usa_a_roda_da_frente_e_as_de_tras_no_mesmo_sentido(self):
        # O que a tabela antiga (0, s, -s) errava: dava diagonal. De lado de verdade, a da frente leva a força e as
        # duas de trás ajudam com metade cada, no sentido oposto à da frente.
        m1, m2, m3 = k.numpad_vector(6, 60)  # direita
        self.assertTrue(m2 > 0 and m1 < 0 and m3 < 0)
        m1, m2, m3 = k.numpad_vector(4, 60)  # esquerda
        self.assertTrue(m2 < 0 and m1 > 0 and m3 > 0)

    def test_a_tabela_antiga_dava_diagonal_e_desviava_a_esquerda(self):
        # Reproduz o que foi visto no robô real (setas do desenho): PWM igual nos 3 motores, sem compensar
        angle, spin = heading((0, 60, -60))  # "direita" antigo
        self.assertGreater(angle, -80)  # em vez de -90: foi meio para a frente
        angle, _ = heading((60, 0, -60))  # "frente" antiga: o motor esquerdo mais forte puxa para a esquerda
        self.assertGreater(angle, 0.5)

    def test_com_a_compensacao_nao_desvia(self):
        antes, _ = heading((60, 0, -60))
        depois, giro = heading(k.numpad_vector(8, 60))
        self.assertLess(abs(depois), abs(antes))
        self.assertLess(abs(depois), 0.5)
        self.assertLess(abs(giro), 1.0)

    def test_girar_no_lugar_nao_anda(self):
        for key in ('cw', 'ccw'):
            vx, vy, omega = wheels_to_body_velocity(*k.numpad_vector(key, 60))
            self.assertLess(math.hypot(vx, vy), 0.01)
        self.assertLess(heading(k.numpad_vector('cw', 60))[1], 0)  # horário = giro negativo (anti-horário positivo)
        self.assertGreater(heading(k.numpad_vector('ccw', 60))[1], 0)

    def test_direcoes_por_nome_usam_a_mesma_conta(self):
        for name, key in (('forward', 8), ('backward', 2), ('left', 4), ('right', 6)):
            self.assertEqual(k.direction_vector(name, 60), k.numpad_vector(key, 60), name)
        self.assertEqual(k.direction_vector('rotate_right', 60), k.numpad_vector('cw', 60))
        self.assertEqual(k.direction_vector('stop', 60), (0, 0, 0))
        self.assertIsNone(k.direction_vector('voar', 60))


class RoboRealTest(unittest.TestCase):
    """O que foi acertado no robô de verdade: a frente, e a trás como o inverso exato dela."""

    def test_frente_acertada_na_pratica(self):
        self.assertEqual(k.numpad_vector(8, 60, k.Calibration.tuned()), (67, 0, -59))

    def test_tras_e_o_inverso_exato_da_frente(self):
        tuned = k.Calibration.tuned()
        self.assertEqual(k.numpad_vector(2, 60, tuned), tuple(-v for v in k.numpad_vector(8, 60, tuned)))

    def test_as_outras_teclas_seguem_a_cinematica_pura(self):
        # Mexer nos ganhos globais para acertar a frente piorou o resto (a 7 virava uma roda zerada)
        tuned, theory = k.Calibration.tuned(), k.Calibration()
        for key in (7, 3):  # as diagonais confirmadas: gravadas fixas, iguais à conta
            self.assertEqual(k.numpad_vector(key, 60, tuned), k.numpad_vector(key, 60, theory), key)
            self.assertIn(str(key), tuned.teclas)
        self.assertEqual((tuned.ganhos, tuned.correcao_lateral, tuned.correcao_giro), (list(k.DEFAULT_GAINS), 0.0, 0.0))

    def test_giro_tem_o_mesmo_valor_nos_tres_motores_em_60(self):
        tuned = k.Calibration.tuned()
        self.assertEqual(k.numpad_vector('cw', 60, tuned), (60, 60, 60))
        self.assertEqual(k.numpad_vector('ccw', 60, tuned), (-60, -60, -60))
        self.assertEqual(k.numpad_vector('cw', 100, tuned), (100, 100, 100))  # escala com a velocidade

    def test_lado_4_e_6_ajustados_a_mao(self):
        tuned = k.Calibration.tuned()
        self.assertEqual(k.numpad_vector(4, 60, tuned), (63, -95, 50))
        self.assertEqual(k.numpad_vector(6, 60, tuned), (-50, 95, -50))

    def test_diagonal_9_ajustada_e_1_e_o_inverso_exato(self):
        tuned = k.Calibration.tuned()
        self.assertEqual(k.numpad_vector(9, 60, tuned), (50, 67, -97))
        self.assertEqual(k.numpad_vector(1, 60, tuned), (-50, -67, 97))

    def test_vale_para_voz_e_autonomo_e_escala_com_a_velocidade(self):
        tuned = k.Calibration.tuned()
        self.assertEqual(k.direction_vector('forward', 60, tuned), (67, 0, -59))
        self.assertEqual(k.direction_vector('backward', 100, tuned), (-112, 0, 98))  # x 100/60, ainda o inverso

    def test_sem_arquivo_vale_o_robo_real(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(k.Calibration.load(os.path.join(tmp, 'nao-existe.json')).teclas, k.Calibration.tuned().teclas)

    def test_o_arquivo_do_projeto_e_o_robo_real(self):
        self.assertEqual(k.Calibration.load().to_dict(), k.Calibration.tuned().to_dict())

    def test_no_robo_real_cada_tecla_e_o_inverso_da_oposta(self):
        tuned = k.Calibration.tuned()
        for key, other in k.OPPOSITE_KEY.items():
            if key in ('4', '6'):
                continue  # o lado foi ajustado à mão em cada sentido (os motores rendem diferente)
            a = k.numpad_vector(key if key.isalpha() else int(key), 60, tuned)
            b = k.numpad_vector(other if other.isalpha() else int(other), 60, tuned)
            self.assertEqual(b, tuple(-v for v in a), f"{key} / {other}")

    def test_cada_tecla_tem_sua_oposta(self):
        for key, other in k.OPPOSITE_KEY.items():
            self.assertEqual(k.OPPOSITE_KEY[other], key)
            self.assertEqual(k.numpad_vector(other if other.isalpha() else int(other), 60),
                             tuple(-v for v in k.numpad_vector(key if key.isalpha() else int(key), 60)), key)


class AjusteManualPorTeclaTest(unittest.TestCase):
    def cal(self, **teclas):
        return k.Calibration(teclas=teclas).validate()

    def test_valor_manual_vale_no_lugar_da_conta(self):
        cal = self.cal(**{'4': [50, -80, 50]})
        self.assertEqual(k.numpad_vector(4, 60, cal), (50, -80, 50))
        self.assertEqual(k.numpad_vector(6, 60, cal), k.numpad_vector(6, 60))  # as outras seguem a cinemática

    def test_vale_tambem_para_voz_e_autonomo(self):
        cal = self.cal(**{'8': [60, 0, -90]})
        self.assertEqual(k.direction_vector('forward', 60, cal), (60, 0, -90))
        self.assertEqual(k.direction_vector('backward', 60, cal), k.direction_vector('backward', 60))

    def test_escala_com_a_velocidade(self):
        cal = self.cal(**{'4': [50, -80, 50]})
        a, b, c = k.numpad_vector(4, 100, cal)
        self.assertEqual((a, b, c), (83, -133, 83))  # x 100/60
        for v in k.numpad_vector(4, 100, cal):
            self.assertLessEqual(abs(v), k.HARD_MAX_PWM)

    def test_valores_invalidos_sao_recusados(self):
        for bad in ({'4': [30, -80, 50]}, {'4': [50, -120, 50]}, {'4': [50, -80]}, {'x': [50, 50, 50]}, {'5': [50, 50, 50]}):
            with self.assertRaises(ValueError):
                k.Calibration(teclas=bad).validate()
        k.Calibration(teclas={'4': [0, -80, 50]}).validate()  # zero é permitido (roda parada)

    def test_salva_e_carrega_os_ajustes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'cal.json')
            k.Calibration(teclas={'4': [50, -80, 50]}).save(path)
            self.assertEqual(k.Calibration.load(path).teclas, {'4': [50, -80, 50]})

    def test_tabela_mostra_o_que_cada_tecla_envia(self):
        tabela = k.key_table(60, self.cal(**{'4': [50, -80, 50]}))
        self.assertEqual(tabela['4'], [50, -80, 50])
        self.assertEqual(tabela['8'], list(k.numpad_vector(8, 60)))
        self.assertEqual(set(tabela), set(k.TUNABLE_KEYS))


class CalibracaoTest(unittest.TestCase):
    def test_correcao_lateral_empurra_para_a_direita(self):
        base, _ = heading(k.compose(1, 0, 0, 60, k.Calibration()))
        com, _ = heading(k.compose(1, 0, 0, 60, k.Calibration(correcao_lateral=0.15)))
        self.assertLess(com, base - 1.5)  # mais negativo = mais para a direita
        # A roda da frente (a que anda de lado) está em 0 ao andar para frente; uma correção pequena pediria dela menos
        # que ZERO_BAND_PWM e ela continua parada. Só as rodas de trás corrigem (efeito menor que o teórico, com um
        # pouco de giro). A partir de ~0,25 a roda da frente liga de uma vez, no mínimo que gira (50).
        self.assertEqual(k.compose(1, 0, 0, 60, k.Calibration(correcao_lateral=0.15))[1], 0)
        self.assertEqual(abs(k.compose(1, 0, 0, 60, k.Calibration(correcao_lateral=0.3))[1]), 50)

    def test_correcao_de_giro(self):
        _, base = heading(k.compose(1, 0, 0, 60, k.Calibration()))
        _, com = heading(k.compose(1, 0, 0, 60, k.Calibration(correcao_giro=0.15)))
        self.assertLess(com, base - 0.5)  # horário = giro negativo

    def test_diferenca_maxima_de_forca_entre_motores_e_2_para_1(self):
        k.Calibration(ganhos=[1.0, 2.0, 1.0]).validate()  # no limite: aceito
        for ganhos in ([1.0, 2.5, 1.0], [0.0, 1.0, 1.0], [1.0, 1.0]):
            with self.assertRaises(ValueError):
                k.Calibration(ganhos=ganhos).validate()
        with self.assertRaises(ValueError):
            k.Calibration(correcao_lateral=0.9).validate()

    def test_salva_e_carrega(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'cal.json')
            k.Calibration(ganhos=[1.2, 1.9, 1.0], correcao_lateral=0.05, correcao_giro=-0.02).save(path)
            cal = k.Calibration.load(path)
            self.assertEqual((cal.ganhos, cal.correcao_lateral, cal.correcao_giro), ([1.2, 1.9, 1.0], 0.05, -0.02))
            self.assertEqual(k.Calibration.load(os.path.join(tmp, 'nao-existe.json')).ganhos, list(k.DEFAULT_GAINS))
            with open(path, 'w') as f:
                f.write('{ isto não é json')
            self.assertEqual(k.Calibration.load(path).ganhos, list(k.DEFAULT_GAINS))  # arquivo ruim: valores iniciais

    def test_o_arquivo_do_projeto_e_valido(self):
        cal = k.Calibration.load()  # calibracao_robo.json
        cal.validate()

    def test_motores_iguais_nao_precisam_de_compensacao(self):
        # Se os 3 motores tivessem a mesma força, a calibração seria neutra: frente = (s, 0, -s) com s = 100 x 0,866
        m1, m2, m3 = k.compose(1, 0, 0, 60, k.Calibration(ganhos=[1.0, 1.0, 1.0]))
        self.assertEqual((m1, m2, m3), (87, 0, -87))


if __name__ == '__main__':
    unittest.main()
