"""José: dicionário de comandos, escuta pelo Vosk e comportamento (sem IA para andar)"""

import json
import os
import sys
import threading
import time
import unittest

import numpy as np

os.environ.setdefault("GEMINI_API_KEY", "teste")  # nada aqui chama o Gemini
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import comandos  # noqa: E402
import jose  # noqa: E402

SR = jose.SAMPLE_RATE


class DicionarioTest(unittest.TestCase):
    def test_todos_os_exemplos_do_dicionario(self):
        # os mesmos exemplos são conferidos no Chrome (test.sh), para os dois reconhecedores concordarem
        for texto, esperado in comandos.DICIONARIO.dados["exemplos"]:
            self.assertEqual(comandos.interpretar(texto).comando, esperado, texto)

    def test_andar_exige_chamar_o_jose(self):
        self.assertEqual(comandos.interpretar("José, frente").comando, "frente")
        sem = comandos.interpretar("frente")
        self.assertIsNone(sem.comando)
        self.assertTrue(sem.sem_chamar)  # o José mostra a dica "diga José"

    def test_depois_de_chamar_a_palavra_basta(self):
        self.assertEqual(comandos.interpretar("esquerda", chamado=True).comando, "esquerda")

    def test_variacoes_do_reconhecimento(self):
        for texto, esperado in [("José frenti", "frente"), ("jone direita", "direita"), ("José atras", "tras"),
                                ("José recua", "tras"), ("José rodar", "gira"), ("josé dirá", "gira")]:
            self.assertEqual(comandos.interpretar(texto).comando, esperado, texto)

    def test_parar_vale_sozinho_mas_so_se_for_a_unica_palavra(self):
        self.assertEqual(comandos.interpretar("pare").comando, "parar")
        self.assertEqual(comandos.interpretar("para").comando, "parar")
        for conversa in ("eu vou para casa", "vamos para a sala", "pare de falar comigo"):
            self.assertIsNone(comandos.interpretar(conversa).comando, conversa)

    def test_para_frente_nao_e_parar(self):
        self.assertEqual(comandos.interpretar("José vai para frente").comando, "frente")
        self.assertEqual(comandos.interpretar("José, para").comando, "parar")

    def test_primeira_palavra_depois_do_jose_vale(self):
        self.assertEqual(comandos.interpretar("José esquerda depois frente").comando, "esquerda")

    def test_conversa_comum_nao_vira_comando(self):
        for texto in ("bom dia", "tem uma pessoa na frente da porta", "vire na próxima direita", "obrigado", ""):
            self.assertIsNone(comandos.interpretar(texto).comando, texto)

    def test_pedidos_do_proprio_jose(self):
        conversa = comandos.interpretar("José, conversa")
        self.assertEqual((conversa.comando, conversa.tipo), ("conversa", "pedido"))
        self.assertEqual(comandos.interpretar("José história").comando, "historia")

    def test_gramatica_do_vosk_tem_o_dicionario_todo(self):
        gramatica = comandos.DICIONARIO.gramatica()
        for palavra in ("josé", "frente", "trás", "direita", "esquerda", "gira", "pare", "para", "[unk]"):
            self.assertIn(palavra, gramatica)


class ReconhecedorFalso:
    """Faz o papel do KaldiRecognizer: devolve o que o teste mandar, um item por bloco de áudio."""

    def __init__(self, roteiro):
        self.roteiro = list(roteiro)  # ("parcial", texto) | ("final", texto) | ("nada", "")
        self.atual = ("nada", "")
        self.resets = 0

    def AcceptWaveform(self, pcm):
        self.atual = self.roteiro.pop(0) if self.roteiro else ("nada", "")
        return self.atual[0] == "final"

    def Result(self):
        return json.dumps({"text": self.atual[1]})

    def PartialResult(self):
        return json.dumps({"partial": self.atual[1] if self.atual[0] == "parcial" else ""})

    def Reset(self):
        self.resets += 1


