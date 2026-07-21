#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${APP_DIR:-/home/pi/FencingWallRack}"
KIOSK_URL="${KIOSK_URL:-http://127.0.0.1:5000}"
KIOSK_DISPLAY_PROFILE="${KIOSK_DISPLAY_PROFILE:-ledwall}"
DISPLAY="${DISPLAY:-:0}"
XAUTHORITY="${XAUTHORITY:-/home/pi/.Xauthority}"
KIOSK_HOME="${KIOSK_HOME:-${XAUTHORITY%/.Xauthority}}"
CHROMIUM_PROFILE_DIR="${CHROMIUM_PROFILE_DIR:-${KIOSK_HOME}/.config/fencing-kiosk}"
STARTUP_TIMEOUT_SEC="${STARTUP_TIMEOUT_SEC:-90}"
CHROMIUM_START_DELAY_SEC="${CHROMIUM_START_DELAY_SEC:-8}"
KIOSK_WINDOW_MODE="${KIOSK_WINDOW_MODE:-dual}"
KIOSK_LEFT_PROFILE_DIR="${KIOSK_LEFT_PROFILE_DIR:-${KIOSK_HOME}/.config/chrome-profile-1}"
KIOSK_RIGHT_PROFILE_DIR="${KIOSK_RIGHT_PROFILE_DIR:-${KIOSK_HOME}/.config/chrome-profile-2}"
KIOSK_UNDERFLOOR_LEFT_A_PROFILE_DIR="${KIOSK_UNDERFLOOR_LEFT_A_PROFILE_DIR:-${KIOSK_HOME}/.config/chrome-underfloor-left-a}"
KIOSK_UNDERFLOOR_LEFT_B_PROFILE_DIR="${KIOSK_UNDERFLOOR_LEFT_B_PROFILE_DIR:-${KIOSK_HOME}/.config/chrome-underfloor-left-b}"
KIOSK_UNDERFLOOR_RIGHT_A_PROFILE_DIR="${KIOSK_UNDERFLOOR_RIGHT_A_PROFILE_DIR:-${KIOSK_HOME}/.config/chrome-underfloor-right-a}"
KIOSK_UNDERFLOOR_RIGHT_B_PROFILE_DIR="${KIOSK_UNDERFLOOR_RIGHT_B_PROFILE_DIR:-${KIOSK_HOME}/.config/chrome-underfloor-right-b}"

case "${KIOSK_DISPLAY_PROFILE}" in
  ledwall|LEDWALL)
    KIOSK_DISPLAY_PROFILE="ledwall"
    KIOSK_SCALE="${KIOSK_LEDWALL_SCALE:-${KIOSK_SCALE:-0.5}}"
    KIOSK_LEFT_URL="${KIOSK_LEDWALL_LEFT_URL:-${KIOSK_LEFT_URL:-${KIOSK_URL}}}"
    KIOSK_RIGHT_URL="${KIOSK_LEDWALL_RIGHT_URL:-${KIOSK_RIGHT_URL:-${KIOSK_URL%/}/rear}}"
    KIOSK_LEFT_GEOMETRY="${KIOSK_LEDWALL_LEFT_GEOMETRY:-${KIOSK_LEFT_GEOMETRY:-0,1,768,414}}"
    KIOSK_RIGHT_GEOMETRY="${KIOSK_LEDWALL_RIGHT_GEOMETRY:-${KIOSK_RIGHT_GEOMETRY:-0,514,768,414}}"
    ;;
  sottopedana|SOTTOPEDANA|underfloor|UNDERFLOOR)
    KIOSK_DISPLAY_PROFILE="sottopedana"
    KIOSK_SCALE="${KIOSK_UNDERFLOOR_SCALE:-1}"
    KIOSK_UNDERFLOOR_LEFT_A_URL="${KIOSK_UNDERFLOOR_LEFT_A_URL:-${KIOSK_URL%/}/underfloor-left-a}"
    KIOSK_UNDERFLOOR_LEFT_B_URL="${KIOSK_UNDERFLOOR_LEFT_B_URL:-${KIOSK_URL%/}/underfloor-left-b}"
    KIOSK_UNDERFLOOR_RIGHT_A_URL="${KIOSK_UNDERFLOOR_RIGHT_A_URL:-${KIOSK_URL%/}/underfloor-right-a}"
    KIOSK_UNDERFLOOR_RIGHT_B_URL="${KIOSK_UNDERFLOOR_RIGHT_B_URL:-${KIOSK_URL%/}/underfloor-right-b}"
    KIOSK_UNDERFLOOR_LEFT_A_GEOMETRY="${KIOSK_UNDERFLOOR_LEFT_A_GEOMETRY:-30,30,1344,96}"
    KIOSK_UNDERFLOOR_LEFT_B_GEOMETRY="${KIOSK_UNDERFLOOR_LEFT_B_GEOMETRY:-30,226,1344,96}"
    KIOSK_UNDERFLOOR_RIGHT_A_GEOMETRY="${KIOSK_UNDERFLOOR_RIGHT_A_GEOMETRY:-30,422,1344,96}"
    KIOSK_UNDERFLOOR_RIGHT_B_GEOMETRY="${KIOSK_UNDERFLOOR_RIGHT_B_GEOMETRY:-30,618,1344,96}"
    ;;
  *)
    echo "KIOSK_DISPLAY_PROFILE non valido: ${KIOSK_DISPLAY_PROFILE}" >&2
    exit 1
    ;;
