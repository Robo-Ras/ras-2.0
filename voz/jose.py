# pip install -r requirements.txt
import argparse
import asyncio
import glob
import io
import json
import os
import queue
import random
import re
import signal
import tempfile
import threading
import time
import unicodedata
import wave
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from typing import Literal

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import av
import edge_tts
import numpy as np
import pygame
import sounddevice as sd
from faster_whisper import WhisperModel
from google import genai
from google.genai import types
from pydantic import BaseModel
from websockets.sync.client import connect as ws_connect

SAMPLE_RATE = 16000
CHUNK_SECONDS = 1.5
MAX_BUFFER_SECONDS = CHUNK_SECONDS * 3  # descarta áudio mais antigo se o processamento atrasar
MODEL_SIZE = "small"
LANGUAGE = "pt"
CPU_THREADS = os.cpu_count() or 4

# Modo conversa: modelo maior (mais preciso, mais lento), carregado só na primeira vez que entra no modo
MODELO_CONVERSA = os.environ.get("JOSE_MODELO_CONVERSA", "large-v3-turbo")
BLOCO_VAD_S = 0.1
SILENCIO_FIM_FALA_S = 1.0
FALA_MIN_S = 0.4  # mais curto que isso é estalo/ruído
MAX_FALA_S = 30
ENERGIA_MIN_VOZ = 0.01  # RMS do áudio float32; abaixo disso nunca é fala
FATOR_VOZ = 3.0  # fala = energia acima de 3x o ruído de fundo
MAX_HISTORICO = 10  # mensagens (pergunta + resposta) lembradas na conversa

GEMINI_MODELO = os.environ.get("JOSE_GEMINI_MODELO", "gemini-3.8-flash")
VOZ_TTS = os.environ.get("JOSE_VOZ", "pt-BR-AntonioNeural")
PRE_PROMPT = (
    "Seu nome é José e você é um robô. Responda em português do Brasil com no máximo 50 palavras, "
    "da forma mais simples e acessível possível, evitando temas polêmicos como política, religião e "
    "dilemas políticos e sociais. Ao confrontar um tema desses, responda somente: "
    "\"É melhor perguntar isso a uma pessoa de verdade.\" "
    "Você recebe o áudio da fala e uma transcrição automática que pode ter erros; use o áudio para entender. "
    "Pelo tom de voz do áudio, classifique a emoção predominante de quem fala no campo 'emocao' "
    "(use 'neutro' se não estiver claro) e não mencione a emoção no campo 'resposta'. "
    "A resposta será falada em voz alta: não use emojis, listas nem markdown."
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PASTA_ROSTOS = os.path.join(BASE_DIR, "rostojose")
PASTA_HISTORIAS = os.path.join(BASE_DIR, "historinhas")
PASTA_WEB = os.path.join(BASE_DIR, "web")

# Os rostos são mostrados no navegador (voz/web/index.html), num servidor próprio
PORTA_WEB = 8090
DURACAO_MOVIMENTO_S = 0.3  # o rosto desliza ao ouvir "José"; a animação em si é feita no navegador
DURACAO_AGRADECIMENTO_S = 3
INTERVALO_LOOP_S = 0.05

DIRECOES = {"frente": "Frente", "tras": "Trás", "direita": "Direita", "esquerda": "Esquerda"}
LADOS = {"direito": "Direito", "esquerdo": "Esquerdo"}
# "para" só vale no fim da frase ("Para!"), para não disparar com "vai para a frente" ou "voltou para casa"
RE_PARAR = r"\b(parar|pare)\b|\bpara\b\s*(?:[.!?,]|$)"

# Backend do RAS (backend/robot_autonomous_control.py); recebe os comandos como {"type": "voice_command"}
BACKEND_URL = os.environ.get("RAS_WS_URL", "ws://127.0.0.1:8765")
INTERVALO_RECONEXAO_S = 3
TEMPO_MAX_CONFIRMACAO_S = 3  # sem resposta do backend nesse tempo, volta a ouvir
TEMPO_MAX_EXECUCAO_S = 20


def normalizar(texto: str) -> str:
    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c))