class EscutaVoskTest(unittest.TestCase):
    """O OuvinteDeAudio alimentado em tempo real (blocos de 0,1 s) com um reconhecedor falso."""

    def escutar(self, roteiro, blocos=None):
        self.reconhecedor = ReconhecedorFalso(roteiro)
        ouvinte = jose.OuvinteDeAudio(None)
        ouvinte.criar_reconhecedor = lambda: self.reconhecedor
        ouvinte._running.set()
        threading.Thread(target=ouvinte._process_loop, daemon=True).start()
        for _ in range(blocos or len(roteiro) + 3):
            with ouvinte._lock:
                ouvinte._buffer.append(np.full((SR // 10, 1), 0.05, dtype=np.float32))
            time.sleep(0.1)
        ouvinte._running.clear()
        textos = []
        while not ouvinte.text_queue.empty():
            textos.append(ouvinte.text_queue.get()[0])
        return textos

    def test_frase_terminada_vira_um_texto(self):
        self.assertEqual(self.escutar([("nada", ""), ("final", "josé frente")]), ["josé frente"])

    def test_age_antes_do_fim_da_frase_quando_o_parcial_se_firma(self):
        # "josé frente" aparece e se mantém por 0,2 s: não espera o silêncio; o reconhecedor recomeça limpo
        textos = self.escutar([("parcial", "josé"), ("parcial", "josé frente"), ("parcial", "josé frente"),
                               ("parcial", "josé frente"), ("nada", "")])
        self.assertEqual(textos, ["josé frente"])
        self.assertEqual(self.reconhecedor.resets, 1)

    def test_parcial_que_muda_nao_dispara(self):
        # "josé" ... "josé frente" ... mudou de novo: ainda está falando, não é firme
        textos = self.escutar([("parcial", "josé frente"), ("parcial", "josé frente na"), ("parcial", "josé frente na sala")])
        self.assertEqual(textos, [])

    def test_pare_espera_o_fim_da_frase(self):
        # "para" no meio de "para frente" não pode virar parar: o parcial só vale para andar
        textos = self.escutar([("parcial", "josé para"), ("parcial", "josé para"), ("parcial", "josé para"), ("parcial", "josé para")])
        self.assertEqual(textos, [])
        textos = self.escutar([("parcial", "josé para"), ("final", "josé para frente")])
        self.assertEqual(textos, ["josé para frente"])

    def test_so_palavra_desconhecida_nao_publica(self):
        self.assertEqual(self.escutar([("final", "[unk]"), ("final", "[unk] [unk]"), ("final", "")]), [])


class JoseTest(unittest.TestCase):
    """Estados do José: o que cada frase reconhecida faz."""

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
        self.app = jose.AssistenteApp(jose.OuvinteDeAudio(None), self.backend)

    def test_jose_e_comando_na_mesma_frase_anda(self):
        self.app._processar_texto("josé frente")
        self.assertEqual(self.backend.enviados, ["frente"])
        self.assertEqual(self.app.estado()["comando"], "Vai pra Frente")

    def test_cada_comando_do_dicionario_chega_ao_backend_com_seu_id(self):
        for texto, id_ in [("josé trás", "tras"), ("josé direita", "direita"), ("josé esquerda", "esquerda"),
                           ("josé gira", "gira")]:
            self.backend.enviados.clear()
            self.app._mostrar_acordado()
            self.app._processar_texto(texto)
            self.assertEqual(self.backend.enviados, [id_], texto)

    def test_sem_chamar_nao_anda_mas_avisa(self):
        self.app._processar_texto("frente")
        self.assertEqual(self.backend.enviados, [])
        self.assertEqual(self.app.estado()["estado"], "acordado")
        self.assertIn("José", self.app.estado()["dica"])

    def test_pare_vale_sem_chamar(self):
        self.app._processar_texto("pare")
        self.assertEqual(self.backend.enviados, ["parar"])

    def test_para_dentro_de_frase_comum_nao_para_o_robo(self):
        self.app._processar_texto("eu vou para casa")
        self.assertEqual(self.backend.enviados, [])

    def test_so_chamar_o_jose_deixa_ele_ouvindo_e_depois_a_palavra_basta(self):
        self.app._processar_texto("josé")
        self.assertEqual(self.app.estado()["estado"], "transicao")
        self.app._novo_estado(self.app.OUVINDO)
        self.app._processar_texto("esquerda")
        self.assertEqual(self.backend.enviados, ["esquerda"])

    def test_conversa_comum_sem_comando_nao_faz_nada(self):
        self.app._processar_texto("bom dia pessoal")
        self.assertEqual(self.app.estado()["dica"], "")
        self.assertEqual(self.backend.enviados, [])


class FraseDaConversaTest(unittest.TestCase):
    """Conversa (Whisper): uma transcrição por frase e nenhuma no silêncio."""

    class ModeloFalso:
        def __init__(self):
            self.chamadas = []

        def transcribe(self, audio, **kwargs):
            self.chamadas.append((audio.size / SR, kwargs))
            return [type("S", (), {"text": "me conta uma coisa"})()], None

    def setUp(self):
        self.modelo = self.ModeloFalso()
        self.ouvinte = jose.OuvinteDeAudio(None)
        self.ouvinte.modelo_conversa = self.modelo
        self.ouvinte.retomar(jose.OuvinteDeAudio.CONVERSA)
        self.ouvinte._running.set()
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

    def test_uma_frase_vira_uma_so_transcricao_rapida(self):
        self.tocar(0.5, 0.0015)
        self.tocar(1.5, 0.1)  # fala
        self.tocar(1.6, 0.0015)  # silêncio: fecha a frase
        texto, _, duracao_audio, audio = self.ouvinte.text_queue.get(timeout=3)
        self.assertEqual(texto, "me conta uma coisa")
        self.assertEqual(len(self.modelo.chamadas), 1)
        kwargs = self.modelo.chamadas[0][1]
        self.assertEqual(kwargs["temperature"], 0.0)  # sem tentativas repetidas (triplicava o tempo)
        self.assertLessEqual(kwargs["max_new_tokens"], 200)

    def test_barulho_constante_nao_vira_fala_infinita(self):
        # Nos primeiros ~3 s o José aprende o ruído (no máximo uma transcrição à toa); depois o limite se adapta
        self.tocar(9.0, 0.03)
        self.assertLessEqual(len(self.modelo.chamadas), 1)
        antes = len(self.modelo.chamadas)
        self.tocar(3.0, 0.03)
        self.assertEqual(len(self.modelo.chamadas), antes)


if __name__ == "__main__":
    unittest.main()
