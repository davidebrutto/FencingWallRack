#!/usr/bin/env bash
set -Eeuo pipefail

FENCEWALL_USER="${FENCEWALL_USER:-fencewall}"
FENCEWALL_GROUP="${FENCEWALL_GROUP:-${FENCEWALL_USER}}"
APP_DIR="${APP_DIR:-/home/${FENCEWALL_USER}/FencingWallRack}"
HOSTNAME_VALUE="${1:-${FENCEWALL_HOSTNAME:-}}"
REPO_URL="${REPO_URL:-https://github.com/davidebrutto/FencingWallRack.git}"
BOOT_DIR="/boot/firmware"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Esegui con sudo: sudo bash tools/install-raspberry.sh FENCEWALL-001" >&2
  exit 1
fi

log() {
  echo "[FENCEWALL install] $*"
}

ensure_user() {
  if ! id "${FENCEWALL_USER}" >/dev/null 2>&1; then
    log "Creo utente ${FENCEWALL_USER}"
    useradd -m -s /bin/bash "${FENCEWALL_USER}"
    usermod -aG sudo,video,render,input,gpio,spi,i2c,dialout,plugdev,netdev "${FENCEWALL_USER}" || true
  else
    usermod -aG sudo,video,render,input,gpio,spi,i2c,dialout,plugdev,netdev "${FENCEWALL_USER}" || true
  fi
}

set_hostname_if_requested() {
  if [[ -z "${HOSTNAME_VALUE}" ]]; then
    log "Hostname non passato: lascio $(hostname)"
    return 0
  fi
  log "Imposto hostname ${HOSTNAME_VALUE}"
  hostnamectl set-hostname "${HOSTNAME_VALUE}"
  if grep -q '^127\.0\.1\.1' /etc/hosts; then
    sed -i "s/^127\.0\.1\.1.*/127.0.1.1\t${HOSTNAME_VALUE}/" /etc/hosts
  else
    printf '127.0.1.1\t%s\n' "${HOSTNAME_VALUE}" >> /etc/hosts
  fi
}

install_packages() {
  log "Aggiorno apt e installo pacchetti"
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y \
    git curl ca-certificates build-essential python3 python3-venv python3-pip python3-pil \
    nodejs npm chromium-browser wmctrl x11-xserver-utils x11-utils xserver-xorg lightdm \
    pcmanfm openbox lxsession lxpanel lxde-core network-manager sqlite3 plymouth \
    rpi-eeprom raspi-config i2c-tools python3-lgpio python3-gpiozero python3-spidev

  # Raspberry Pi OS desktop packages are not always present on generic Debian repos.
  DEBIAN_FRONTEND=noninteractive apt-get install -y raspberrypi-ui-mods || true
}

ensure_repo() {
  if [[ ! -d "${APP_DIR}/.git" ]]; then
    log "Clono repository in ${APP_DIR}"
    rm -rf "${APP_DIR}"
    sudo -u "${FENCEWALL_USER}" git clone "${REPO_URL}" "${APP_DIR}"
  else
    log "Repository gia presente: ${APP_DIR}"
  fi
  chown -R "${FENCEWALL_USER}:${FENCEWALL_GROUP}" "${APP_DIR}"
}

install_node_dependencies() {
  log "Installo dipendenze Node"
  sudo -u "${FENCEWALL_USER}" bash -lc "cd '${APP_DIR}' && npm install"
}

install_oled_dependencies() {
  log "Installo ambiente Python OLED"
  python3 -m venv "${APP_DIR}/.venv-oled"
  "${APP_DIR}/.venv-oled/bin/pip" install --upgrade pip wheel
  "${APP_DIR}/.venv-oled/bin/pip" install -r "${APP_DIR}/tools/oled_network/requirements.txt"
  chown -R "${FENCEWALL_USER}:${FENCEWALL_GROUP}" "${APP_DIR}/.venv-oled"
}