def identificar_comando(texto_normalizado: str):
    """Devolve (texto mostrado na tela, id do comando enviado ao backend) ou None."""
    if re.search(RE_PARAR, texto_normalizado):
        return "Parar", "parar"
    m = re.search(r"vai (?:pra|para) a? ?(frente|tras|direita|esquerda)", texto_normalizado)
    if m:
        return f"Vai pra {DIRECOES[m.group(1)]}", m.group(1)
    if re.search(r"\bme segue\b", texto_normalizado):
        return "Me Segue", "me_segue"
    if re.search(r"meia volta", texto_normalizado):
        return "Dê Meia Volta", "meia_volta"
    if re.search(r"volta completa", texto_normalizado):
        return "Dê Volta Completa", "volta_completa"
    m = re.search(r"fica do meu lado (direito|esquerdo)", texto_normalizado)
    if m:
        return f"Fica do Meu Lado {LADOS[m.group(1)]}", f"lado_{m.group(1)}"
    return None


class ConexaoBackend:
    """Envia os comandos ao backend do robô pelo WebSocket e recebe a confirmação e o fim de cada um."""

    def __init__(self, url: str):
        self.url = url
        self.conectado = threading.Event()
        self.eventos = queue.Queue()  # voice_command (confirmação) e voice_command_done (fim do movimento)
        self._fila = queue.Queue()
        threading.Thread(target=self._loop, daemon=True).start()

    def enviar(self, comando: str, texto: str):
        self._fila.put({"type": "voice_command", "command": comando, "text": texto, "source": "jose"})

    def eventos_pendentes(self):
        while True:
            try:
                yield self.eventos.get_nowait()
            except queue.Empty:
                return

    def limpar_eventos(self):
        for _ in self.eventos_pendentes():
            pass

    def _loop(self):
        while True:
            try:
                with ws_connect(self.url, open_timeout=2, max_size=None) as ws:
                    print(f"✓ Conectado ao backend em {self.url}")
                    self.conectado.set()
                    threading.Thread(target=self._receber, args=(ws,), daemon=True).start()
                    while self.conectado.is_set():
                        try:
                            mensagem = self._fila.get(timeout=0.5)
                        except queue.Empty:
                            continue
                        ws.send(json.dumps(mensagem))
                raise ConnectionError("conexão fechada")
            except Exception as e:
                self.conectado.clear()
                print(f"⚠ Backend indisponível ({self.url}): {e}. Tentando de novo em {INTERVALO_RECONEXAO_S}s")
                # Comando antigo não deve mover o robô quando a conexão voltar
                while not self._fila.empty():
                    self._fila.get_nowait()
                time.sleep(INTERVALO_RECONEXAO_S)

    def _receber(self, ws):
        try:
            for bruto in ws:
                # O backend manda sensor_data (com imagens) o tempo todo: só decodifica o que interessa
                if '"voice_command' not in bruto:
                    continue
                mensagem = json.loads(bruto)
                tipo = mensagem.get("type")
                if tipo == "voice_command_done" or (tipo == "voice_command" and mensagem.get("source") == "jose"):
                    self.eventos.put(mensagem)
        except Exception:
            pass
        finally:
            self.conectado.clear()