esac

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
CHROME_LEFT_PID=""
CHROME_RIGHT_PID=""
CHROME_UNDERFLOOR_LEFT_A_PID=""
CHROME_UNDERFLOOR_LEFT_B_PID=""
CHROME_UNDERFLOOR_RIGHT_A_PID=""
CHROME_UNDERFLOOR_RIGHT_B_PID=""
LAST_CHROME_PID=""

cleanup() {
  set +e
  if [[ -n "${CHROME_UNDERFLOOR_LEFT_A_PID}" ]] && kill -0 "${CHROME_UNDERFLOOR_LEFT_A_PID}" 2>/dev/null; then
    kill "${CHROME_UNDERFLOOR_LEFT_A_PID}" 2>/dev/null
    wait "${CHROME_UNDERFLOOR_LEFT_A_PID}" 2>/dev/null
  fi
  if [[ -n "${CHROME_UNDERFLOOR_LEFT_B_PID}" ]] && kill -0 "${CHROME_UNDERFLOOR_LEFT_B_PID}" 2>/dev/null; then
    kill "${CHROME_UNDERFLOOR_LEFT_B_PID}" 2>/dev/null
    wait "${CHROME_UNDERFLOOR_LEFT_B_PID}" 2>/dev/null
  fi
  if [[ -n "${CHROME_UNDERFLOOR_RIGHT_A_PID}" ]] && kill -0 "${CHROME_UNDERFLOOR_RIGHT_A_PID}" 2>/dev/null; then
    kill "${CHROME_UNDERFLOOR_RIGHT_A_PID}" 2>/dev/null
    wait "${CHROME_UNDERFLOOR_RIGHT_A_PID}" 2>/dev/null
  fi
  if [[ -n "${CHROME_UNDERFLOOR_RIGHT_B_PID}" ]] && kill -0 "${CHROME_UNDERFLOOR_RIGHT_B_PID}" 2>/dev/null; then
    kill "${CHROME_UNDERFLOOR_RIGHT_B_PID}" 2>/dev/null
    wait "${CHROME_UNDERFLOOR_RIGHT_B_PID}" 2>/dev/null
  fi
  if [[ -n "${CHROME_LEFT_PID}" ]] && kill -0 "${CHROME_LEFT_PID}" 2>/dev/null; then
    kill "${CHROME_LEFT_PID}" 2>/dev/null
    wait "${CHROME_LEFT_PID}" 2>/dev/null
  fi
  if [[ -n "${CHROME_RIGHT_PID}" ]] && kill -0 "${CHROME_RIGHT_PID}" 2>/dev/null; then
    kill "${CHROME_RIGHT_PID}" 2>/dev/null
    wait "${CHROME_RIGHT_PID}" 2>/dev/null
  fi
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
  wait_for_http_url "${KIOSK_URL}"
}