write_kiosk_service() {
  log "Installo servizio kiosk"
  cat > /etc/systemd/system/fencingwallrack-kiosk.service <<EOF_SERVICE
[Unit]
Description=FencingWallRack Node + Chromium Kiosk
After=network-online.target graphical.target
Wants=network-online.target

[Service]
Type=simple
User=${FENCEWALL_USER}
Group=${FENCEWALL_GROUP}
WorkingDirectory=${APP_DIR}
EnvironmentFile=-/etc/default/fencingwallrack-kiosk
Environment=NODE_ENV=production
ExecStart=${APP_DIR}/tools/systemd/run-kiosk-stack.sh
Restart=always
RestartSec=2
KillMode=control-group
TimeoutStopSec=15
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=graphical.target
EOF_SERVICE
}

write_oled_service() {
  log "Installo servizio OLED"
  cp "${APP_DIR}/tools/oled_network/fencingwallrack-oled-network.service" /etc/systemd/system/fencingwallrack-oled-network.service
}

install_env_files() {
  log "Installo configurazioni /etc/default se mancanti"
  if [[ ! -f /etc/default/fencingwallrack-kiosk ]]; then
    cp "${APP_DIR}/tools/systemd/fencingwallrack-kiosk.env.example" /etc/default/fencingwallrack-kiosk
  fi
  if [[ ! -f /etc/default/fencingwallrack-oled-network ]]; then
    cp "${APP_DIR}/tools/oled_network/fencingwallrack-oled-network.env.example" /etc/default/fencingwallrack-oled-network
  fi

  sed -i "s|^APP_DIR=.*|APP_DIR=${APP_DIR}|" /etc/default/fencingwallrack-kiosk
  sed -i "s|^XAUTHORITY=.*|XAUTHORITY=/home/${FENCEWALL_USER}/.Xauthority|" /etc/default/fencingwallrack-kiosk
  sed -i "s|^CHROMIUM_PROFILE_DIR=.*|CHROMIUM_PROFILE_DIR=/home/${FENCEWALL_USER}/.config/fencing-kiosk|" /etc/default/fencingwallrack-kiosk
  sed -i "s|/home/fencewall/FencingWallRack|${APP_DIR}|g" /etc/default/fencingwallrack-kiosk
  sed -i "s|/home/fencewall/FencingWallRack|${APP_DIR}|g" /etc/default/fencingwallrack-oled-network
}

detect_desktop_session() {
  local session_file session_name
  for session_file in \
    /usr/share/xsessions/LXDE-pi.desktop \
    /usr/share/xsessions/rpd-x.desktop \
    /usr/share/xsessions/LXDE.desktop \
    /usr/share/xsessions/openbox.desktop; do
    if [[ -f "${session_file}" ]]; then
      session_name="$(basename "${session_file}" .desktop)"
      echo "${session_name}"
      return 0
    fi
  done
  session_file="$(find /usr/share/xsessions -maxdepth 1 -name '*.desktop' 2>/dev/null | head -n 1 || true)"
  if [[ -n "${session_file}" ]]; then
    basename "${session_file}" .desktop
    return 0
  fi
  echo "LXDE-pi"
}

configure_desktop_session() {
  log "Configuro sessione grafica e autologin"
  local session_name
  session_name="$(detect_desktop_session)"

  mkdir -p "/home/${FENCEWALL_USER}"
  cat > "/home/${FENCEWALL_USER}/.dmrc" <<EOF_DMRC
[Desktop]
Session=${session_name}
EOF_DMRC
  chown "${FENCEWALL_USER}:${FENCEWALL_GROUP}" "/home/${FENCEWALL_USER}/.dmrc"

  mkdir -p /etc/lightdm/lightdm.conf.d
  cat > /etc/lightdm/lightdm.conf.d/50-fencewall-autologin.conf <<EOF_LIGHTDM
[Seat:*]
autologin-user=${FENCEWALL_USER}
autologin-user-timeout=0
user-session=${session_name}
EOF_LIGHTDM

  systemctl set-default graphical.target
  systemctl enable lightdm.service || true
  raspi-config nonint do_boot_behaviour B4 || true
}