class OuvinteDeAudio:
    """Grava o microfone e publica o texto numa fila: em blocos curtos (comandos) ou a frase inteira (conversa)."""

    COMANDOS, CONVERSA = "comandos", "conversa"

    def __init__(self, model, sample_rate=SAMPLE_RATE, chunk_seconds=CHUNK_SECONDS):
        self.model = model
        self.modelo_conversa = None
        self.modo = self.COMANDOS
        self.sample_rate = sample_rate
        self.chunk_seconds = chunk_seconds
        # Itens: (texto, segundos processando, segundos de áudio, áudio da fala ou None)
        self.text_queue = queue.Queue()
        self.transcrevendo_fala = threading.Event()
        self._buffer = []
        self._lock = threading.Lock()
        self._running = threading.Event()
        self._pausado = threading.Event()
        self._geracao = 0  # muda a cada pausa/retomada, para descartar transcrições de áudio antigo
        self._stream = None
        self._worker = None

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            print(status)
        if self._pausado.is_set():
            return
        with self._lock:
            self._buffer.append(indata.copy())

    def pausar(self):
        with self._lock:
            self._pausado.set()
            self._buffer.clear()
            self._geracao += 1

    def retomar(self, modo: str):
        with self._lock:
            self.modo = modo
            self._buffer.clear()
            self._geracao += 1
            self._pausado.clear()

    def _pegar_audio(self):
        with self._lock:
            if not self._buffer:
                return None, self._geracao
            audio = np.concatenate(self._buffer, axis=0).flatten()
            self._buffer.clear()
            return audio, self._geracao

    def _publicar(self, geracao, texto, duracao_processamento, duracao_audio, audio=None):
        with self._lock:
            if geracao == self._geracao:
                self.text_queue.put((texto, duracao_processamento, duracao_audio, audio))

    def start(self):
        self._running.set()
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            callback=self._audio_callback,
        )
        self._stream.start()
        self._worker = threading.Thread(target=self._process_loop, daemon=True)
        self._worker.start()

    def stop(self):
        self._running.clear()
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()

    def _process_loop(self):
        proxima_leitura = time.monotonic() + self.chunk_seconds
        while self._running.is_set():
            if self.modo == self.CONVERSA:
                self._ouvir_fala()
                proxima_leitura = time.monotonic() + self.chunk_seconds
                continue
            # Desconta o tempo gasto transcrevendo, senão cada bloco fica maior e mais lento que o anterior
            time.sleep(max(0.0, proxima_leitura - time.monotonic()))
            proxima_leitura = time.monotonic() + self.chunk_seconds
            audio, geracao = self._pegar_audio()
            if audio is None or audio.size == 0:
                continue
            max_amostras = int(MAX_BUFFER_SECONDS * self.sample_rate)
            if audio.size > max_amostras:
                audio = audio[-max_amostras:]  # descarta o áudio mais antigo para não acumular atraso
            duracao_audio = audio.size / self.sample_rate
            inicio_processamento = time.time()
            segments, _ = self.model.transcribe(
                audio, language=LANGUAGE, beam_size=1, vad_filter=True
            )
            texto = "".join(segment.text for segment in segments).strip()
            self._publicar(geracao, texto, time.time() - inicio_processamento, duracao_audio)

    def _ouvir_fala(self):
        """Junta o áudio da fala até 1 s de silêncio (pela energia do som) e transcreve tudo de uma vez."""
        fala, anterior, silencio = [], None, 0.0
        ruido = ENERGIA_MIN_VOZ / FATOR_VOZ
        geracao = self._geracao
        while self._running.is_set() and self.modo == self.CONVERSA:
            time.sleep(BLOCO_VAD_S)
            bloco, geracao_atual = self._pegar_audio()
            if geracao_atual != geracao:
                fala, anterior, silencio, geracao = [], None, 0.0, geracao_atual
            if bloco is None:
                continue
            energia = float(np.sqrt(np.mean(np.square(bloco))))
            falando = energia > max(ruido * FATOR_VOZ, ENERGIA_MIN_VOZ)
            if not fala:
                if falando:
                    # Inclui o bloco anterior para não cortar o começo da primeira palavra
                    fala = [anterior, bloco] if anterior is not None else [bloco]
                    silencio = 0.0
                else:
                    ruido = 0.95 * ruido + 0.05 * energia
                    anterior = bloco
                continue
            fala.append(bloco)
            silencio = 0.0 if falando else silencio + bloco.size / self.sample_rate
            duracao = sum(b.size for b in fala) / self.sample_rate
            if silencio >= SILENCIO_FIM_FALA_S or duracao >= MAX_FALA_S:
                if duracao - silencio >= FALA_MIN_S:
                    self._transcrever_fala(np.concatenate(fala))
                    return
                fala, silencio = [], 0.0

    def _transcrever_fala(self, audio):
        self.pausar()  # José não escuta enquanto pensa e responde
        geracao = self._geracao
        self.transcrevendo_fala.set()
        inicio_processamento = time.time()
        try:
            segments, _ = self.modelo_conversa.transcribe(
                audio, language=LANGUAGE, beam_size=5, vad_filter=True
            )
            texto = "".join(segment.text for segment in segments).strip()
        except Exception as e:
            print(f"⚠ Erro ao transcrever a fala: {e}")
            texto = ""
        # Limpa antes de publicar: o app não pode ver "transcrevendo" depois de já ter tratado o texto
        self.transcrevendo_fala.clear()
        self._publicar(geracao, texto, time.time() - inicio_processamento, audio.size / self.sample_rate, audio)


def duracao_audio_segundos(caminho: str) -> float:
    with av.open(caminho) as container:
        return container.duration / av.time_base if container.duration else 0.0


