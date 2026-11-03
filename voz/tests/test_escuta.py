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


class PalavraChaveTest(unittest.TestCase):
    """O que vale é a palavra-chave ("frente"), não a frase inteira ("vai pra frente")."""

    def comando(self, texto):
        achado = jose.identificar_comando(jose.normalizar(texto))
        return achado[1] if achado else None

    def test_so_a_palavra_ja_basta(self):
        for texto, esperado in [("frente", "frente"), ("Trás", "tras"), ("atrás", "tras"), ("ré", "tras"),
                                ("Direita", "direita"), ("esquerda!", "esquerda")]:
            self.assertEqual(self.comando(texto), esperado, texto)

    def test_frase_com_a_palavra_no_meio(self):
        for texto, esperado in [("vai pra frente", "frente"), ("Vai para frente.", "frente"),
                                ("por favor, ande para a esquerda", "esquerda"), ("vira à direita", "direita"),
                                ("avança", "frente"), ("recua um pouco", "tras")]:
            self.assertEqual(self.comando(texto), esperado, texto)

    def test_primeira_palavra_vale(self):
        self.assertEqual(self.comando("esquerda e depois frente"), "esquerda")

    def test_giros_seguir_e_lado(self):
        self.assertEqual(self.comando("dê meia volta"), "meia_volta")
        self.assertEqual(self.comando("dê uma volta completa"), "volta_completa")
        self.assertEqual(self.comando("me segue"), "me_segue")
        self.assertEqual(self.comando("fica do meu lado esquerdo"), "lado_esquerdo")  # não vira "esquerda"
        self.assertEqual(self.comando("fica do meu lado direito"), "lado_direito")

    def test_parar_tem_prioridade_e_nao_confunde_com_para_frente(self):
        self.assertEqual(self.comando("para!"), "parar")
        self.assertEqual(self.comando("vai pra frente e para"), "parar")
        self.assertEqual(self.comando("vai para frente"), "frente")  # "para" aqui é preposição

    def test_conversa_comum_nao_vira_comando(self):
        for texto in ("bom dia", "tudo bem com você", "obrigado", ""):
            self.assertIsNone(self.comando(texto), texto)


class ChamarSemJoseTest(unittest.TestCase):
    """Comando ouvido sem ninguém chamar o José: mostra uma dica na tela (ou executa, se o José não exigir)."""

    class BackendFalso:
        def __init__(self):
            self.conectado = type("E", (), {"is_set": staticmethod(lambda: True)})()
            self.enviados = []

        def limpar_eventos(self):
            pass

        def enviar(self, comando, texto):
            self.enviados.append(comando)

        def eventos_pendentes(self):
            return []

    def setUp(self):
        self.backend = self.BackendFalso()
        self.app = jose.AssistenteApp(jose.OuvinteDeAudio(ModeloFalso()), self.backend)
        self.exige = jose.EXIGE_CHAMAR

    def tearDown(self):
        jose.EXIGE_CHAMAR = self.exige

    def test_sem_chamar_nao_anda_mas_avisa(self):
        jose.EXIGE_CHAMAR = True
        self.app._processar_texto("Vai para frente.")
        self.assertEqual(self.backend.enviados, [])
        self.assertEqual(self.app.estado()["estado"], "acordado")
        self.assertIn("José", self.app.estado()["dica"])

    def test_chamando_o_jose_na_mesma_frase_anda(self):
        jose.EXIGE_CHAMAR = True
        self.app._processar_texto("José, frente")
        self.assertEqual(self.backend.enviados, ["frente"])
        self.assertEqual(self.app.estado()["dica"], "")

    def test_sem_exigir_chamar_a_palavra_basta(self):
        jose.EXIGE_CHAMAR = False
        self.app._processar_texto("frente")
        self.assertEqual(self.backend.enviados, ["frente"])

    def test_conversa_comum_sem_jose_nao_avisa_nada(self):
        jose.EXIGE_CHAMAR = True
        self.app._processar_texto("bom dia pessoal")
        self.assertEqual(self.app.estado()["dica"], "")
        self.assertEqual(self.backend.enviados, [])


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
