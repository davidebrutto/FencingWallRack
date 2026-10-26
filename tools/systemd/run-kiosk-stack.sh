#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${APP_DIR:-/home/pi/FencingWallRack}"
KIOSK_URL="${KIOSK_URL:-http://127.0.0.1:5000}"
KIOSK_DISPLAY_PROFILE="${KIOSK_DISPLAY_PROFILE:-ledwall}"
DISPLAY="${DISPLAY:-:0}"
XAUTHORITY="${XAUTHORITY:-/home/pi/.Xauthority}"
KIOSK_HOME="${KIOSK_HOME:-${XAUTHORITY%/.Xauthority}}"
KIOSK_SET_WALLPAPER="${KIOSK_SET_WALLPAPER:-1}"
KIOSK_WALLPAPER_MODE="${KIOSK_WALLPAPER_MODE:-fit}"
KIOSK_WALLPAPER_BACKEND="${KIOSK_WALLPAPER_BACKEND:-auto}"
KIOSK_PCMANFM_PROFILE="${KIOSK_PCMANFM_PROFILE:-LXDE-pi}"
KIOSK_MIRROR_DISPLAYS="${KIOSK_MIRROR_DISPLAYS:-1}"
KIOSK_MIRROR_PRIMARY_OUTPUT="${KIOSK_MIRROR_PRIMARY_OUTPUT:-}"
KIOSK_MIRROR_SECONDARY_OUTPUT="${KIOSK_MIRROR_SECONDARY_OUTPUT:-}"
KIOSK_MIRROR_MODE="${KIOSK_MIRROR_MODE:-}"
KIOSK_DISABLE_POWER_SAVE="${KIOSK_DISABLE_POWER_SAVE:-1}"
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
KIOSK_MONITOR_1_PROFILE_DIR="${KIOSK_MONITOR_1_PROFILE_DIR:-${KIOSK_HOME}/.config/chrome-monitor-1}"
KIOSK_MONITOR_2_PROFILE_DIR="${KIOSK_MONITOR_2_PROFILE_DIR:-${KIOSK_HOME}/.config/chrome-monitor-2}"
KIOSK_MONITOR_URL="${KIOSK_MONITOR_URL:-${KIOSK_URL%/}/monitor}"
KIOSK_MONITOR_PRIMARY_OUTPUT="${KIOSK_MONITOR_PRIMARY_OUTPUT:-}"
KIOSK_MONITOR_SECONDARY_OUTPUT="${KIOSK_MONITOR_SECONDARY_OUTPUT:-}"
KIOSK_MONITOR_HIDE_CURSOR="${KIOSK_MONITOR_HIDE_CURSOR:-1}"
MONITOR_PRIMARY_GEOMETRY=""
MONITOR_SECONDARY_GEOMETRY=""