wait_for_http_url() {
  local url="$1"
  local elapsed=0
  local step=2
  while ! curl -fsS --max-time 2 "${url}" >/dev/null 2>&1; do
    if ! kill -0 "${NODE_PID}" 2>/dev/null; then
      echo "Node terminato durante attesa HTTP" >&2
      return 1
    fi
    elapsed=$((elapsed + step))
    if (( elapsed >= STARTUP_TIMEOUT_SEC )); then
      echo "Timeout attesa endpoint ${url}" >&2
      return 1
    fi
    sleep "${step}"
  done
  return 0
}

geometry_part() {
  local geometry="$1"
  local index="$2"
  IFS=',' read -r x y w h <<<"${geometry}"
  case "${index}" in
    x) echo "${x}" ;;
    y) echo "${y}" ;;
    w) echo "${w}" ;;
    h) echo "${h}" ;;
  esac
}

wait_for_window_id() {
  local class_name="$1"
  local elapsed=0
  local step=1
  local window_id=""

  while [[ -z "${window_id}" ]]; do
    if command -v wmctrl >/dev/null 2>&1; then
      window_id="$(wmctrl -lx | awk -v cls="${class_name}" '$0 ~ cls {print $1}' | tail -n 1)"
    fi
    if [[ -n "${window_id}" ]]; then
      echo "${window_id}"
      return 0
    fi
    elapsed=$((elapsed + step))
    if (( elapsed >= 20 )); then
      return 1
    fi
    sleep "${step}"
  done
}

configure_window() {
  local class_name="$1"
  local geometry="$2"
  local window_id=""
  local attempt=0

  if ! command -v wmctrl >/dev/null 2>&1; then
    echo "wmctrl non trovato: salto posizionamento finestra ${class_name}" >&2
    return 0
  fi

  window_id="$(wait_for_window_id "${class_name}" || true)"
  if [[ -z "${window_id}" ]]; then
    echo "Finestra ${class_name} non trovata da wmctrl" >&2
    return 0
  fi

  while (( attempt < 10 )); do
    wmctrl -x -r "${class_name}" -b remove,maximized_vert,maximized_horz || true

    if command -v xprop >/dev/null 2>&1; then
      xprop -id "${window_id}" -f _MOTIF_WM_HINTS 32c \
        -set _MOTIF_WM_HINTS "0x2, 0x0, 0x0, 0x0, 0x0" || true
    elif (( attempt == 0 )); then
      echo "xprop non trovato: salto rimozione bordi finestra ${class_name}" >&2
    fi

    wmctrl -x -r "${class_name}" -e "0,${geometry}" || true
    attempt=$((attempt + 1))
    sleep 0.5
  done
}

launch_chromium_app_window() {
  local url="$1"
  local profile_dir="$2"
  local class_name="$3"
  local geometry="$4"
  local use_bwsi="${5:-0}"
  local x y w h

  x="$(geometry_part "${geometry}" x)"
  y="$(geometry_part "${geometry}" y)"
  w="$(geometry_part "${geometry}" w)"
  h="$(geometry_part "${geometry}" h)"

  mkdir -p "${profile_dir}"
  pkill -f "${CHROMIUM_BIN}.*${profile_dir}" >/dev/null 2>&1 || true

  echo "Avvio ${class_name}: url=${url} geometry=${geometry} profile=${profile_dir}"

  local args=(
    --disable-gpu
    --disable-software-rasterizer
    --autoplay-policy=no-user-gesture-required
    --disable-infobars
    --disable-session-crashed-bubble
    --noerrdialogs
    --no-first-run
    --ozone-platform=x11
    "--app=${url}"
    "--user-data-dir=${profile_dir}"
    "--class=${class_name}"
    "--name=${class_name}"
    "--window-size=${w},${h}"
    "--window-position=${x},${y}"
    "--force-device-scale-factor=${KIOSK_SCALE}"
    --new-window
    --disable-features=OverlayScrollbar
  )
  if [[ "${use_bwsi}" == "1" ]]; then
    args+=(--bwsi)
  fi

  "${CHROMIUM_BIN}" "${args[@]}" &
  LAST_CHROME_PID=$!
  sleep 0.4
  if ! kill -0 "${LAST_CHROME_PID}" 2>/dev/null; then
    echo "Chromium ${class_name} terminato subito dopo l'avvio" >&2
    return 1
  fi
}