enable_spi_i2c() {
  log "Abilito SPI/I2C"
  raspi-config nonint do_spi 0 || true
  raspi-config nonint do_i2c 0 || true
  mkdir -p "${BOOT_DIR}"
  touch "${BOOT_DIR}/config.txt"
  grep -q '^dtparam=spi=on' "${BOOT_DIR}/config.txt" || printf '\ndtparam=spi=on\n' >> "${BOOT_DIR}/config.txt"
  grep -q '^dtparam=i2c_arm=on' "${BOOT_DIR}/config.txt" || printf 'dtparam=i2c_arm=on\n' >> "${BOOT_DIR}/config.txt"
  grep -q '^disable_splash=1' "${BOOT_DIR}/config.txt" || printf 'disable_splash=1\n' >> "${BOOT_DIR}/config.txt"
}

install_plymouth_theme() {
  log "Installo splash Plymouth FENCEWALL"
  local theme_dir="/usr/share/plymouth/themes/fencingwallrack"
  mkdir -p "${theme_dir}"
  cp "${APP_DIR}/static/sc_avvio.png" "${theme_dir}/splash.png"
  cat > "${theme_dir}/fencingwallrack.plymouth" <<'EOF_PLY'
[Plymouth Theme]
Name=FencingWallRack
Description=FencingWallRack boot splash
ModuleName=script

[script]
ImageDir=/usr/share/plymouth/themes/fencingwallrack
ScriptFile=/usr/share/plymouth/themes/fencingwallrack/fencingwallrack.script
EOF_PLY
  cat > "${theme_dir}/fencingwallrack.script" <<'EOF_SCRIPT'
splash = Image("splash.png");
sprite = Sprite(splash);

screen_w = Window.GetWidth();
screen_h = Window.GetHeight();
image_w = splash.GetWidth();
image_h = splash.GetHeight();

sprite.SetX((screen_w - image_w) / 2);
sprite.SetY((screen_h - image_h) / 2);
EOF_SCRIPT
  plymouth-set-default-theme -R fencingwallrack || true
}

quiet_boot_config() {
  log "Configuro boot silenzioso"
  local cmdline="${BOOT_DIR}/cmdline.txt"
  touch "${cmdline}"
  if [[ ! -s "${cmdline}" && -s /boot/cmdline.txt ]]; then
    cp /boot/cmdline.txt "${cmdline}" || true
  fi
  if [[ -s "${cmdline}" ]]; then
    local line
    line="$(tr '\n' ' ' < "${cmdline}" | sed 's/  */ /g')"
    line="$(printf '%s' "${line}" | sed -E 's/(^| )console=tty1( |$)/ /g; s/  */ /g; s/^ //; s/ $//')"
    for token in quiet splash loglevel=0 systemd.show_status=false rd.udev.log_level=3 vt.global_cursor_default=0 logo.nologo plymouth.ignore-serial-consoles; do
      case " ${line} " in
        *" ${token} "*) ;;
        *) line="${line} ${token}" ;;
      esac
    done
    printf '%s\n' "${line}" > "${cmdline}"
  fi
  systemctl mask cloud-init.service cloud-init-local.service cloud-init-main.service cloud-init-network.service cloud-config.service cloud-final.service cloud-init-hotplugd.service cloud-init-hotplugd.socket cloud-config.target cloud-init.target userconfig.service >/dev/null 2>&1 || true
}

regenerate_machine_identity() {
  log "Rigenero machine-id e chiavi SSH"
  truncate -s 0 /etc/machine-id || true
  rm -f /var/lib/dbus/machine-id
  systemd-machine-id-setup || true
  ln -sf /etc/machine-id /var/lib/dbus/machine-id || true
  rm -f /etc/ssh/ssh_host_*
  dpkg-reconfigure openssh-server || true
  systemctl restart ssh || true
}

enable_services() {
  log "Abilito servizi"
  systemctl daemon-reload
  systemctl enable fencingwallrack-kiosk.service
  systemctl enable fencingwallrack-oled-network.service
}

main() {
  ensure_user
  set_hostname_if_requested
  install_packages
  ensure_repo
  install_node_dependencies
  install_oled_dependencies
  write_kiosk_service
  write_oled_service
  install_env_files
  configure_desktop_session
  enable_spi_i2c
  install_plymouth_theme
  quiet_boot_config
  regenerate_machine_identity
  enable_services

  log "Installazione completata. Riavvia con: sudo reboot"
  log "Poi completa la procedura EEPROM per nascondere la schermata rosa/bianca del Raspberry Pi 5."
}

main "$@"
