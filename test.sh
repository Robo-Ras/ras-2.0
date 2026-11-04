#!/usr/bin/env bash
# Testes internos, sem precisar do robô:
#   backend  - drivers de LiDAR, Arduino simulado, navegação, servidor WebSocket, YOLO
#   voz      - dicionário de comandos, escuta pelo Vosk, estados do José, conversa
#   frontend - checagem de tipos e build
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${RAS_VENV:-$HOME/L515}"
PYTHON="$VENV/bin/python"
[ -x "$PYTHON" ] || PYTHON="$(command -v python3)"

echo "== Backend =="
(cd "$ROOT/backend" && "$PYTHON" -m unittest discover -s tests -v 2>&1 | grep -E " \.\.\. (ok|FAIL|ERROR|skipped)|^Ran |^OK|^FAILED|^(FAIL|ERROR):|Error|assert" ; exit "${PIPESTATUS[0]}")

echo; echo "== Voz (José) =="
(cd "$ROOT/voz" && "$PYTHON" -m unittest discover -s tests -v 2>&1 | grep -E " \.\.\. (ok|FAIL|ERROR|skipped)|^Ran |^OK|^FAILED|^(FAIL|ERROR):|Error|assert" ; exit "${PIPESTATUS[0]}")

echo; echo "== Frontend =="
cd "$ROOT/frontend"
[ -d node_modules ] || npm ci --no-audit --no-fund
./node_modules/.bin/tsc -p tsconfig.app.json --noEmit
# O Chrome tem que entender o dicionário de voz igual ao José (comandos_voz.json)
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
./node_modules/.bin/esbuild src/lib/voiceCommands.ts --bundle --format=esm --platform=node --outfile="$TMP/voice.mjs" --log-level=error
node tests/voiceCommands.test.mjs "$TMP/voice.mjs"
./node_modules/.bin/vite build --logLevel warn
echo "✓ Frontend compila"