launch_dual_windows() {
  local left_x left_y left_w left_h right_x right_y right_w right_h
  left_x="$(geometry_part "${KIOSK_LEFT_GEOMETRY}" x)"
  left_y="$(geometry_part "${KIOSK_LEFT_GEOMETRY}" y)"
  left_w="$(geometry_part "${KIOSK_LEFT_GEOMETRY}" w)"
  left_h="$(geometry_part "${KIOSK_LEFT_GEOMETRY}" h)"
  right_x="$(geometry_part "${KIOSK_RIGHT_GEOMETRY}" x)"
  right_y="$(geometry_part "${KIOSK_RIGHT_GEOMETRY}" y)"
  right_w="$(geometry_part "${KIOSK_RIGHT_GEOMETRY}" w)"
  right_h="$(geometry_part "${KIOSK_RIGHT_GEOMETRY}" h)"

  mkdir -p "${KIOSK_LEFT_PROFILE_DIR}" "${KIOSK_RIGHT_PROFILE_DIR}"
  pkill -f "${CHROMIUM_BIN}.*${KIOSK_LEFT_PROFILE_DIR}" >/dev/null 2>&1 || true
  pkill -f "${CHROMIUM_BIN}.*${KIOSK_RIGHT_PROFILE_DIR}" >/dev/null 2>&1 || true

  "${CHROMIUM_BIN}" \
    --disable-gpu \
    --disable-software-rasterizer \
    --autoplay-policy=no-user-gesture-required \
    --disable-infobars \
    --disable-session-crashed-bubble \
    --noerrdialogs \
    --no-first-run \
    --ozone-platform=x11 \
    --app="${KIOSK_LEFT_URL}" \
    --user-data-dir="${KIOSK_LEFT_PROFILE_DIR}" \
    --class="kiosk_sinistro" \
    --name="kiosk_sinistro" \
    --window-size="${left_w},${left_h}" \
    --window-position="${left_x},${left_y}" \
    --force-device-scale-factor="${KIOSK_SCALE}" \
    --new-window \
    --disable-features=OverlayScrollbar &
  CHROME_LEFT_PID=$!

  "${CHROMIUM_BIN}" \
    --disable-gpu \
    --disable-software-rasterizer \
    --autoplay-policy=no-user-gesture-required \
    --disable-infobars \
    --disable-session-crashed-bubble \
    --noerrdialogs \
    --no-first-run \
    --ozone-platform=x11 \
    --app="${KIOSK_RIGHT_URL}" \
    --user-data-dir="${KIOSK_RIGHT_PROFILE_DIR}" \
    --class="kiosk_destro" \
    --name="kiosk_destro" \
    --window-size="${right_w},${right_h}" \
    --window-position="${right_x},${right_y}" \
    --force-device-scale-factor="${KIOSK_SCALE}" \
    --new-window \
    --bwsi \
    --disable-features=OverlayScrollbar &
  CHROME_RIGHT_PID=$!

  configure_window "kiosk_sinistro" "${KIOSK_LEFT_GEOMETRY}" &
  configure_window "kiosk_destro" "${KIOSK_RIGHT_GEOMETRY}" &

  echo "Chromium sinistro avviato PID=${CHROME_LEFT_PID}"
  echo "Chromium destro avviato PID=${CHROME_RIGHT_PID}"
}