class PlayerDeHistorias:
    """Toca uma lista sorteada de histórias (mp3) com pygame."""

    def __init__(self, pasta: str):
        self.arquivos = sorted(glob.glob(os.path.join(pasta, "*.mp3")))
        self.playlist = []
        self.indice = -1
        self.duracao = 0.0
        self.tocando = False
        pygame.mixer.init()

    def nova_playlist(self) -> bool:
        self.playlist = random.sample(self.arquivos, len(self.arquivos))
        self.indice = -1
        return self.ir_para(0)

    def ir_para(self, indice: int) -> bool:
        if not 0 <= indice < len(self.playlist):
            self.parar()
            return False
        self.indice = indice
        caminho = self.playlist[indice]
        self.duracao = duracao_audio_segundos(caminho)
        pygame.mixer.music.load(caminho)
        pygame.mixer.music.play()
        self.tocando = True
        return True

    def proxima(self) -> bool:
        return self.ir_para(self.indice + 1)

    def anterior(self) -> bool:
        return self.ir_para(self.indice - 1)

    def parar(self):
        self.tocando = False
        pygame.mixer.music.stop()
        pygame.mixer.music.unload()

    def terminou(self) -> bool:
        return self.tocando and not pygame.mixer.music.get_busy()

    def progresso(self) -> float:
        if self.duracao <= 0:
            return 0.0
        return min(max(pygame.mixer.music.get_pos() / 1000 / self.duracao, 0.0), 1.0)

    def titulo(self) -> str:
        return os.path.splitext(os.path.basename(self.playlist[self.indice]))[0]


def audio_para_wav(audio: np.ndarray, sample_rate=SAMPLE_RATE) -> bytes:
    pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
    saida = io.BytesIO()
    with wave.open(saida, "wb") as arquivo:
        arquivo.setnchannels(1)
        arquivo.setsampwidth(2)
        arquivo.setframerate(sample_rate)
        arquivo.writeframes(pcm.tobytes())
    return saida.getvalue()


class RespostaJose(BaseModel):
    emocao: Literal["neutro", "feliz", "triste", "bravo", "assustado", "surpreso", "ansioso", "cansado"]
    resposta: str


class CerebroGemini:
    """Responde no modo conversa com o Gemini, que também ouve o áudio para perceber a emoção."""

    def __init__(self, modelo=GEMINI_MODELO):
        self.modelo = modelo
        self._cliente = None

    def responder(self, texto: str, audio: np.ndarray, historico: list) -> str:
        if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
            print("⚠ Defina GEMINI_API_KEY para o modo conversa (veja voz/README.md)")
            return "Ainda não tenho a chave do Gemini configurada."
        try:
            if self._cliente is None:
                self._cliente = genai.Client()
            conteudos = [
                types.Content(role=papel, parts=[types.Part.from_text(text=fala)]) for papel, fala in historico
            ]
            conteudos.append(types.Content(role="user", parts=[
                types.Part.from_bytes(data=audio_para_wav(audio), mime_type="audio/wav"),
                types.Part.from_text(text=f"Transcrição automática (pode ter erros): {texto}"),
            ]))
            resultado = self._cliente.models.generate_content(
                model=self.modelo,
                contents=conteudos,
                config=types.GenerateContentConfig(
                    system_instruction=PRE_PROMPT,
                    response_mime_type="application/json",
                    response_schema=RespostaJose,
                    thinking_config=types.ThinkingConfig(thinking_level="low"),
                ),
            )
            dados = resultado.parsed or RespostaJose.model_validate_json(resultado.text)
        except Exception as e:
            print(f"⚠ Erro no Gemini: {e}")
            return "Desculpe, não consegui pensar agora. Tente de novo."
        print(f"🙂 Emoção: {dados.emocao} | Resposta: {dados.resposta}")
        if dados.emocao != "neutro":
            return f"Notei que você parece um pouco {dados.emocao}. {dados.resposta}"
        return dados.resposta


class VozDoJose:
    """Fala as respostas com o edge-tts (voz neural da Microsoft, precisa de internet)."""

    def __init__(self, voz=VOZ_TTS):
        self.voz = voz
        self._arquivo = None

    def sintetizar(self, texto: str):
        fd, caminho = tempfile.mkstemp(prefix="jose_", suffix=".mp3")
        os.close(fd)
        try:
            asyncio.run(edge_tts.Communicate(texto, self.voz).save(caminho))
            return caminho
        except Exception as e:
            print(f"⚠ Não consegui gerar a voz (edge-tts): {e}")
            os.remove(caminho)
            return None

    def tocar(self, caminho: str):
        self._arquivo = caminho
        pygame.mixer.music.load(caminho)
        pygame.mixer.music.play()

    def terminou(self) -> bool:
        return not pygame.mixer.music.get_busy()

    def parar(self):
        if self._arquivo is None:
            return
        pygame.mixer.music.stop()
        pygame.mixer.music.unload()
        try:
            os.remove(self._arquivo)
        except OSError:
            pass
        self._arquivo = None