case "${KIOSK_DISPLAY_PROFILE}" in
  ledwall|LEDWALL)
    KIOSK_DISPLAY_PROFILE="ledwall"
    KIOSK_SCALE="${KIOSK_LEDWALL_SCALE:-${KIOSK_SCALE:-0.5}}"
    KIOSK_LEFT_URL="${KIOSK_LEDWALL_LEFT_URL:-${KIOSK_LEFT_URL:-${KIOSK_URL}}}"
    KIOSK_RIGHT_URL="${KIOSK_LEDWALL_RIGHT_URL:-${KIOSK_RIGHT_URL:-${KIOSK_URL%/}/rear}}"
    KIOSK_LEFT_GEOMETRY="${KIOSK_LEDWALL_LEFT_GEOMETRY:-${KIOSK_LEFT_GEOMETRY:-0,1,768,414}}"
    KIOSK_RIGHT_GEOMETRY="${KIOSK_LEDWALL_RIGHT_GEOMETRY:-${KIOSK_RIGHT_GEOMETRY:-0,514,768,414}}"
    KIOSK_WALLPAPER="${KIOSK_LEDWALL_WALLPAPER:-${KIOSK_WALLPAPER:-}}"
    ;;
  sottopedana|SOTTOPEDANA|underfloor|UNDERFLOOR)
    KIOSK_DISPLAY_PROFILE="sottopedana"
    KIOSK_SCALE="${KIOSK_UNDERFLOOR_SCALE:-1}"
    KIOSK_UNDERFLOOR_LEFT_A_URL="${KIOSK_UNDERFLOOR_LEFT_A_URL:-${KIOSK_URL%/}/underfloor-left-a}"
    KIOSK_UNDERFLOOR_LEFT_B_URL="${KIOSK_UNDERFLOOR_LEFT_B_URL:-${KIOSK_URL%/}/underfloor-left-b}"
    KIOSK_UNDERFLOOR_RIGHT_A_URL="${KIOSK_UNDERFLOOR_RIGHT_A_URL:-${KIOSK_URL%/}/underfloor-right-a}"
    KIOSK_UNDERFLOOR_RIGHT_B_URL="${KIOSK_UNDERFLOOR_RIGHT_B_URL:-${KIOSK_URL%/}/underfloor-right-b}"
    KIOSK_UNDERFLOOR_LEFT_A_GEOMETRY="${KIOSK_UNDERFLOOR_LEFT_A_GEOMETRY:-30,30,1152,96}"
    KIOSK_UNDERFLOOR_LEFT_B_GEOMETRY="${KIOSK_UNDERFLOOR_LEFT_B_GEOMETRY:-30,226,1536,96}"
    KIOSK_UNDERFLOOR_RIGHT_A_GEOMETRY="${KIOSK_UNDERFLOOR_RIGHT_A_GEOMETRY:-30,422,1536,96}"
    KIOSK_UNDERFLOOR_RIGHT_B_GEOMETRY="${KIOSK_UNDERFLOOR_RIGHT_B_GEOMETRY:-30,618,1152,96}"
    KIOSK_WALLPAPER="${KIOSK_UNDERFLOOR_WALLPAPER:-${KIOSK_WALLPAPER:-}}"
    ;;
  monitor|MONITOR)
    KIOSK_DISPLAY_PROFILE="monitor"
    KIOSK_SCALE=1
    KIOSK_WALLPAPER="${KIOSK_MONITOR_WALLPAPER:-${KIOSK_LEDWALL_WALLPAPER:-${KIOSK_WALLPAPER:-}}}"
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
CHROME_MONITOR_1_PID=""
CHROME_MONITOR_2_PID=""
HIDE_CURSOR_PID=""
LAST_CHROME_PID=""