launch_underfloor_windows() {
  echo "Profilo sottopedana: 4 finestre 1344x96"
  wait_for_http_url "${KIOSK_UNDERFLOOR_LEFT_A_URL}"
  wait_for_http_url "${KIOSK_UNDERFLOOR_LEFT_B_URL}"
  wait_for_http_url "${KIOSK_UNDERFLOOR_RIGHT_A_URL}"
  wait_for_http_url "${KIOSK_UNDERFLOOR_RIGHT_B_URL}"

  launch_chromium_app_window "${KIOSK_UNDERFLOOR_LEFT_A_URL}" "${KIOSK_UNDERFLOOR_LEFT_A_PROFILE_DIR}" "kiosk_sottopedana_sx_a" "${KIOSK_UNDERFLOOR_LEFT_A_GEOMETRY}"
  CHROME_UNDERFLOOR_LEFT_A_PID="${LAST_CHROME_PID}"
  launch_chromium_app_window "${KIOSK_UNDERFLOOR_LEFT_B_URL}" "${KIOSK_UNDERFLOOR_LEFT_B_PROFILE_DIR}" "kiosk_sottopedana_sx_b" "${KIOSK_UNDERFLOOR_LEFT_B_GEOMETRY}" "1"
  CHROME_UNDERFLOOR_LEFT_B_PID="${LAST_CHROME_PID}"
  launch_chromium_app_window "${KIOSK_UNDERFLOOR_RIGHT_A_URL}" "${KIOSK_UNDERFLOOR_RIGHT_A_PROFILE_DIR}" "kiosk_sottopedana_dx_a" "${KIOSK_UNDERFLOOR_RIGHT_A_GEOMETRY}"
  CHROME_UNDERFLOOR_RIGHT_A_PID="${LAST_CHROME_PID}"
  launch_chromium_app_window "${KIOSK_UNDERFLOOR_RIGHT_B_URL}" "${KIOSK_UNDERFLOOR_RIGHT_B_PROFILE_DIR}" "kiosk_sottopedana_dx_b" "${KIOSK_UNDERFLOOR_RIGHT_B_GEOMETRY}" "1"
  CHROME_UNDERFLOOR_RIGHT_B_PID="${LAST_CHROME_PID}"

  configure_window "kiosk_sottopedana_sx_a" "${KIOSK_UNDERFLOOR_LEFT_A_GEOMETRY}" &
  configure_window "kiosk_sottopedana_sx_b" "${KIOSK_UNDERFLOOR_LEFT_B_GEOMETRY}" &
  configure_window "kiosk_sottopedana_dx_a" "${KIOSK_UNDERFLOOR_RIGHT_A_GEOMETRY}" &
  configure_window "kiosk_sottopedana_dx_b" "${KIOSK_UNDERFLOOR_RIGHT_B_GEOMETRY}" &

  echo "Chromium sottopedana SX A avviato PID=${CHROME_UNDERFLOOR_LEFT_A_PID}"
  echo "Chromium sottopedana SX B avviato PID=${CHROME_UNDERFLOOR_LEFT_B_PID}"
  echo "Chromium sottopedana DX A avviato PID=${CHROME_UNDERFLOOR_RIGHT_A_PID}"
  echo "Chromium sottopedana DX B avviato PID=${CHROME_UNDERFLOOR_RIGHT_B_PID}"
}

launch_single_window() {
  mkdir -p "${CHROMIUM_PROFILE_DIR}"
  # Prevent stale instances from stacking black overlay windows.
  pkill -f "${CHROMIUM_BIN}.*${CHROMIUM_PROFILE_DIR}" >/dev/null 2>&1 || true
  "${CHROMIUM_BIN}" \
    --kiosk \
    --incognito \
    --ozone-platform=x11 \
    --disable-gpu \
    --autoplay-policy=no-user-gesture-required \
    --disable-infobars \
    --disable-session-crashed-bubble \
    --noerrdialogs \
    --no-first-run \
    --user-data-dir="${CHROMIUM_PROFILE_DIR}" \
    "${KIOSK_URL}" &
  CHROME_PID=$!
  echo "Chromium avviato PID=${CHROME_PID}"
}

