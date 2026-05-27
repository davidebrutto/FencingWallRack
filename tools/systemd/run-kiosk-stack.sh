#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${APP_DIR:-/home/pi/FencingWallRack}"
KIOSK_URL="${KIOSK_URL:-http://127.0.0.1:5000}"
DISPLAY="${DISPLAY:-:0}"
XAUTHORITY="${XAUTHORITY:-/home/pi/.Xauthority}"
CHROMIUM_PROFILE_DIR="${CHROMIUM_PROFILE_DIR:-/home/pi/.config/fencing-kiosk}"
STARTUP_TIMEOUT_SEC="${STARTUP_TIMEOUT_SEC:-90}"

export DISPLAY
export XAUTHORITY

if command -v chromium-browser >/dev/null 2>&1; then
  CHROMIUM_BIN="chromium-browser"
elif command -v chromium >/dev/null 2>&1; then
  CHROMIUM_BIN="chromium"
else
  echo "Chromium non trovato (cercati: chromium-browser, chromium)" >&2
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "npm non trovato nel PATH" >&2
  exit 1
fi

NODE_PID=""
CHROME_PID=""

cleanup() {
  set +e
  if [[ -n "${CHROME_PID}" ]] && kill -0 "${CHROME_PID}" 2>/dev/null; then
    kill "${CHROME_PID}" 2>/dev/null
    wait "${CHROME_PID}" 2>/dev/null
  fi
  if [[ -n "${NODE_PID}" ]] && kill -0 "${NODE_PID}" 2>/dev/null; then
    kill "${NODE_PID}" 2>/dev/null
    wait "${NODE_PID}" 2>/dev/null
  fi
}
trap cleanup EXIT INT TERM

wait_for_x_display() {
  local elapsed=0
  local step=2
  local x_sock="/tmp/.X11-unix/X${DISPLAY#:}"
  while [[ ! -S "${x_sock}" ]]; do
    elapsed=$((elapsed + step))
    if (( elapsed >= STARTUP_TIMEOUT_SEC )); then
      echo "Timeout attesa display X (${DISPLAY})" >&2
      return 1
    fi
    sleep "${step}"
  done
  return 0
}

wait_for_http() {
  local elapsed=0
  local step=2
  while ! curl -fsS --max-time 2 "${KIOSK_URL}" >/dev/null 2>&1; do
    if ! kill -0 "${NODE_PID}" 2>/dev/null; then
      echo "Node terminato durante attesa HTTP" >&2
      return 1
    fi
    elapsed=$((elapsed + step))
    if (( elapsed >= STARTUP_TIMEOUT_SEC )); then
      echo "Timeout attesa endpoint ${KIOSK_URL}" >&2
      return 1
    fi
    sleep "${step}"
  done
  return 0
}

cd "${APP_DIR}"
npm start &
NODE_PID=$!
echo "Node avviato PID=${NODE_PID}"

wait_for_x_display
wait_for_http

mkdir -p "${CHROMIUM_PROFILE_DIR}"
"${CHROMIUM_BIN}" \
  --kiosk \
  --incognito \
  --autoplay-policy=no-user-gesture-required \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --noerrdialogs \
  --no-first-run \
  --user-data-dir="${CHROMIUM_PROFILE_DIR}" \
  "${KIOSK_URL}" &
CHROME_PID=$!
echo "Chromium avviato PID=${CHROME_PID}"

set +e
wait -n "${NODE_PID}" "${CHROME_PID}"
EXIT_CODE=$?
set -e

if ! kill -0 "${NODE_PID}" 2>/dev/null; then
  echo "Node terminato, richiesto restart service" >&2
fi

if ! kill -0 "${CHROME_PID}" 2>/dev/null; then
  echo "Chromium terminato, richiesto restart service" >&2
fi

exit "${EXIT_CODE}"