cleanup() {
  set +e
  if [[ -n "${HIDE_CURSOR_PID}" ]] && kill -0 "${HIDE_CURSOR_PID}" 2>/dev/null; then
    kill "${HIDE_CURSOR_PID}" 2>/dev/null
    wait "${HIDE_CURSOR_PID}" 2>/dev/null
  fi
  if [[ -n "${CHROME_MONITOR_1_PID}" ]] && kill -0 "${CHROME_MONITOR_1_PID}" 2>/dev/null; then
    kill "${CHROME_MONITOR_1_PID}" 2>/dev/null
    wait "${CHROME_MONITOR_1_PID}" 2>/dev/null
  fi
  if [[ -n "${CHROME_MONITOR_2_PID}" ]] && kill -0 "${CHROME_MONITOR_2_PID}" 2>/dev/null; then
    kill "${CHROME_MONITOR_2_PID}" 2>/dev/null
    wait "${CHROME_MONITOR_2_PID}" 2>/dev/null
  fi
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

unlock_chromium_profile() {
  local profile_dir="$1"

  [[ -d "${profile_dir}" ]] || return 0
  find "${profile_dir}" -maxdepth 1     \( -name "SingletonLock" -o -name "SingletonSocket" -o -name "SingletonCookie" -o -name "Singleton*" \)     -print -delete 2>/dev/null || true
}

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

disable_x_power_save() {
  if [[ "${KIOSK_DISABLE_POWER_SAVE}" != "1" ]]; then
    return 0
  fi

  if ! command -v xset >/dev/null 2>&1; then
    echo "xset non trovato: impossibile disattivare risparmio energetico display" >&2
    return 0
  fi

  xset s 0 0 >/dev/null 2>&1 || true
  xset s off >/dev/null 2>&1 || true
  xset s noblank >/dev/null 2>&1 || true
  xset -dpms >/dev/null 2>&1 || true
  echo "Risparmio energetico display disattivato: screensaver off, blanking off, DPMS off"
}

array_contains() {
  local needle="$1"
  shift
  local item
  for item in "$@"; do
    [[ "${item}" == "${needle}" ]] && return 0
  done
  return 1
}

configure_mirrored_displays() {
  if [[ "${KIOSK_DISPLAY_PROFILE}" == "monitor" ]]; then
    return 0
  fi
  if [[ "${KIOSK_MIRROR_DISPLAYS}" != "1" ]]; then
    return 0
  fi

  if ! command -v xrandr >/dev/null 2>&1; then
    echo "xrandr non trovato: salto clone HDMI" >&2
    return 0
  fi

  local query primary secondary detected_primary output
  local outputs=()
  query="$(xrandr --query 2>/dev/null || true)"
  if [[ -z "${query}" ]]; then
    echo "xrandr non disponibile: salto clone HDMI" >&2
    return 0
  fi

  while IFS= read -r output; do
    [[ -n "${output}" ]] && outputs+=("${output}")
  done < <(printf '%s\n' "${query}" | awk '$2 == "connected" {print $1}')

  if (( ${#outputs[@]} < 2 )); then
    echo "Clone HDMI non necessario: uscite connesse=${#outputs[@]}" >&2
    return 0
  fi

  detected_primary="$(printf '%s\n' "${query}" | awk '$2 == "connected" && $3 == "primary" {print $1; exit}')"

  if [[ -n "${KIOSK_MIRROR_PRIMARY_OUTPUT}" ]] && array_contains "${KIOSK_MIRROR_PRIMARY_OUTPUT}" "${outputs[@]}"; then
    primary="${KIOSK_MIRROR_PRIMARY_OUTPUT}"
  elif [[ -n "${detected_primary}" ]]; then
    primary="${detected_primary}"
  else
    primary="${outputs[0]}"
  fi

  if [[ -n "${KIOSK_MIRROR_SECONDARY_OUTPUT}" ]] && [[ "${KIOSK_MIRROR_SECONDARY_OUTPUT}" != "${primary}" ]] && array_contains "${KIOSK_MIRROR_SECONDARY_OUTPUT}" "${outputs[@]}"; then
    secondary="${KIOSK_MIRROR_SECONDARY_OUTPUT}"
  else
    secondary=""
    for output in "${outputs[@]}"; do
      if [[ "${output}" != "${primary}" ]]; then
        secondary="${output}"
        break
      fi
    done
  fi

  if [[ -z "${secondary}" ]]; then
    echo "Clone HDMI non configurabile: secondary vuota" >&2
    return 0
  fi

  local args=(--output "${primary}" --primary --auto)
  if [[ -n "${KIOSK_MIRROR_MODE}" ]]; then
    args+=(--mode "${KIOSK_MIRROR_MODE}")
  fi
  args+=(--output "${secondary}" --same-as "${primary}" --auto)
  if [[ -n "${KIOSK_MIRROR_MODE}" ]]; then
    args+=(--mode "${KIOSK_MIRROR_MODE}")
  fi

  if xrandr "${args[@]}"; then
    echo "Display HDMI clonati: ${secondary} segue ${primary}"
  else
    echo "Impossibile clonare HDMI con xrandr: ${secondary} -> ${primary}" >&2
  fi
}

monitor_output_geometry() {
  local output="$1" mode
  mode="$(xrandr --query | awk -v name="${output}" '$1 == name && $2 == "connected" { for (i = 3; i <= NF; i++) if ($i ~ /^[0-9]+x[0-9]+\+[0-9]+\+[0-9]+$/) { print $i; exit } }')"
  if [[ "${mode}" =~ ^([0-9]+)x([0-9]+)\+([0-9]+)\+([0-9]+)$ ]]; then
    printf '%s,%s,%s,%s\n' "${BASH_REMATCH[3]}" "${BASH_REMATCH[4]}" "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}"
  fi
}

configure_monitor_displays() {
  command -v xrandr >/dev/null 2>&1 || { echo "MONITOR richiede xrandr" >&2; return 1; }
  local query primary secondary output
  local outputs=()
  query="$(xrandr --query)" || return 1
  while IFS= read -r output; do
    [[ -n "${output}" ]] && outputs+=("${output}")
  done < <(printf '%s\n' "${query}" | awk '$2 == "connected" {print $1}')
  (( ${#outputs[@]} > 0 )) || { echo "MONITOR: nessuna uscita HDMI connessa" >&2; return 1; }

  if [[ -n "${KIOSK_MONITOR_PRIMARY_OUTPUT}" ]] && array_contains "${KIOSK_MONITOR_PRIMARY_OUTPUT}" "${outputs[@]}"; then
    primary="${KIOSK_MONITOR_PRIMARY_OUTPUT}"
  else
    primary="${outputs[0]}"
    for output in "${outputs[@]}"; do
      if [[ "${output}" == HDMI-1 || "${output}" == HDMI-A-1 ]]; then primary="${output}"; break; fi
    done
  fi
  secondary=""
  if [[ -n "${KIOSK_MONITOR_SECONDARY_OUTPUT}" ]] && [[ "${KIOSK_MONITOR_SECONDARY_OUTPUT}" != "${primary}" ]] && array_contains "${KIOSK_MONITOR_SECONDARY_OUTPUT}" "${outputs[@]}"; then
    secondary="${KIOSK_MONITOR_SECONDARY_OUTPUT}"
  else
    for output in "${outputs[@]}"; do
      if [[ "${output}" != "${primary}" ]]; then secondary="${output}"; break; fi
    done
  fi

  if [[ -n "${secondary}" ]]; then
    xrandr --output "${primary}" --primary --auto --pos 0x0 --output "${secondary}" --auto --right-of "${primary}" || return 1
  else
    xrandr --output "${primary}" --primary --auto --pos 0x0 || return 1
  fi
  MONITOR_PRIMARY_GEOMETRY="$(monitor_output_geometry "${primary}")"
  [[ -n "${MONITOR_PRIMARY_GEOMETRY}" ]] || { echo "MONITOR: geometria non trovata per ${primary}" >&2; return 1; }
  if [[ -n "${secondary}" ]]; then
    MONITOR_SECONDARY_GEOMETRY="$(monitor_output_geometry "${secondary}")"
    [[ -n "${MONITOR_SECONDARY_GEOMETRY}" ]] || { echo "MONITOR: geometria non trovata per ${secondary}" >&2; return 1; }
  fi
  echo "MONITOR: ${primary}=${MONITOR_PRIMARY_GEOMETRY} ${secondary:-non connesso}=${MONITOR_SECONDARY_GEOMETRY:-n/a}"
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
  local fullscreen="${3:-0}"
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
  if [[ "${fullscreen}" == "1" ]]; then
    wmctrl -x -r "${class_name}" -b add,fullscreen || true
  fi
}

pcmanfm_wallpaper_mode() {
  case "${KIOSK_WALLPAPER_MODE}" in
    fill) echo "crop" ;;
    scale) echo "stretch" ;;
    max) echo "fit" ;;
    *) echo "${KIOSK_WALLPAPER_MODE}" ;;
  esac
}

feh_wallpaper_flag() {
  case "${KIOSK_WALLPAPER_MODE}" in
    fit) echo "--bg-scale" ;;
    fill|crop) echo "--bg-fill" ;;
    center) echo "--bg-center" ;;
    tile) echo "--bg-tile" ;;
    max) echo "--bg-max" ;;
    stretch|scale) echo "--bg-scale" ;;
    *) echo "--bg-scale" ;;
  esac
}

