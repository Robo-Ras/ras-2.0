#!/usr/bin/env bash
# Sobe o backend (Python, WebSocket :8765) e o frontend (Vite, http://localhost:8080) juntos.
# Ctrl+C encerra os dois.
#
#   ./start.sh                 hardware real (C270 + D435 + LiDAR 2D)
#   ./start.sh --sim           sem o robô: robô, Arduino, câmera e LiDAR simulados
#   ./start.sh --lan           permite abrir pelo tablet: http://<ip-do-notebook>:8080/tablet
#   ./start.sh --no-browser    não abre o navegador
#   ./start.sh --voz           também sobe o assistente de voz José; rosto em http://localhost:8090
#   ./start.sh --controle      também sobe só o controle para o celular (porta 8100, na rede Wi-Fi)
#
# As outras opções vão direto para o backend, ex.:
#   ./start.sh --lidar ld06 --lidar-port /dev/ttyUSB1 --camera-device /dev/video2
#   (veja todas com: ./start.sh --help)
#
# Venv do Python: $RAS_VENV (padrão ~/L515)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${RAS_VENV:-$HOME/L515}"
PYTHON="$VENV/bin/python"
[ -x "$PYTHON" ] || PYTHON="$(command -v python3)"

OPEN_BROWSER=1
VOICE=0
CONTROLE=0
VOICE_ARGS=()
WEB_HOST=127.0.0.1
BACKEND_ARGS=()
for arg in "$@"; do
  case "$arg" in
    --no-browser) OPEN_BROWSER=0; VOICE_ARGS+=(--no-browser) ;;
    --voz) VOICE=1 ;;
    --controle) CONTROLE=1; BACKEND_ARGS+=(--host 0.0.0.0) ;;
    --lan) WEB_HOST=0.0.0.0; BACKEND_ARGS+=(--host 0.0.0.0); VOICE_ARGS+=(--host 0.0.0.0) ;;
    -h|--help)
      sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//'
      echo; echo "Opções do backend:"
      cd "$ROOT/backend" && exec "$PYTHON" robot_autonomous_control.py --help ;;
    *) BACKEND_ARGS+=("$arg") ;;
  esac
done

if [ ! -d "$ROOT/frontend/node_modules" ]; then
  echo "📦 Instalando dependências do frontend (só na primeira vez)..."
  (cd "$ROOT/frontend" && npm ci --no-audit --no-fund)
fi

PIDS=()
cleanup() {
  trap - INT TERM EXIT
  echo; echo "🛑 Encerrando..."
  for pid in "${PIDS[@]}"; do kill -TERM "$pid" 2>/dev/null || true; done
  wait 2>/dev/null || true
}
trap cleanup INT TERM EXIT

echo "🐍 Backend: $PYTHON robot_autonomous_control.py ${BACKEND_ARGS[*]:-}"
(cd "$ROOT/backend" && exec "$PYTHON" -u robot_autonomous_control.py "${BACKEND_ARGS[@]}") &
PIDS+=($!)

echo "🌐 Frontend: http://localhost:8080"
(cd "$ROOT/frontend" && exec ./node_modules/.bin/vite --host "$WEB_HOST" --port 8080 --strictPort) &
PIDS+=($!)

if [ "$VOICE" = 1 ]; then
  echo "🎙️ Assistente de voz: $PYTHON voz/jose.py ${VOICE_ARGS[*]:-} (rosto em http://localhost:8090)"
  (cd "$ROOT/voz" && exec "$PYTHON" -u jose.py "${VOICE_ARGS[@]}") &
  PIDS+=($!)
fi

if [ "$CONTROLE" = 1 ]; then
  # IP do notebook na rede (a interface da rota padrão; ignora docker0 etc.)
  LAN_IP="$(ip route get 1.1.1.1 2>/dev/null | sed -n 's/.* src \([0-9.]*\).*/\1/p' | head -1)"
  LAN_IP="${LAN_IP:-$(hostname -I | awk '{print $1}')}"
  echo "📱 Controle do celular: http://$LAN_IP:8100  (celular no mesmo Wi-Fi)"
  (cd "$ROOT/frontend" && RAS_CONTROLE_ONLY=1 VITE_CACHE_DIR="$ROOT/frontend/node_modules/.vite-controle" \
    exec ./node_modules/.bin/vite --host 0.0.0.0 --port 8100 --strictPort) &
  PIDS+=($!)
fi

if [ "$OPEN_BROWSER" = 1 ]; then
  (
    for _ in $(seq 1 60); do
      if curl -fs -o /dev/null http://127.0.0.1:8080; then
        xdg-open http://localhost:8080 >/dev/null 2>&1 || true
        exit 0
      fi
      sleep 0.5
    done
  ) &
fi

# Se o backend ou o frontend cair, derruba o resto (o José pode fechar sozinho)
wait -n "${PIDS[0]}" "${PIDS[1]}"
