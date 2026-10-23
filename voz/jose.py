# pip install -r requirements.txt
import argparse
import glob
import json
import os
import queue
import random
import re
import signal
import threading
import time
import unicodedata
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import av
import numpy as np
import pygame
import sounddevice as sd
from faster_whisper import WhisperModel
from websockets.sync.client import connect as ws_connect

SAMPLE_RATE = 16000
CHUNK_SECONDS = 1.5
MAX_BUFFER_SECONDS = CHUNK_SECONDS * 3  # descarta áudio mais antigo se o processamento atrasar
MODEL_SIZE = "small"
LANGUAGE = "pt"
CPU_THREADS = os.cpu_count() or 4

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
    """Envia os comandos reconhecidos ao backend do robô pelo WebSocket, reconectando sozinha."""

    def __init__(self, url: str):
        self.url = url
        self._fila = queue.Queue()
        threading.Thread(target=self._loop, daemon=True).start()

    def enviar(self, comando: str, texto: str):
        self._fila.put({"type": "voice_command", "command": comando, "text": texto, "source": "jose"})

    def _loop(self):
        while True:
            try:
                with ws_connect(self.url, open_timeout=2, max_size=None) as ws:
                    print(f"✓ Conectado ao backend em {self.url}")
                    # O backend manda sensor_data o tempo todo; uma thread só descarta para não encher o buffer
                    threading.Thread(target=self._descartar_recebidas, args=(ws,), daemon=True).start()
                    while True:
                        ws.send(json.dumps(self._fila.get()))
            except Exception as e:
                print(f"⚠ Backend indisponível ({self.url}): {e}. Tentando de novo em {INTERVALO_RECONEXAO_S}s")
                # Comando antigo não deve mover o robô quando a conexão voltar
                while not self._fila.empty():
                    self._fila.get_nowait()
                time.sleep(INTERVALO_RECONEXAO_S)

    @staticmethod
    def _descartar_recebidas(ws):
        try:
            for _ in ws:
                pass
        except Exception:
            pass


class OuvinteDeAudio:
    """Grava o microfone continuamente e transcreve em blocos, publicando o texto numa fila."""

    def __init__(self, model, sample_rate=SAMPLE_RATE, chunk_seconds=CHUNK_SECONDS):
        self.model = model
        self.sample_rate = sample_rate
        self.chunk_seconds = chunk_seconds
        self.text_queue = queue.Queue()
        self._buffer = []
        self._lock = threading.Lock()
        self._running = threading.Event()
        self._stream = None
        self._worker = None

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            print(status)
        with self._lock:
            self._buffer.append(indata.copy())

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
            # Desconta o tempo gasto transcrevendo, senão cada bloco fica maior e mais lento que o anterior
            time.sleep(max(0.0, proxima_leitura - time.monotonic()))
            proxima_leitura = time.monotonic() + self.chunk_seconds
            with self._lock:
                if not self._buffer:
                    continue
                audio = np.concatenate(self._buffer, axis=0).flatten()
                self._buffer.clear()
            if audio.size == 0:
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
            duracao_processamento = time.time() - inicio_processamento
            self.text_queue.put((texto, duracao_processamento, duracao_audio))


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


class AssistenteApp:
    """Máquina de estados do José. Não desenha nada: a página web lê estado() e mostra o rosto."""

    ACORDADO, TRANSICAO, OUVINDO, COMANDO, AGRADECIMENTO, HISTORIA = (
        "acordado", "transicao", "ouvindo", "comando", "agradecimento", "historia"
    )

    def __init__(self, ouvinte: OuvinteDeAudio, backend=None):
        self.ouvinte = ouvinte
        self.backend = backend
        self.player = PlayerDeHistorias(PASTA_HISTORIAS)
        self._lock = threading.Lock()  # o servidor web lê o estado de outra thread
        self._live_words = []
        self.transcricao = ""
        self.velocidade = ""
        self._mostrar_acordado()

    def _novo_estado(self, estado: str, comando: str = ""):
        self.state = estado
        self.comando = comando
        self.desde = time.monotonic()

    def _mostrar_acordado(self):
        self._novo_estado(self.ACORDADO)

    def _mostrar_comando(self, texto: str):
        self._novo_estado(self.COMANDO, texto)

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
            try:
                while True:
                    texto, duracao_processamento, duracao_audio = self.ouvinte.text_queue.get_nowait()
                    self._atualizar_velocidade(duracao_processamento, duracao_audio)
                    if texto:
                        self._processar_texto(texto)
            except queue.Empty:
                pass

            decorrido = time.monotonic() - self.desde
            if self.state == self.TRANSICAO and decorrido >= DURACAO_MOVIMENTO_S:
                self._novo_estado(self.OUVINDO)
            elif self.state == self.AGRADECIMENTO and decorrido >= DURACAO_AGRADECIMENTO_S:
                self._mostrar_acordado()
            elif self.state == self.HISTORIA and self.player.terminou():
                self._trocar_historia(self.player.proxima())

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

    def _processar_texto(self, texto: str):
        self._atualizar_transcricao_topo(texto)
        normalizado = normalizar(texto)

        if self.state == self.ACORDADO:
            if "jose" in normalizado:
                self._novo_estado(self.TRANSICAO)
            return

        if self.state == self.OUVINDO:
            if re.search(r"\bhistori", normalizado):
                self._iniciar_historias()
                return
            comando = identificar_comando(normalizado)
            if comando:
                titulo, id_comando = comando
                self._mostrar_comando(titulo)
                if self.backend:
                    self.backend.enviar(id_comando, texto)
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
