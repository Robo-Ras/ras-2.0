"""Escuta do José: uma transcrição por frase, nenhuma no silêncio, "José" tolerante a erros do Whisper"""

import os
import sys
import time
import unittest

import numpy as np

os.environ.setdefault("GEMINI_API_KEY", "teste")  # nada aqui chama o Gemini
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import jose  # noqa: E402

SR = jose.SAMPLE_RATE


class Segmento:
    def __init__(self, text):
        self.text = text


class ModeloFalso:
    """Faz o papel do WhisperModel: guarda como foi chamado."""

    def __init__(self, texto="vai pra frente"):
        self.texto = texto
        self.chamadas = []

    def transcribe(self, audio, **kwargs):
        self.chamadas.append((audio.size / SR, kwargs))
        return [Segmento(self.texto)], None


class ChamarJoseTest(unittest.TestCase):
    def test_aceita_o_jose_e_erros_comuns_do_reconhecimento(self):
        self.assertEqual(jose.apos_chamar_jose("jose vai pra frente"), "vai pra frente")
        self.assertEqual(jose.apos_chamar_jose("jome, vai pra frente"), "vai pra frente")
        self.assertEqual(jose.apos_chamar_jose("jone me segue"), "me segue")
        self.assertEqual(jose.apos_chamar_jose("jose"), "")

    def test_ignora_frases_sem_jose(self):
        self.assertIsNone(jose.apos_chamar_jose("vai pra frente"))
        self.assertIsNone(jose.apos_chamar_jose("jornal de hoje"))
        self.assertIsNone(jose.apos_chamar_jose(""))

    def test_o_comando_depois_do_jose_e_entendido(self):
        resto = jose.apos_chamar_jose(jose.normalizar("José, vai pra frente!"))
        self.assertEqual(jose.identificar_comando(resto)[1], "frente")


class FraseTest(unittest.TestCase):
    """Alimenta o OuvinteDeAudio em tempo real, em blocos de 0,1 s, como o microfone."""

    def setUp(self):
        self.modelo = ModeloFalso()
        self.ouvinte = jose.OuvinteDeAudio(self.modelo)
        self.ouvinte._running.set()
        import threading
        threading.Thread(target=self.ouvinte._process_loop, daemon=True).start()
        self.rng = np.random.default_rng(1)

    def tearDown(self):
        self.ouvinte._running.clear()

    def tocar(self, segundos, amplitude):
        for _ in range(int(segundos * 10)):
            bloco = (self.rng.standard_normal(SR // 10) * amplitude).astype(np.float32)
            with self.ouvinte._lock:
                self.ouvinte._buffer.append(bloco.reshape(-1, 1))
            time.sleep(0.1)

    def test_silencio_nao_gasta_transcricao(self):
        self.tocar(2.5, 0.0015)
        self.assertEqual(self.modelo.chamadas, [])
        self.assertTrue(self.ouvinte.text_queue.empty())

    def test_uma_frase_vira_uma_so_transcricao(self):
        self.tocar(0.5, 0.0015)
        self.tocar(1.5, 0.1)  # fala
        self.tocar(1.2, 0.0015)  # silêncio: fecha a frase
        texto, _, duracao_audio, _ = self.ouvinte.text_queue.get(timeout=3)
        self.assertEqual(texto, "vai pra frente")
        self.assertEqual(len(self.modelo.chamadas), 1)
        self.assertGreaterEqual(duracao_audio, 1.4)

    def test_transcricao_rapida_sem_tentativas_repetidas(self):
        self.tocar(1.0, 0.1)
        self.tocar(1.2, 0.0015)
        self.ouvinte.text_queue.get(timeout=3)
        kwargs = self.modelo.chamadas[0][1]
        self.assertEqual(kwargs["temperature"], 0.0)  # sem fallback de temperatura (triplicava o tempo)
        self.assertEqual(kwargs["beam_size"], 1)
        self.assertLessEqual(kwargs["max_new_tokens"], 48)  # corta laços de repetição

    def test_barulho_constante_nao_vira_fala_infinita(self):
        # Local barulhento (energia 0,03 o tempo todo): nos primeiros ~3 s o José ainda aprende o ruído
        # (no máximo uma transcrição à toa); depois o limite se adapta e ele para de "ouvir fala"
        self.tocar(9.0, 0.03)
        self.assertLessEqual(len(self.modelo.chamadas), 1)
        antes = len(self.modelo.chamadas)
        self.tocar(3.0, 0.03)
        self.assertEqual(len(self.modelo.chamadas), antes)


if __name__ == "__main__":
    unittest.main()