write_pcmanfm_wallpaper_config() {
  local config_file="$1"
  local config_dir
  local config_tmp
  local pcmanfm_mode

  config_dir="$(dirname "${config_file}")"
  config_tmp="${config_file}.tmp"
  pcmanfm_mode="$(pcmanfm_wallpaper_mode)"
  mkdir -p "${config_dir}"

  if [[ ! -f "${config_file}" ]]; then
    cat >"${config_file}" <<EOF
[*]
wallpaper=${KIOSK_WALLPAPER}
wallpaper_mode=${pcmanfm_mode}
desktop_bg=#000000
desktop_fg=#ffffff
desktop_shadow=#000000
show_wm_menu=0
show_documents=0
show_trash=0
show_mounts=0
EOF
    return 0
  fi

  awk -v wallpaper="${KIOSK_WALLPAPER}" -v wallpaper_mode="${pcmanfm_mode}" '
    BEGIN {
      in_default = 0
      saw_default = 0
      saw_wallpaper = 0
      saw_wallpaper_mode = 0
    }
    /^\[\*\]$/ {
      in_default = 1
      saw_default = 1
      print
      next
    }
    /^\[/ && $0 !~ /^\[\*\]$/ {
      if (in_default) {
        if (!saw_wallpaper) print "wallpaper=" wallpaper
        if (!saw_wallpaper_mode) print "wallpaper_mode=" wallpaper_mode
      }
      in_default = 0
      print
      next
    }
    in_default && /^wallpaper=/ {
      print "wallpaper=" wallpaper
      saw_wallpaper = 1
      next
    }
    in_default && /^wallpaper_mode=/ {
      print "wallpaper_mode=" wallpaper_mode
      saw_wallpaper_mode = 1
      next
    }
    { print }
    END {
      if (!saw_default) {
        print "[*]"
        print "wallpaper=" wallpaper
        print "wallpaper_mode=" wallpaper_mode
      } else if (in_default) {
        if (!saw_wallpaper) print "wallpaper=" wallpaper
        if (!saw_wallpaper_mode) print "wallpaper_mode=" wallpaper_mode
      }
    }
  ' "${config_file}" >"${config_tmp}"
  mv "${config_tmp}" "${config_file}"
}

set_pcmanfm_wallpaper() {
  local pcmanfm_dir="${KIOSK_HOME}/.config/pcmanfm"
  local config_file
  local profile
  local wrote_config=0
  local profiles=(
    "${KIOSK_PCMANFM_PROFILE}"
    "LXDE-pi"
    "rpd-x"
    "default"
  )

  for profile in "${profiles[@]}"; do
    [[ -z "${profile}" ]] && continue
    config_file="${pcmanfm_dir}/${profile}/desktop-items-0.conf"
    write_pcmanfm_wallpaper_config "${config_file}"
    wrote_config=1
  done

  for config_file in "${pcmanfm_dir}"/*/desktop-items-0.conf; do
    [[ -e "${config_file}" ]] || continue
    write_pcmanfm_wallpaper_config "${config_file}"
    wrote_config=1
  done

  if (( wrote_config == 0 )); then
    return 1
  fi

  if command -v pcmanfm >/dev/null 2>&1; then
    if ! pgrep -u "$(id -u)" -x pcmanfm >/dev/null 2>&1; then
      pcmanfm --desktop --profile="${KIOSK_PCMANFM_PROFILE}" >/dev/null 2>&1 &
    fi
  fi

  echo "Wallpaper desktop configurato: ${KIOSK_WALLPAPER}"
  return 0
}

set_feh_wallpaper() {
  local feh_flag

  if ! command -v feh >/dev/null 2>&1; then
    return 1
  fi

  feh_flag="$(feh_wallpaper_flag)"
  feh "${feh_flag}" "${KIOSK_WALLPAPER}" >/dev/null 2>&1
}

set_desktop_wallpaper() {
  if [[ "${KIOSK_SET_WALLPAPER}" == "0" ]] || [[ -z "${KIOSK_WALLPAPER}" ]]; then
    return 0
  fi

  if [[ ! -f "${KIOSK_WALLPAPER}" ]]; then
    echo "Wallpaper non trovato: ${KIOSK_WALLPAPER}" >&2
    return 0
  fi

  if [[ "${KIOSK_WALLPAPER_BACKEND}" == "auto" || "${KIOSK_WALLPAPER_BACKEND}" == "pcmanfm" ]]; then
    if set_pcmanfm_wallpaper; then
      return 0
    fi
  fi

  if [[ "${KIOSK_WALLPAPER_BACKEND}" == "auto" || "${KIOSK_WALLPAPER_BACKEND}" == "feh" ]]; then
    if set_feh_wallpaper; then
      return 0
    fi
  fi

  if [[ "${KIOSK_WALLPAPER_BACKEND}" == "auto" || "${KIOSK_WALLPAPER_BACKEND}" == "pcmanfm-qt" ]]; then
    if command -v pcmanfm-qt >/dev/null 2>&1 && pgrep -u "$(id -u)" -x pcmanfm-qt >/dev/null 2>&1; then
      pcmanfm-qt --set-wallpaper="${KIOSK_WALLPAPER}" --wallpaper-mode="$(pcmanfm_wallpaper_mode)" >/dev/null 2>&1 || \
        echo "Impossibile impostare wallpaper con pcmanfm-qt: ${KIOSK_WALLPAPER}" >&2
      return 0
    fi
  fi

  if [[ "${KIOSK_WALLPAPER_BACKEND}" != "auto" ]]; then
    echo "Backend wallpaper non disponibile o non attivo: ${KIOSK_WALLPAPER_BACKEND}" >&2
    return 0
  fi

  echo "Nessun gestore wallpaper attivo: installa feh oppure usa KIOSK_WALLPAPER_BACKEND=pcmanfm" >&2
}

disable_pcmanfm_usb_prompt() {
  local pcmanfm_dir="${KIOSK_HOME}/.config/pcmanfm"
  local profile config_file config_tmp
  local profiles=("${KIOSK_PCMANFM_PROFILE}" "LXDE-pi" "LXDE" "rpd-x" "default")

  for config_file in "${pcmanfm_dir}"/*/pcmanfm.conf; do
    [[ -e "${config_file}" ]] || continue
    profiles+=("$(basename "$(dirname "${config_file}")")")
  done

  for profile in "${profiles[@]}"; do
    [[ -n "${profile}" ]] || continue
    config_file="${pcmanfm_dir}/${profile}/pcmanfm.conf"
    mkdir -p "$(dirname "${config_file}")"
    config_tmp="$(mktemp "${config_file}.XXXXXX")"
    if [[ -f "${config_file}" ]]; then
      awk '
        /^\[volume\]$/ { in_volume = 1; has_volume = 1; print; next }
        /^\[/ && in_volume { if (!has_autorun) print "autorun=0"; in_volume = 0 }
        in_volume && /^autorun=/ { if (!has_autorun) print "autorun=0"; has_autorun = 1; next }
        { print }
        END {
          if (in_volume && !has_autorun) print "autorun=0"
          if (!has_volume) print "[volume]\nautorun=0"
        }
      ' "${config_file}" >"${config_tmp}"
    else
      printf '[volume]\nmount_removable=1\nautorun=0\n' >"${config_tmp}"
    fi
    if cmp -s "${config_tmp}" "${config_file}"; then
      rm -f "${config_tmp}"
    else
      mv "${config_tmp}" "${config_file}"
    fi
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
  unlock_chromium_profile "${profile_dir}"

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
  unlock_chromium_profile "${KIOSK_LEFT_PROFILE_DIR}"
  unlock_chromium_profile "${KIOSK_RIGHT_PROFILE_DIR}"

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
    --bwsi \
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
  echo "Profilo sottopedana: SX 1152x96 + 1536x96, DX 1536x96 + 1152x96"
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

launch_monitor_windows() {
  wait_for_http_url "${KIOSK_MONITOR_URL}"
  launch_chromium_app_window "${KIOSK_MONITOR_URL}" "${KIOSK_MONITOR_1_PROFILE_DIR}" "kiosk_monitor_1" "${MONITOR_PRIMARY_GEOMETRY}" "1"
  CHROME_MONITOR_1_PID="${LAST_CHROME_PID}"
  configure_window "kiosk_monitor_1" "${MONITOR_PRIMARY_GEOMETRY}" "1" &

  if [[ -n "${MONITOR_SECONDARY_GEOMETRY}" ]]; then
    launch_chromium_app_window "${KIOSK_MONITOR_URL}" "${KIOSK_MONITOR_2_PROFILE_DIR}" "kiosk_monitor_2" "${MONITOR_SECONDARY_GEOMETRY}" "1"
    CHROME_MONITOR_2_PID="${LAST_CHROME_PID}"
    configure_window "kiosk_monitor_2" "${MONITOR_SECONDARY_GEOMETRY}" "1" &
  fi
  echo "Chromium MONITOR avviato: HDMI1=${CHROME_MONITOR_1_PID} HDMI2=${CHROME_MONITOR_2_PID:-non connesso}"
}

launch_single_window() {
  mkdir -p "${CHROMIUM_PROFILE_DIR}"
  # Prevent stale instances from stacking black overlay windows.
  pkill -f "${CHROMIUM_BIN}.*${CHROMIUM_PROFILE_DIR}" >/dev/null 2>&1 || true
  unlock_chromium_profile "${CHROMIUM_PROFILE_DIR}"
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
if [[ -z "${DBUS_SESSION_BUS_ADDRESS:-}" ]] && [[ -S "/run/user/$(id -u)/bus" ]]; then
  export DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$(id -u)/bus"
fi
disable_x_power_save
configure_mirrored_displays
if [[ "${KIOSK_DISPLAY_PROFILE}" == "monitor" ]]; then
  configure_monitor_displays
  if [[ "${KIOSK_MONITOR_HIDE_CURSOR}" == "1" ]]; then
    python3 "${APP_DIR}/tools/systemd/hide-x11-cursor.py" &
    HIDE_CURSOR_PID=$!
  fi
fi
wait_for_http
disable_pcmanfm_usb_prompt
set_desktop_wallpaper
sleep "${CHROMIUM_START_DELAY_SEC}"

if [[ "${KIOSK_DISPLAY_PROFILE}" == "sottopedana" ]]; then
  launch_underfloor_windows
elif [[ "${KIOSK_DISPLAY_PROFILE}" == "monitor" ]]; then
  launch_monitor_windows
elif [[ "${KIOSK_WINDOW_MODE}" == "dual" ]]; then
  launch_dual_windows
else
  launch_single_window
fi

set +e
if [[ "${KIOSK_DISPLAY_PROFILE}" == "sottopedana" ]]; then
  wait -n "${NODE_PID}" "${CHROME_UNDERFLOOR_LEFT_A_PID}" "${CHROME_UNDERFLOOR_LEFT_B_PID}" "${CHROME_UNDERFLOOR_RIGHT_A_PID}" "${CHROME_UNDERFLOOR_RIGHT_B_PID}"
elif [[ "${KIOSK_DISPLAY_PROFILE}" == "monitor" ]]; then
  if [[ -n "${CHROME_MONITOR_2_PID}" ]]; then
    wait -n "${NODE_PID}" "${CHROME_MONITOR_1_PID}" "${CHROME_MONITOR_2_PID}"
  else
    wait -n "${NODE_PID}" "${CHROME_MONITOR_1_PID}"
  fi
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

if [[ "${KIOSK_DISPLAY_PROFILE}" == "monitor" ]] && ! kill -0 "${CHROME_MONITOR_1_PID}" 2>/dev/null; then
  echo "Chromium monitor HDMI1 terminato, richiesto restart service" >&2
fi
if [[ "${KIOSK_DISPLAY_PROFILE}" == "monitor" ]] && [[ -n "${CHROME_MONITOR_2_PID}" ]] && ! kill -0 "${CHROME_MONITOR_2_PID}" 2>/dev/null; then
  echo "Chromium monitor HDMI2 terminato, richiesto restart service" >&2
fi
if [[ "${KIOSK_DISPLAY_PROFILE}" == "ledwall" ]] && [[ "${KIOSK_WINDOW_MODE}" == "single" ]] && ! kill -0 "${CHROME_PID}" 2>/dev/null; then
  echo "Chromium terminato, richiesto restart service" >&2
fi

if [[ "${KIOSK_DISPLAY_PROFILE}" == "ledwall" ]] && [[ "${KIOSK_WINDOW_MODE}" == "dual" ]] && ! kill -0 "${CHROME_LEFT_PID}" 2>/dev/null; then
  echo "Chromium sinistro terminato, richiesto restart service" >&2
fi

if [[ "${KIOSK_DISPLAY_PROFILE}" == "ledwall" ]] && [[ "${KIOSK_WINDOW_MODE}" == "dual" ]] && ! kill -0 "${CHROME_RIGHT_PID}" 2>/dev/null; then
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