class AssistenteApp:
    """Máquina de estados do José. Não desenha nada: a página web lê estado() e mostra o rosto."""

    ACORDADO, TRANSICAO, OUVINDO, COMANDO, AGRADECIMENTO, HISTORIA = (
        "acordado", "transicao", "ouvindo", "comando", "agradecimento", "historia"
    )
    EXECUTANDO = "executando"  # backend movendo o robô; José não escuta até terminar
    CARREGANDO, CONVERSA, PENSANDO, RESPONDENDO = "carregando", "conversa", "pensando", "respondendo"

    def __init__(self, ouvinte: OuvinteDeAudio, backend=None):
        self.ouvinte = ouvinte
        self.backend = backend
        self.player = PlayerDeHistorias(PASTA_HISTORIAS)
        self.cerebro = CerebroGemini()
        self.voz = VozDoJose()
        self._lock = threading.Lock()  # o servidor web e as threads de conversa usam o estado
        self._live_words = []
        self.transcricao = ""
        self.velocidade = ""
        self.em_conversa = False
        self.historico = []
        self._comando_em_execucao = None
        self._confirmado = False
        self._mostrar_acordado()

    def _novo_estado(self, estado: str, comando: str = ""):
        self.state = estado
        self.comando = comando
        self.desde = time.monotonic()

    def _mostrar_acordado(self):
        self._novo_estado(self.ACORDADO)

    def _mostrar_comando(self, texto: str):
        self._novo_estado(self.COMANDO, texto)

    def _voltar_ao_menu(self):
        self._novo_estado(self.OUVINDO)
        self.ouvinte.retomar(OuvinteDeAudio.COMANDOS)

    def _iniciar_historias(self):
        if self.player.nova_playlist():
            self._novo_estado(self.HISTORIA)
        else:
            self._mostrar_acordado()

    def _trocar_historia(self, tocando: bool):
        if tocando:
            self._novo_estado(self.HISTORIA)
        else:
            self._mostrar_acordado()

    def parar(self):
        self.voz.parar()
        self.player.parar()

    def estado(self) -> dict:
        with self._lock:
            historia = self.state == self.HISTORIA
            return {
                "estado": self.state,
                "comando": self.comando,
                "titulo": self.player.titulo() if historia else "",
                "progresso": self.player.progresso() if historia else 0.0,
                "transcricao": self.transcricao,
                "velocidade": self.velocidade,
            }

    def passo(self):
        """Chamado em loop: lê o que foi transcrito e avança os estados que dependem de tempo."""
        with self._lock:
            if self.state == self.CONVERSA and self.ouvinte.transcrevendo_fala.is_set():
                self._novo_estado(self.PENSANDO)
            try:
                while True:
                    texto, duracao_processamento, duracao_audio, audio = self.ouvinte.text_queue.get_nowait()
                    self._atualizar_velocidade(duracao_processamento, duracao_audio)
                    self._processar_texto(texto, audio)
            except queue.Empty:
                pass

            decorrido = time.monotonic() - self.desde
            if self.state == self.TRANSICAO and decorrido >= DURACAO_MOVIMENTO_S:
                self._novo_estado(self.OUVINDO)
            elif self.state == self.AGRADECIMENTO and decorrido >= DURACAO_AGRADECIMENTO_S:
                self._mostrar_acordado()
            elif self.state == self.HISTORIA and self.player.terminou():
                self._trocar_historia(self.player.proxima())
            elif self.state == self.EXECUTANDO:
                self._acompanhar_execucao(decorrido)
            elif self.state == self.RESPONDENDO and decorrido > 0.3 and self.voz.terminou():
                self.voz.parar()
                self._ouvir_conversa()

    def _atualizar_transcricao_topo(self, texto: str):
        for palavra in texto.split():
            if len(self._live_words) >= 7:
                self._live_words = []
            self._live_words.append(palavra)
        self.transcricao = " ".join(self._live_words)

    def _atualizar_velocidade(self, duracao_processamento: float, duracao_audio: float):
        rtf = duracao_processamento / duracao_audio if duracao_audio > 0 else 0
        self.velocidade = (
            f"Processamento: {duracao_processamento:.2f}s | Áudio: {duracao_audio:.2f}s | RTF: {rtf:.2f}x"
        )

    # ---- Comandos do robô ----

    def _executar_comando(self, titulo: str, id_comando: str, texto: str):
        if self.backend and self.backend.conectado.is_set():
            self.backend.limpar_eventos()
            self.backend.enviar(id_comando, texto)
            self.ouvinte.pausar()
            self._comando_em_execucao = id_comando
            self._confirmado = False
            self._novo_estado(self.EXECUTANDO, titulo)
            return
        # Sem backend: igual a antes (mostra o comando e espera "obrigado")
        self._sair_da_conversa()
        self.ouvinte.retomar(OuvinteDeAudio.COMANDOS)
        self._mostrar_comando(titulo)

    def _acompanhar_execucao(self, decorrido: float):
        for evento in self.backend.eventos_pendentes():
            if evento.get("command") != self._comando_em_execucao:
                continue
            if evento["type"] == "voice_command_done":
                self._fim_da_execucao()
                return
            self._confirmado = True
            if not evento.get("running"):  # parar, no_robot, not_implemented...
                self._fim_da_execucao()
                return
        sem_confirmacao = not self._confirmado and decorrido > TEMPO_MAX_CONFIRMACAO_S
        if sem_confirmacao or decorrido > TEMPO_MAX_EXECUCAO_S:
            print("⚠ O backend não avisou o fim do comando; voltando a ouvir")
            self._fim_da_execucao()

    def _fim_da_execucao(self):
        self._comando_em_execucao = None
        if self.em_conversa:
            self._ouvir_conversa()
        else:
            self._voltar_ao_menu()

    # ---- Modo conversa ----

    def _iniciar_conversa(self):
        self.em_conversa = True
        self.historico = []
        self.ouvinte.pausar()
        if self.ouvinte.modelo_conversa is not None:
            self._ouvir_conversa()
            return
        self._novo_estado(self.CARREGANDO)
        threading.Thread(target=self._carregar_modelo_conversa, daemon=True).start()

    def _carregar_modelo_conversa(self):
        print(f"⏳ Carregando o modelo da conversa ({MODELO_CONVERSA})...")
        try:
            modelo = WhisperModel(MODELO_CONVERSA, device="cpu", compute_type="int8", cpu_threads=CPU_THREADS)
        except Exception as e:
            print(f"✗ Não consegui carregar o modelo da conversa: {e}")
            with self._lock:
                self._sair_da_conversa()
                self._voltar_ao_menu()
            return
        print("✓ Modelo da conversa carregado")
        with self._lock:
            self.ouvinte.modelo_conversa = modelo
            if self.state == self.CARREGANDO:
                self._ouvir_conversa()

    def _ouvir_conversa(self):
        self._novo_estado(self.CONVERSA)
        self.ouvinte.retomar(OuvinteDeAudio.CONVERSA)

    def _sair_da_conversa(self):
        self.em_conversa = False
        self.historico = []

    def _processar_fala_da_conversa(self, texto: str, audio):
        normalizado = normalizar(texto)
        if re.search(r"\bvoltar\b", normalizado):
            self._sair_da_conversa()
            self._voltar_ao_menu()
            return
        if re.search(r"\bhistori", normalizado):
            self._sair_da_conversa()
            self.ouvinte.retomar(OuvinteDeAudio.COMANDOS)
            self._iniciar_historias()
            return
        comando = identificar_comando(normalizado)
        if comando:
            self._executar_comando(*comando, texto)
            return
        self._novo_estado(self.PENSANDO)
        threading.Thread(target=self._responder, args=(texto, audio, list(self.historico)), daemon=True).start()

    def _responder(self, texto: str, audio, historico: list):
        resposta = self.cerebro.responder(texto, audio, historico)
        caminho = self.voz.sintetizar(resposta)
        with self._lock:
            if self.state != self.PENSANDO:
                if caminho:
                    os.remove(caminho)
                return
            self.historico = (historico + [("user", texto), ("model", resposta)])[-MAX_HISTORICO:]
            if caminho:
                self.voz.tocar(caminho)
                self._novo_estado(self.RESPONDENDO)
            else:
                self._ouvir_conversa()

    # ---- Texto reconhecido ----

    def _processar_texto(self, texto: str, audio=None):
        if texto:
            self._atualizar_transcricao_topo(texto)

        if self.state in (self.CONVERSA, self.PENSANDO):
            if texto:
                self._processar_fala_da_conversa(texto, audio)
            else:
                self._ouvir_conversa()
            return

        if not texto:
            return
        normalizado = normalizar(texto)

        if self.state == self.ACORDADO:
            if "jose" in normalizado:
                self._novo_estado(self.TRANSICAO)
            return

        if self.state == self.OUVINDO:
            if re.search(r"\bconversa", normalizado):
                self._iniciar_conversa()
                return
            if re.search(r"\bhistori", normalizado):
                self._iniciar_historias()
                return
            comando = identificar_comando(normalizado)
            if comando:
                self._executar_comando(*comando, texto)
            return

        if self.state == self.COMANDO:
            if re.search(r"\bobrigad[oa]\b", normalizado):
                self._novo_estado(self.AGRADECIMENTO)
            elif re.search(RE_PARAR, normalizado):
                # Parar tem que funcionar sem precisar chamar "José" de novo
                self._mostrar_comando("Parar")
                if self.backend:
                    self.backend.enviar("parar", texto)
            return

        if self.state == self.HISTORIA:
            if re.search(RE_PARAR, normalizado):
                self.player.parar()
                self._mostrar_acordado()
            elif re.search(r"\bproxima\b", normalizado):
                self._trocar_historia(self.player.proxima())
            elif re.search(r"\bvolta(r)?\b", normalizado):
                self._trocar_historia(self.player.anterior())
            return


