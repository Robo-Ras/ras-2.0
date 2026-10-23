# RAS 2.0 - Robô Autônomo de Serviços

Sistema de controle e navegação autônoma para robô omnidirecional de 3 rodas.
Frontend (React/Vite) e backend (Python) rodam juntos no notebook, sem depender do Lovable.

🚀 Passo a passo para ligar o robô: [COMO_RODAR.md](COMO_RODAR.md)

📖 Documentação completa (arquitetura, sensores, navegação, protocolo, testes): [DOCUMENTACAO.md](DOCUMENTACAO.md)

![RAS-Imagem](https://github.com/user-attachments/assets/fb7c15bb-2333-40f6-87b7-962a2bd71497)

## Hardware

- Robô omnidirecional com 3 motores DC + Arduino (`arduino/arduino_robot_control.ino`)
- **Logitech C270**: câmera RGB frontal (YOLO)
- **LiDAR 2D**: LDROBOT LD06/LD19 ou Slamtec RPLIDAR A1/A2/C1 (obstáculos ao redor)
- **Intel RealSense D435**: câmera de cor + profundidade (obstáculos na altura e distância dos objetos)
- Tablet (opcional) para a "carinha" de status em `/tablet`

## ▶️ Rodando

```bash
cd ~/ras-2.0
./start.sh            # robô real
./start.sh --sim      # sem o robô: robô, Arduino, câmera e LiDAR simulados
```

Abre sozinho em **http://localhost:8080**. `Ctrl+C` encerra tudo (os motores param antes de sair).

Na primeira vez o script instala as dependências do frontend (`npm ci`). O Python usa o venv
`~/L515` (troque com `RAS_VENV=/outro/venv ./start.sh`).

### Opções úteis

| Opção | Para quê |
|-------|----------|
| `--sim` | Testar tudo sem hardware. A porta `SIM` (Arduino simulado) já vem conectada |
| `--lan` | Acessar de outro aparelho: `http://<ip-do-notebook>:8080/tablet` |
| `--lidar ld06 --lidar-port /dev/ttyUSB1` | Escolher o LiDAR (padrão: detecta sozinho) |
| `--lidar-offset 180` / `--lidar-flip` | Alinhar o 0° do LiDAR com a frente do robô |
| `--camera-device /dev/video2` | Escolher a webcam (padrão: procura a C270) |
| `--realsense off` | Ignorar a D435 |
| `--no-browser` | Não abrir o navegador |
| `--voz` | Assistente de voz José; rosto em http://localhost:8090 ([voz/README.md](voz/README.md)) |

Todas: `./start.sh --help`.

### Na simulação

A câmera simulada mostra a visão do robô e um mini-mapa (canto superior direito) com a sala,
o rastro do robô e os pontos do LiDAR. Dá para dirigir pelos botões/WASD, ligar o modo
autônomo e o YOLO normalmente.

## 🧪 Testes (sem o robô)

```bash
./test.sh
```

- Drivers do LD06 e RPLIDAR com pacotes montados byte a byte (CRC, sincronismo, ângulos)
- Arduino simulado interpretando os comandos igual ao `.ino`
- Navegação autônoma rodando 3 × 3 minutos na sala simulada, sem colisões
- Servidor WebSocket: as mesmas mensagens que o frontend manda (mover, autônomo, serial, tablet)
- YOLO + LiDAR: pessoas detectadas recebem a distância lida pelo LiDAR
- Frontend: checagem de tipos e build

## Arquivos

| Arquivo | Função |
|---------|--------|
| `start.sh` | Sobe backend + frontend juntos |
| `test.sh` | Testes internos |
| `backend/robot_autonomous_control.py` | Servidor WebSocket (8765), obstáculos, navegação, Arduino |
| `backend/sensors.py` | C270 (OpenCV), D435 (librealsense), LiDAR LD06 e RPLIDAR |
| `backend/simulator.py` | Mundo simulado, Arduino virtual, LiDAR e câmera sintéticos |
| `backend/robot_tracking_system.py` | YOLO + filtro de Kalman; distância pela D435 ou pelo LiDAR |
| `frontend/src/pages/Index.tsx` | Painel principal |
| `frontend/src/pages/TabletStatus.tsx` | Tela do tablet |
| `frontend/src/components/Lidar2DView.tsx` | Mapa de pontos do LiDAR 2D |
| `frontend/src/lib/ws.ts` | Endereço do backend (mesmo host da página, ou `VITE_WS_URL`) |

### D435 e librealsense

Se existir a build local da librealsense em `~/librealsense/build/wrappers/python` (troque com
`RAS_REALSENSE_DIR`), o backend usa ela; senão, usa o `pyrealsense2` do pip. A D435 funciona com as duas.
Ligue a D435 numa porta USB 3 (azul): em USB 2 ela pode não abrir os fluxos de cor e profundidade.

## Navegação autônoma

A cada 100 ms o backend junta os obstáculos de todos os sensores (LiDAR 2D, D435, YOLO):

1. Se há algo no **corredor à frente** (largura do robô + margem) a menos de 0,8 m, gira para o
   lado com mais espaço e continua girando até o caminho abrir
2. Senão anda para frente; a cada ~1,5 s gira um pouco para observar ao redor

Parâmetros em `AutonomousNavigator` e `ObstacleDetector` (`backend/robot_autonomous_control.py`).

## Instalação em outra máquina

```bash
cd frontend && npm ci
pip install -r backend/requirements.txt
```

## ❗ Solução de Problemas

| Problema | Solução |
|----------|---------|
| Porta serial não aparece | Verifique o cabo e permissões: `sudo usermod -aG dialout $USER` (relogar) |
| LiDAR não detectado | Passe `--lidar ld06 --lidar-port /dev/ttyUSBx` (ou `rplidar`) |
| Pontos do LiDAR girados/espelhados | Ajuste `--lidar-offset` / `--lidar-flip` olhando o radar na interface |
| Webcam errada | `v4l2-ctl --list-devices` e depois `--camera-device /dev/videoN` |
| Tablet não conecta | Use `./start.sh --lan` e abra `http://<ip-do-notebook>:8080/tablet` |