cd "${APP_DIR}"
npm start &
NODE_PID=$!
echo "Node avviato PID=${NODE_PID}"

wait_for_x_display
wait_for_http
sleep "${CHROMIUM_START_DELAY_SEC}"

if [[ "${KIOSK_DISPLAY_PROFILE}" == "sottopedana" ]]; then
  launch_underfloor_windows
elif [[ "${KIOSK_WINDOW_MODE}" == "dual" ]]; then
  launch_dual_windows
else
  launch_single_window
fi

set +e
if [[ "${KIOSK_DISPLAY_PROFILE}" == "sottopedana" ]]; then
  wait -n "${NODE_PID}" "${CHROME_UNDERFLOOR_LEFT_A_PID}" "${CHROME_UNDERFLOOR_LEFT_B_PID}" "${CHROME_UNDERFLOOR_RIGHT_A_PID}" "${CHROME_UNDERFLOOR_RIGHT_B_PID}"
elif [[ "${KIOSK_WINDOW_MODE}" == "dual" ]]; then
  wait -n "${NODE_PID}" "${CHROME_LEFT_PID}" "${CHROME_RIGHT_PID}"
else
  wait -n "${NODE_PID}" "${CHROME_PID}"
fi
EXIT_CODE=$?
set -e

if ! kill -0 "${NODE_PID}" 2>/dev/null; then
  echo "Node terminato, richiesto restart service" >&2
fi

if [[ "${KIOSK_DISPLAY_PROFILE}" != "sottopedana" ]] && [[ "${KIOSK_WINDOW_MODE}" == "single" ]] && ! kill -0 "${CHROME_PID}" 2>/dev/null; then
  echo "Chromium terminato, richiesto restart service" >&2
fi

if [[ "${KIOSK_DISPLAY_PROFILE}" != "sottopedana" ]] && [[ "${KIOSK_WINDOW_MODE}" == "dual" ]] && ! kill -0 "${CHROME_LEFT_PID}" 2>/dev/null; then
  echo "Chromium sinistro terminato, richiesto restart service" >&2
fi

if [[ "${KIOSK_DISPLAY_PROFILE}" != "sottopedana" ]] && [[ "${KIOSK_WINDOW_MODE}" == "dual" ]] && ! kill -0 "${CHROME_RIGHT_PID}" 2>/dev/null; then
  echo "Chromium destro terminato, richiesto restart service" >&2
fi

if [[ "${KIOSK_DISPLAY_PROFILE}" == "sottopedana" ]] && ! kill -0 "${CHROME_UNDERFLOOR_LEFT_A_PID}" 2>/dev/null; then
  echo "Chromium sottopedana SX A terminato, richiesto restart service" >&2
fi

if [[ "${KIOSK_DISPLAY_PROFILE}" == "sottopedana" ]] && ! kill -0 "${CHROME_UNDERFLOOR_LEFT_B_PID}" 2>/dev/null; then
  echo "Chromium sottopedana SX B terminato, richiesto restart service" >&2
fi

if [[ "${KIOSK_DISPLAY_PROFILE}" == "sottopedana" ]] && ! kill -0 "${CHROME_UNDERFLOOR_RIGHT_A_PID}" 2>/dev/null; then
  echo "Chromium sottopedana DX A terminato, richiesto restart service" >&2
fi

if [[ "${KIOSK_DISPLAY_PROFILE}" == "sottopedana" ]] && ! kill -0 "${CHROME_UNDERFLOOR_RIGHT_B_PID}" 2>/dev/null; then
  echo "Chromium sottopedana DX B terminato, richiesto restart service" >&2
fi

exit "${EXIT_CODE}"