def criar_servidor_web(app: AssistenteApp, host: str, porta: int) -> ThreadingHTTPServer:
    """Serve voz/web/ (a página), voz/rostojose/ (as imagens) e /estado (JSON lido pela página)."""

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=PASTA_WEB, **kwargs)

        def translate_path(self, path):
            if path.startswith("/rostojose/"):
                nome = os.path.basename(path.split("?", 1)[0])
                return os.path.join(PASTA_ROSTOS, nome)
            return super().translate_path(path)

        def do_GET(self):
            if self.path.split("?", 1)[0] == "/estado":
                corpo = json.dumps(app.estado()).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(corpo)))
                self.end_headers()
                self.wfile.write(corpo)
                return
            super().do_GET()

        def log_message(self, *args):
            pass  # a página consulta /estado várias vezes por segundo

    return ThreadingHTTPServer((host, porta), Handler)


def main():
    parser = argparse.ArgumentParser(description="Assistente de voz José do RAS")
    parser.add_argument("--backend", default=BACKEND_URL, help=f"WebSocket do backend (padrão: {BACKEND_URL})")
    parser.add_argument("--sem-robo", action="store_true", help="só mostra os comandos, não envia ao backend")
    parser.add_argument("--host", default="127.0.0.1", help="use 0.0.0.0 para abrir o rosto de outro aparelho")
    parser.add_argument("--porta", type=int, default=PORTA_WEB, help=f"porta da página do rosto (padrão: {PORTA_WEB})")
    parser.add_argument("--no-browser", action="store_true", help="não abre o navegador")
    args = parser.parse_args()

    backend = None if args.sem_robo else ConexaoBackend(args.backend)
    print(f"⏳ Carregando o modelo de fala ({MODEL_SIZE})...")
    model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8", cpu_threads=CPU_THREADS)
    ouvinte = OuvinteDeAudio(model)
    app = AssistenteApp(ouvinte, backend)

    servidor = criar_servidor_web(app, args.host, args.porta)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    url = f"http://localhost:{args.porta}"
    print(f"🙂 Rosto do José: {url}")
    if not args.no_browser:
        webbrowser.open(url)

    ouvinte.start()
    print("🎙️ José está ouvindo. Diga \"José\" para chamar.")
    if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
        print("⚠ GEMINI_API_KEY não definida: o modo conversa não vai conseguir responder")

    rodando = threading.Event()
    rodando.set()
    signal.signal(signal.SIGTERM, lambda *_: rodando.clear())
    try:
        while rodando.is_set():
            app.passo()
            time.sleep(INTERVALO_LOOP_S)
    except KeyboardInterrupt:
        pass
    finally:
        ouvinte.stop()
        app.parar()
        servidor.shutdown()
        print("👋 José encerrado")


if __name__ == "__main__":
    main()
