#!/usr/bin/env python3
import ipaddress
import glob
import os
import pwd
import queue
import re
import signal
import socket
import subprocess
import sys
import threading
import time

from gpiozero import Button
from luma.core.interface.serial import spi
from luma.oled.device import sh1106
from PIL import Image, ImageDraw, ImageFont

try:
    import qrcode
except ImportError:
    qrcode = None


def env_bool(name, default):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in ("0", "false", "no", "off")


def env_float(name, default):
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value.strip().split()[0])
    except (IndexError, ValueError):
        return default


def env_int(name, default):
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value.strip().split()[0])
    except (IndexError, ValueError):
        return default


def bool_from_value(value, default):
    if value is None or str(value).strip() == "":
        return default
    return str(value).strip().lower() not in ("0", "false", "no", "off", "n")


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WIDTH = int(os.getenv("OLED_WIDTH", "128"))
HEIGHT = int(os.getenv("OLED_HEIGHT", "64"))
ROTATE = int(os.getenv("OLED_ROTATE", "0"))
FLIP_180 = env_bool("OLED_FLIP_180", True)
INPUT_FLIP_180 = env_bool("OLED_INPUT_FLIP_180", FLIP_180)
LOGO_PATH = os.getenv("OLED_LOGO_PATH", os.path.join(SCRIPT_DIR, "logo.png"))
LOGO_TIMEOUT_SEC = env_float("OLED_LOGO_TIMEOUT_SEC", 10)
HOSTNAME_FONT_PATH = os.getenv("OLED_HOSTNAME_FONT_PATH", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")
HOSTNAME_FONT_SIZE = env_int("OLED_HOSTNAME_FONT_SIZE", 12)
KIOSK_ENV_PATH = os.getenv("KIOSK_ENV_PATH", "/etc/default/fencingwallrack-kiosk")
KIOSK_SERVICE = os.getenv("KIOSK_SERVICE", "fencingwallrack-kiosk.service")
RESTART_KIOSK_ON_PROFILE_SAVE = env_bool("OLED_RESTART_KIOSK_ON_PROFILE_SAVE", True)
REBOOT_ON_PROFILE_SAVE = env_bool("OLED_REBOOT_ON_PROFILE_SAVE", True)
REBOOT_DELAY_SEC = env_float("OLED_REBOOT_DELAY_SEC", 2)
SPI_PORT = int(os.getenv("OLED_SPI_PORT", "0"))
SPI_DEVICE = int(os.getenv("OLED_SPI_DEVICE", "0"))
GPIO_DC = int(os.getenv("OLED_GPIO_DC", "24"))
GPIO_RST = int(os.getenv("OLED_GPIO_RST", "25"))

PINS = {
    "up": int(os.getenv("OLED_BTN_UP", "6")),
    "down": int(os.getenv("OLED_BTN_DOWN", "19")),
    "left": int(os.getenv("OLED_BTN_LEFT", "5")),
    "right": int(os.getenv("OLED_BTN_RIGHT", "26")),
    "press": int(os.getenv("OLED_BTN_PRESS", "13")),
    "k1": int(os.getenv("OLED_BTN_K1", "21")),
    "k2": int(os.getenv("OLED_BTN_K2", "20")),
    "k3": int(os.getenv("OLED_BTN_K3", "16")),
}

DEFAULT_IP = os.getenv("OLED_DEFAULT_IP", "192.168.1.50")
DEFAULT_PREFIX = int(os.getenv("OLED_DEFAULT_PREFIX", "24"))
DEFAULT_GATEWAY = os.getenv("OLED_DEFAULT_GATEWAY", "192.168.1.1")
DEFAULT_DISPLAY_PROFILE = os.getenv("OLED_DEFAULT_DISPLAY_PROFILE", "ledwall")
DEFAULT_SPOT_INACTIVITY_MINUTES = env_int("OLED_DEFAULT_SPOT_INACTIVITY_MINUTES", 5)
SPOT_MIN_MINUTES = env_int("OLED_SPOT_MIN_MINUTES", 1)
SPOT_MAX_MINUTES = env_int("OLED_SPOT_MAX_MINUTES", 60)
SPOT_ENV_KEY = os.getenv("OLED_SPOT_ENV_KEY", "SPOT_INACTIVITY_MINUTES")
DEFAULT_ATHLETE_PLACEHOLDER_ENABLED = env_bool("OLED_DEFAULT_ATHLETE_PLACEHOLDER_ENABLED", True)
ATHLETE_PLACEHOLDER_ENV_KEY = os.getenv("OLED_ATHLETE_PLACEHOLDER_ENV_KEY", "ATHLETE_PLACEHOLDER_ENABLED")
PREFERRED_IFACE = os.getenv("NET_IFACE", "").strip()
DISPLAY_PROFILES = ["ledwall", "sottopedana"]
MAIN_MENU_ITEMS = ["NETWORK", "MODE", "SPOT", "AVATAR ATLETA", "MANUALE", "VERSIONE", "UPDATE", "REBOOT"]
MANUAL_URL = os.getenv("OLED_MANUAL_URL", "https://fencewall.sportlabweb.it/manuale")
UPDATE_APP_DIR = os.getenv("OLED_UPDATE_APP_DIR", os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..")))
FIRMWARE_VERSION_FILE = os.getenv("FENCEWALL_VERSION_FILE", os.path.join(UPDATE_APP_DIR, "VERSION"))
FIRMWARE_VERSION_FALLBACK = os.getenv("FENCEWALL_VERSION", "1.0.1")
UPDATE_GIT_TIMEOUT_SEC = env_int("OLED_UPDATE_GIT_TIMEOUT_SEC", 120)
UPDATE_PIP_TIMEOUT_SEC = env_int("OLED_UPDATE_PIP_TIMEOUT_SEC", 180)
UPDATE_APT_TIMEOUT_SEC = env_int("OLED_UPDATE_APT_TIMEOUT_SEC", 300)
UPDATE_APT_PACKAGES = [
    package.strip()
    for package in os.getenv("OLED_UPDATE_APT_PACKAGES", "ffmpeg").split(",")
    if package.strip()
]
UPDATE_REQUIREMENTS_PATH = os.getenv(
    "OLED_UPDATE_REQUIREMENTS_PATH",
    os.path.join(UPDATE_APP_DIR, "tools", "oled_network", "requirements.txt"),
)


def run(cmd, check=True):
    return subprocess.run(cmd, text=True, capture_output=True, check=check)

def load_firmware_version():
    try:
        with open(FIRMWARE_VERSION_FILE, "r", encoding="utf-8") as file:
            version = file.read().strip()
            if version:
                return version
    except OSError:
        pass
    return FIRMWARE_VERSION_FALLBACK


def load_git_short_revision(app_dir=UPDATE_APP_DIR):
    try:
        result = subprocess.run(
            ["git", "-C", app_dir, "-c", f"safe.directory={app_dir}", "rev-parse", "--short", "HEAD"],
            text=True,
            capture_output=True,
            check=False,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "n/d"


def cmd_ok(cmd):
    try:
        return run(cmd).stdout.strip()
    except subprocess.CalledProcessError:
        return ""


def list_connected_ifaces():
    out = cmd_ok(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "dev", "status"])
    result = []
    for line in out.splitlines():
        parts = line.split(":")
        if len(parts) < 3:
            continue
        dev, typ, state = parts[:3]
        if dev != "lo" and typ == "ethernet" and state == "connected":
            result.append(dev)
    if result:
        return result

    out = cmd_ok(["nmcli", "-t", "-f", "DEVICE,TYPE", "dev", "status"])
    fallback = []
    for line in out.splitlines():
        parts = line.split(":")
        if len(parts) < 2:
            continue
        dev, typ = parts[:2]
        if typ == "ethernet" and dev != "lo" and dev not in fallback:
            fallback.append(dev)

    for dev in os.listdir("/sys/class/net"):
        if dev != "lo" and dev not in fallback:
            wireless_path = os.path.join("/sys/class/net", dev, "wireless")
            if not os.path.exists(wireless_path) and dev.startswith(("eth", "en")):
                fallback.append(dev)
    return fallback or ["eth0"]


def active_connection_for_iface(iface):
    out = cmd_ok(["nmcli", "-t", "-f", "NAME,DEVICE", "con", "show", "--active"])
    for line in out.splitlines():
        if not line:
            continue
        name, _, dev = line.rpartition(":")
        if dev == iface:
            return name
    out = cmd_ok(["nmcli", "-t", "-f", "NAME,DEVICE", "con", "show"])
    for line in out.splitlines():
        name, _, dev = line.rpartition(":")
        if dev == iface:
            return name
    return ""


def get_ipv4_config(iface):
    ip = DEFAULT_IP
    prefix = DEFAULT_PREFIX
    gateway = DEFAULT_GATEWAY
    mode = "DHCP"

    addr = cmd_ok(["ip", "-4", "-o", "addr", "show", "dev", iface])
    match = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)/(\d+)", addr)
    if match:
        ip = match.group(1)
        prefix = int(match.group(2))

    route = cmd_ok(["ip", "route", "show", "default", "dev", iface])
    match = re.search(r"default\s+via\s+(\d+\.\d+\.\d+\.\d+)", route)
    if match:
        gateway = match.group(1)

    conn = active_connection_for_iface(iface)
    if conn:
        method = cmd_ok(["nmcli", "-g", "ipv4.method", "con", "show", conn])
        mode = "DHCP" if method == "auto" else "STATIC"

    return {"ip": ip, "prefix": prefix, "netmask": prefix_to_netmask(prefix), "gateway": gateway, "mode": mode}


def valid_ip(value):
    try:
        ipaddress.IPv4Address(value)
        return True
    except ValueError:
        return False


def prefix_to_netmask(prefix):
    return str(ipaddress.IPv4Network(f"0.0.0.0/{int(prefix)}").netmask)


def netmask_to_prefix(netmask):
    try:
        mask = ipaddress.IPv4Address(netmask)
        network = ipaddress.IPv4Network(f"0.0.0.0/{netmask}", strict=False)
        if str(network.netmask) != str(mask):
            raise ValueError("hostmask is not accepted")
        return int(network.prefixlen)
    except ValueError as exc:
        raise RuntimeError("Subnet mask is not valid") from exc


def apply_network(iface, cfg):
    conn = active_connection_for_iface(iface)
    if not conn:
        raise RuntimeError(f"No active NetworkManager connection for {iface}")

    if cfg["mode"] == "DHCP":
        run(["nmcli", "con", "mod", conn, "ipv4.method", "auto", "ipv4.addresses", "", "ipv4.gateway", "", "ipv4.dns", ""])
    else:
        if not valid_ip(cfg["ip"]) or not valid_ip(cfg["gateway"]):
            raise RuntimeError("IP or gateway is not valid")
        prefix = netmask_to_prefix(cfg.get("netmask", prefix_to_netmask(cfg["prefix"])))
        if not (1 <= prefix <= 32):
            raise RuntimeError("Subnet mask is not valid")
        run([
            "nmcli", "con", "mod", conn,
            "ipv4.method", "manual",
            "ipv4.addresses", f'{cfg["ip"]}/{prefix}',
            "ipv4.gateway", cfg["gateway"],
            "ipv4.dns", cfg["gateway"],
        ])
    run(["nmcli", "con", "up", conn])


def ip_to_chars(ip):
    return list(".".join(part.zfill(3) for part in ip.split(".")))


def chars_to_ip(chars):
    parts = "".join(chars).split(".")
    return ".".join(str(min(255, int(part or "0"))) for part in parts)


def numeric_positions(chars):
    return [i for i, ch in enumerate(chars) if ch.isdigit()]


def normalize_display_profile(value):
    value = (value or "").strip().lower()
    if value in ("sottopedana", "underfloor", "pedana"):
        return "sottopedana"
    return "ledwall"


def display_profile_label(value):
    return "SOTTOPEDANA" if normalize_display_profile(value) == "sottopedana" else "LEDWALL"


def read_env_value(path, key):
    try:
        with open(path, "r", encoding="utf-8") as file:
            for line in file:
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or "=" not in stripped:
                    continue
                current_key, current_value = stripped.split("=", 1)
                if current_key == key:
                    return current_value.strip().strip('"').strip("'")
    except FileNotFoundError:
        return ""
    return ""


def write_env_value(path, key, value):
    lines = []
    found = False
    changed = True

    try:
        with open(path, "r", encoding="utf-8") as file:
            lines = file.readlines()
    except FileNotFoundError:
        lines = []

    next_line = f"{key}={value}\n"
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in stripped:
            continue
        current_key, _ = stripped.split("=", 1)
        if current_key == key:
            found = True
            changed = line != next_line
            lines[idx] = next_line
            break

    if not found:
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        lines.append(next_line)

    if changed or not found:
        tmp_path = f"{path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as file:
            file.writelines(lines)
        os.replace(tmp_path, path)
        return True
    return False


def load_kiosk_display_profile():
    value = read_env_value(KIOSK_ENV_PATH, "KIOSK_DISPLAY_PROFILE") or DEFAULT_DISPLAY_PROFILE
    return normalize_display_profile(value)


def apply_kiosk_display_profile(profile):
    return write_env_value(KIOSK_ENV_PATH, "KIOSK_DISPLAY_PROFILE", normalize_display_profile(profile))


def clamp_spot_minutes(value):
    try:
        minutes = int(value)
    except (TypeError, ValueError):
        minutes = DEFAULT_SPOT_INACTIVITY_MINUTES
    return max(SPOT_MIN_MINUTES, min(SPOT_MAX_MINUTES, minutes))


def load_spot_inactivity_minutes():
    value = read_env_value(KIOSK_ENV_PATH, SPOT_ENV_KEY)
    return clamp_spot_minutes(value or DEFAULT_SPOT_INACTIVITY_MINUTES)


def apply_spot_inactivity_minutes(minutes):
    return write_env_value(KIOSK_ENV_PATH, SPOT_ENV_KEY, str(clamp_spot_minutes(minutes)))


def load_athlete_placeholder_enabled():
    value = read_env_value(KIOSK_ENV_PATH, ATHLETE_PLACEHOLDER_ENV_KEY)
    return bool_from_value(value, DEFAULT_ATHLETE_PLACEHOLDER_ENABLED)


def apply_athlete_placeholder_enabled(enabled):
    return write_env_value(KIOSK_ENV_PATH, ATHLETE_PLACEHOLDER_ENV_KEY, "1" if enabled else "0")


def pcmanfm_wallpaper_mode(value):
    mode = (value or "fit").strip().lower()
    if mode == "fill":
        return "crop"
    if mode == "scale":
        return "stretch"
    if mode == "max":
        return "fit"
    return mode


def kiosk_home_from_env():
    kiosk_home = read_env_value(KIOSK_ENV_PATH, "KIOSK_HOME")
    if kiosk_home:
        return kiosk_home

    xauthority = read_env_value(KIOSK_ENV_PATH, "XAUTHORITY")
    if xauthority.endswith("/.Xauthority"):
        return os.path.dirname(xauthority)

    return "/home/fencewall"


def kiosk_wallpaper_for_profile(profile):
    normalized_profile = normalize_display_profile(profile)
    if normalized_profile == "sottopedana":
        wallpaper = read_env_value(KIOSK_ENV_PATH, "KIOSK_UNDERFLOOR_WALLPAPER")
    else:
        wallpaper = read_env_value(KIOSK_ENV_PATH, "KIOSK_LEDWALL_WALLPAPER")
    return wallpaper or read_env_value(KIOSK_ENV_PATH, "KIOSK_WALLPAPER")


def chown_like_home(path, kiosk_home):
    try:
        home_stat = os.stat(kiosk_home)
        os.chown(path, home_stat.st_uid, home_stat.st_gid)
    except OSError:
        pass


def update_pcmanfm_wallpaper_config(config_path, wallpaper, wallpaper_mode, kiosk_home):
    config_dir = os.path.dirname(config_path)
    os.makedirs(config_dir, exist_ok=True)
    chown_like_home(config_dir, kiosk_home)

    try:
        with open(config_path, "r", encoding="utf-8") as file:
            lines = file.readlines()
    except FileNotFoundError:
        lines = []

    output = []
    in_default = False
    saw_default = False
    saw_wallpaper = False
    saw_wallpaper_mode = False

    for line in lines:
        stripped = line.strip()
        if stripped == "[*]":
            in_default = True
            saw_default = True
            output.append(line)
            continue

        if stripped.startswith("[") and stripped.endswith("]") and in_default:
            if not saw_wallpaper:
                output.append(f"wallpaper={wallpaper}\n")
            if not saw_wallpaper_mode:
                output.append(f"wallpaper_mode={wallpaper_mode}\n")
            in_default = False
            output.append(line)
            continue

        if in_default and stripped.startswith("wallpaper="):
            output.append(f"wallpaper={wallpaper}\n")
            saw_wallpaper = True
            continue

        if in_default and stripped.startswith("wallpaper_mode="):
            output.append(f"wallpaper_mode={wallpaper_mode}\n")
            saw_wallpaper_mode = True
            continue

        output.append(line)

    if not saw_default:
        if output and not output[-1].endswith("\n"):
            output[-1] += "\n"
        output.extend([
            "[*]\n",
            f"wallpaper={wallpaper}\n",
            f"wallpaper_mode={wallpaper_mode}\n",
            "desktop_bg=#000000\n",
            "desktop_fg=#ffffff\n",
            "desktop_shadow=#000000\n",
            "show_wm_menu=0\n",
            "show_documents=0\n",
            "show_trash=0\n",
            "show_mounts=0\n",
        ])
    elif in_default:
        if not saw_wallpaper:
            output.append(f"wallpaper={wallpaper}\n")
        if not saw_wallpaper_mode:
            output.append(f"wallpaper_mode={wallpaper_mode}\n")

    tmp_path = f"{config_path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as file:
        file.writelines(output)
    os.replace(tmp_path, config_path)
    chown_like_home(config_path, kiosk_home)


def prepare_desktop_wallpaper_for_profile(profile):
    wallpaper = kiosk_wallpaper_for_profile(profile)
    if not wallpaper or not os.path.exists(wallpaper):
        print(f"Wallpaper not found for {profile}: {wallpaper}", file=sys.stderr)
        return

    kiosk_home = kiosk_home_from_env()
    pcmanfm_dir = os.path.join(kiosk_home, ".config", "pcmanfm")
    wallpaper_mode = pcmanfm_wallpaper_mode(read_env_value(KIOSK_ENV_PATH, "KIOSK_WALLPAPER_MODE") or "fit")
    preferred_profile = read_env_value(KIOSK_ENV_PATH, "KIOSK_PCMANFM_PROFILE") or "LXDE-pi"
    profiles = [preferred_profile, "LXDE-pi", "rpd-x", "default"]
    config_paths = []

    for pcmanfm_profile in profiles:
        if pcmanfm_profile:
            config_paths.append(os.path.join(pcmanfm_dir, pcmanfm_profile, "desktop-items-0.conf"))

    config_paths.extend(glob.glob(os.path.join(pcmanfm_dir, "*", "desktop-items-0.conf")))

    for config_path in dict.fromkeys(config_paths):
        update_pcmanfm_wallpaper_config(config_path, wallpaper, wallpaper_mode, kiosk_home)


def restart_kiosk_service():
    if not RESTART_KIOSK_ON_PROFILE_SAVE:
        return
    run(["systemctl", "restart", KIOSK_SERVICE])


def reboot_system():
    commands = [
        ["/usr/bin/systemctl", "--no-block", "reboot"],
        ["/bin/systemctl", "--no-block", "reboot"],
        ["/usr/sbin/reboot"],
        ["/sbin/reboot"],
        ["reboot"],
    ]
    last_error = None
    for cmd in commands:
        if os.path.isabs(cmd[0]) and not os.path.exists(cmd[0]):
            continue
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
            return
        except OSError as exc:
            last_error = exc
    raise RuntimeError(f"Reboot command failed: {last_error}")


def reboot_after_delay(delay_sec):
    time.sleep(delay_sec)
    reboot_system()

def git_owner_command(app_dir, git_args):
    git_cmd = ["git", "-C", app_dir, "-c", f"safe.directory={app_dir}"] + git_args
    try:
        stat_info = os.stat(app_dir)
    except OSError:
        return git_cmd

    if os.geteuid() != 0 or stat_info.st_uid == 0:
        return git_cmd

    try:
        owner = pwd.getpwuid(stat_info.st_uid).pw_name
    except KeyError:
        return git_cmd

    runuser_path = "/usr/sbin/runuser" if os.path.exists("/usr/sbin/runuser") else "runuser"
    return [runuser_path, "-u", owner, "--"] + git_cmd


def run_git(app_dir, git_args, timeout=UPDATE_GIT_TIMEOUT_SEC):
    return subprocess.run(
        git_owner_command(app_dir, git_args),
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )


def compact_git_output(result):
    output = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part and part.strip())
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return lines


def run_oled_requirements_install(timeout=UPDATE_PIP_TIMEOUT_SEC):
    if not os.path.isfile(UPDATE_REQUIREMENTS_PATH):
        return {"ok": True, "lines": ["DEPS SKIP", "No requirements"]}

    env = os.environ.copy()
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", UPDATE_REQUIREMENTS_PATH],
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
        env=env,
    )
    if result.returncode != 0:
        return {"ok": False, "lines": ["DEPS ERROR"] + compact_git_output(result)[:4]}

    lines = compact_git_output(result)
    installed = any(
        text in line
        for line in lines
        for text in ("Successfully installed", "Installing collected packages")
    )
    return {
        "ok": True,
        "installed": installed,
        "lines": ["DEPS OK", "Installate" if installed else "Gia presenti"],
    }

def is_debian_package_installed(package):
    result = subprocess.run(
        ["dpkg-query", "-W", "-f=${Status}", package],
        text=True,
        capture_output=True,
        check=False,
        timeout=15,
    )
    return result.returncode == 0 and "install ok installed" in result.stdout


def run_system_dependencies_install(timeout=UPDATE_APT_TIMEOUT_SEC):
    packages = [package for package in UPDATE_APT_PACKAGES if package]
    if not packages:
        return {"ok": True, "installed": False, "lines": ["SYSDEPS SKIP", "Nessun pacchetto"]}

    missing = [package for package in packages if not is_debian_package_installed(package)]
    if not missing:
        return {"ok": True, "installed": False, "lines": ["SYSDEPS OK", "Gia presenti"]}

    if os.geteuid() != 0:
        return {"ok": False, "installed": False, "lines": ["SYSDEPS ERROR", "Serve root"]}

    env = os.environ.copy()
    env["DEBIAN_FRONTEND"] = "noninteractive"
    update = subprocess.run(
        ["apt-get", "update"],
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
        env=env,
    )
    if update.returncode != 0:
        return {"ok": False, "installed": False, "lines": ["APT UPDATE ERR"] + compact_git_output(update)[:4]}

    install = subprocess.run(
        ["apt-get", "install", "-y"] + missing,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
        env=env,
    )
    if install.returncode != 0:
        return {"ok": False, "installed": False, "lines": ["APT INSTALL ERR"] + compact_git_output(install)[:4]}

    return {
        "ok": True,
        "installed": True,
        "lines": ["SYSDEPS OK", "Installato " + ",".join(missing)[:11]],
    }


def run_repository_update(app_dir=UPDATE_APP_DIR):
    if not os.path.isdir(app_dir):
        return {"ok": False, "updated": False, "lines": ["UPDATE ERROR", "Repo not found", app_dir[-21:]]}

    before = run_git(app_dir, ["rev-parse", "HEAD"], timeout=15)
    if before.returncode != 0:
        lines = compact_git_output(before)
        return {"ok": False, "updated": False, "lines": ["UPDATE ERROR"] + lines[:4]}

    stash_saved = False
    dirty = run_git(app_dir, ["status", "--porcelain"], timeout=15)
    if dirty.returncode != 0:
        lines = compact_git_output(dirty)
        return {"ok": False, "updated": False, "lines": ["STATUS ERROR"] + lines[:4]}

    if dirty.stdout.strip():
        stash_name = f"oled-update-backup-{time.strftime('%Y%m%d-%H%M%S')}"
        stash = run_git(app_dir, ["stash", "push", "--include-untracked", "-m", stash_name], timeout=45)
        if stash.returncode != 0:
            lines = compact_git_output(stash)
            return {"ok": False, "updated": False, "lines": ["STASH ERROR"] + lines[:4]}
        stash_saved = True

    pull = run_git(app_dir, ["pull", "--ff-only"], timeout=UPDATE_GIT_TIMEOUT_SEC)
    if pull.returncode != 0:
        lines = compact_git_output(pull)
        prefix = ["PULL ERROR"]
        if stash_saved:
            prefix.append("Local saved stash")
        return {"ok": False, "updated": False, "lines": prefix + lines[:4]}

    after = run_git(app_dir, ["rev-parse", "HEAD"], timeout=15)
    before_sha = before.stdout.strip()
    after_sha = after.stdout.strip() if after.returncode == 0 else before_sha
    updated = bool(before_sha and after_sha and before_sha != after_sha)
    deps = run_oled_requirements_install()
    if not deps["ok"]:
        return {"ok": False, "updated": updated, "lines": deps["lines"] + ["K1 indietro"]}

    sysdeps = run_system_dependencies_install()
    if not sysdeps["ok"]:
        return {"ok": False, "updated": updated, "lines": sysdeps["lines"] + ["K1 indietro"]}

    deps_changed = bool(deps.get("installed") or sysdeps.get("installed"))

    if not updated:
        lines = ["NO UPDATE", "Gia aggiornato"]
        if stash_saved:
            lines.append("Local saved stash")
        lines.extend(deps["lines"][:2])
        lines.extend(sysdeps["lines"][:2])
        if deps_changed:
            lines.append("K2 reboot")
            return {"ok": True, "updated": True, "lines": lines}
        lines.append("K1 indietro")
        return {"ok": True, "updated": False, "lines": lines}

    changed = run_git(app_dir, ["diff", "--name-only", f"{before_sha}..{after_sha}"], timeout=20)
    files = [line.strip() for line in changed.stdout.splitlines() if line.strip()]
    summary = f"Files: {len(files)}" if files else "Files aggiornati"
    lines = ["UPDATED", summary, after_sha[:7]]
    if stash_saved:
        lines.append("Local saved stash")
    lines.extend(deps["lines"][:2])
    lines.extend(sysdeps["lines"][:2])
    lines.extend(["K2 reboot", "K1 indietro"])
    return {
        "ok": True,
        "updated": True,
        "lines": lines,
    }



class OledNetworkApp:
    network_fields = ["ip", "netmask", "gateway"]

    def __init__(self):
        serial = spi(port=SPI_PORT, device=SPI_DEVICE, gpio_DC=GPIO_DC, gpio_RST=GPIO_RST)
        self.device = sh1106(serial, width=WIDTH, height=HEIGHT, rotate=ROTATE)
        self.font = ImageFont.load_default()
        self.events = queue.Queue()
        self.running = True
        self.buttons = []

        self.ifaces = list_connected_ifaces()
        if PREFERRED_IFACE and PREFERRED_IFACE in self.ifaces:
            self.iface_index = self.ifaces.index(PREFERRED_IFACE)
        else:
            self.iface_index = 0
        self.iface = self.ifaces[self.iface_index]
        self.cfg = get_ipv4_config(self.iface)
        self.display_profile = load_kiosk_display_profile()
        self.spot_minutes = load_spot_inactivity_minutes()
        self.athlete_placeholder_enabled = load_athlete_placeholder_enabled()
        self.update_lines = ["UPDATE", "Press to start"]
        self.update_reboot_available = False
        self.update_running = False
        self.menu_selected = 0
        self.network_selected = 0
        self.editing = False
        self.ip_chars = ip_to_chars(self.cfg["ip"])
        self.netmask_chars = ip_to_chars(self.cfg["netmask"])
        self.gw_chars = ip_to_chars(self.cfg["gateway"])
        self.cursor = 0
        self.status = ""
        self.render_lock = threading.Lock()
        self.blink_on = True
        self.last_blink_at = time.monotonic()
        self.screen = "logo"
        self.last_activity_at = time.monotonic()
        self.hostname_label = os.getenv("OLED_HOSTNAME_LABEL", socket.gethostname().strip() or "FENCEWALL").upper()
        self.hostname_font = self.load_hostname_font()
        self.logo_image = self.load_logo_image()
        self.manual_qr_image = self.build_manual_qr_image()

        self.setup_buttons()

    def current_fields(self):
        if self.screen == "network":
            return self.network_fields
        if self.screen == "mode":
            return ["display_profile"]
        if self.screen == "spot":
            return ["spot_minutes"]
        if self.screen == "avatar":
            return ["athlete_placeholder"]
        return []

    def current_selected_index(self):
        if self.screen == "network":
            return self.network_selected
        return 0

    def current_selected_field(self):
        fields = self.current_fields()
        if not fields:
            return ""
        return fields[self.current_selected_index() % len(fields)]

    def load_logo_image(self):
        if not LOGO_PATH or not os.path.exists(LOGO_PATH):
            return None
        try:
            image = Image.open(LOGO_PATH).convert("1")
            image.thumbnail((WIDTH, HEIGHT), getattr(getattr(Image, "Resampling", Image), "LANCZOS"))
            canvas = Image.new("1", (WIDTH, HEIGHT), 0)
            x = max(0, (WIDTH - image.width) // 2)
            y = max(0, (HEIGHT - image.height) // 2)
            canvas.paste(image, (x, y))
            return canvas
        except Exception as exc:
            print(f"Logo load error: {exc}", file=sys.stderr)
            return None

    def load_hostname_font(self):
        try:
            return ImageFont.truetype(HOSTNAME_FONT_PATH, HOSTNAME_FONT_SIZE)
        except Exception as exc:
            print(f"Hostname font load error: {exc}", file=sys.stderr)
            return self.font

    def build_manual_qr_image(self):
        if not qrcode or not MANUAL_URL:
            return None
        try:
            qr = qrcode.QRCode(
                version=None,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=2,
                border=1,
            )
            qr.add_data(MANUAL_URL)
            qr.make(fit=True)
            qr_image = qr.make_image(fill_color="black", back_color="white").convert("L")
            resample_nearest = getattr(getattr(Image, "Resampling", Image), "NEAREST")
            qr_image = qr_image.resize((62, 62), resample_nearest)
            qr_image = qr_image.point(lambda pixel: 255 if pixel > 127 else 0, mode="1")
            canvas = Image.new("1", (WIDTH, HEIGHT), 0)
            canvas.paste(qr_image, (0, 1))
            return canvas
        except Exception as exc:
            print(f"Manual QR build error: {exc}", file=sys.stderr)
            return None

    def display_image(self, image):
        if FLIP_180:
            rotate_180 = getattr(getattr(Image, "Transpose", Image), "ROTATE_180")
            image = image.transpose(rotate_180)
        self.device.display(image)

    def normalize_input_event(self, event):
        if not INPUT_FLIP_180:
            return event
        return {
            "up": "down",
            "down": "up",
            "left": "right",
            "right": "left",
        }.get(event, event)

    def setup_buttons(self):
        for name, pin in PINS.items():
            if name == "k3":
                button = Button(pin, pull_up=True, bounce_time=0.08, hold_time=3)
                button.when_held = lambda event="k3_hold": self.events.put(event)
            else:
                button = Button(pin, pull_up=True, bounce_time=0.08)
                button.when_pressed = lambda event=name: self.events.put(event)
            self.buttons.append(button)

    def mark_activity(self):
        self.last_activity_at = time.monotonic()

    def reset_blink(self):
        self.blink_on = True
        self.last_blink_at = time.monotonic()

    def refresh_iface(self):
        self.ifaces = list_connected_ifaces()
        if not self.ifaces:
            self.ifaces = ["eth0"]
        self.iface_index %= len(self.ifaces)
        self.iface = self.ifaces[self.iface_index]
        self.cfg = get_ipv4_config(self.iface)
        self.display_profile = load_kiosk_display_profile()
        self.spot_minutes = load_spot_inactivity_minutes()
        self.athlete_placeholder_enabled = load_athlete_placeholder_enabled()
        self.ip_chars = ip_to_chars(self.cfg["ip"])
        self.netmask_chars = ip_to_chars(self.cfg["netmask"])
        self.gw_chars = ip_to_chars(self.cfg["gateway"])
        self.cursor = 0

    def chars_for_field(self, field):
        if field == "ip":
            return self.ip_chars
        if field == "netmask":
            return self.netmask_chars
        return self.gw_chars

    def toggle_display_profile(self, delta=1):
        current = normalize_display_profile(self.display_profile)
        current_index = DISPLAY_PROFILES.index(current) if current in DISPLAY_PROFILES else 0
        self.display_profile = DISPLAY_PROFILES[(current_index + delta) % len(DISPLAY_PROFILES)]

    def change_spot_minutes(self, delta):
        self.spot_minutes = clamp_spot_minutes(self.spot_minutes + delta)

    def toggle_athlete_placeholder(self):
        self.athlete_placeholder_enabled = not self.athlete_placeholder_enabled

    def display_value_for_field(self, field):
        if field == "display_profile":
            return display_profile_label(self.display_profile)
        if field == "spot_minutes":
            return f"{self.spot_minutes} min"
        if field == "athlete_placeholder":
            return "SI" if self.athlete_placeholder_enabled else "NO"
        if self.editing and self.screen == "network" and self.current_selected_field() == field:
            return "".join(self.chars_for_field(field))
        return str(self.cfg["gateway"] if field == "gateway" else self.cfg[field])

    def move_cursor(self, delta):
        field = self.current_selected_field()
        if field == "display_profile":
            self.toggle_display_profile(delta)
            return
        if field == "spot_minutes":
            self.change_spot_minutes(delta)
            return
        if field == "athlete_placeholder":
            self.toggle_athlete_placeholder()
            return
        chars = self.chars_for_field(field)
        positions = numeric_positions(chars)
        if not positions:
            return
        current = positions.index(self.cursor) if self.cursor in positions else 0
        self.cursor = positions[(current + delta) % len(positions)]

    def change_digit(self, delta):
        field = self.current_selected_field()
        if field == "display_profile":
            self.toggle_display_profile(delta)
            return
        if field == "spot_minutes":
            self.change_spot_minutes(delta)
            return
        if field == "athlete_placeholder":
            self.toggle_athlete_placeholder()
            return
        chars = self.chars_for_field(field)
        if self.cursor >= len(chars) or not chars[self.cursor].isdigit():
            positions = numeric_positions(chars)
            self.cursor = positions[0]
        value = (int(chars[self.cursor]) + delta) % 10
        chars[self.cursor] = str(value)
        if field == "ip":
            self.cfg["ip"] = chars_to_ip(chars)
        elif field == "netmask":
            self.cfg["netmask"] = chars_to_ip(chars)
        else:
            self.cfg["gateway"] = chars_to_ip(chars)

    def field_text_and_cursor(self, field_name, prefix, value):
        text = f"{prefix}{value}"
        if not self.editing or self.current_selected_field() != field_name:
            return text, None, False

        if field_name in ("display_profile", "spot_minutes", "athlete_placeholder"):
            return text, None, True

        cursor_offset = len(prefix) + self.cursor
        return text, cursor_offset, False

    def draw_line_with_cursor(self, draw, y, text, cursor_offset=None, blink_line=False):
        visible_text = text[:21]
        if blink_line and self.blink_on:
            draw.rectangle((0, y, WIDTH - 1, y + 9), fill=255)
            draw.text((0, y), visible_text, font=self.font, fill=0)
            return

        draw.text((0, y), visible_text, font=self.font, fill=255)
        if cursor_offset is None or not self.blink_on:
            return

        if cursor_offset < 0 or cursor_offset >= len(visible_text):
            return

        left = self.font.getlength(visible_text[:cursor_offset])
        char = visible_text[cursor_offset]
        char_width = max(6, int(self.font.getlength(char)) + 1)
        draw.rectangle((left, y, left + char_width, y + 8), fill=255)
        draw.text((left, y), char, font=self.font, fill=0)

    def enter_screen(self, screen):
        self.screen = screen
        self.editing = False
        self.status = ""
        self.cursor = 0
        self.reset_blink()

    def enter_selected_menu(self):
        item = MAIN_MENU_ITEMS[self.menu_selected]
        if item == "NETWORK":
            self.enter_screen("network")
        elif item == "MODE":
            self.enter_screen("mode")
        elif item == "SPOT":
            self.enter_screen("spot")
        elif item == "AVATAR ATLETA":
            self.enter_screen("avatar")
        elif item == "MANUALE":
            self.enter_screen("manual")
        elif item == "VERSIONE":
            self.enter_screen("version")
        elif item == "UPDATE":
            self.enter_screen("update")
            self.perform_update()
        elif item == "REBOOT":
            self.enter_screen("reboot")

    def save_current_screen(self):
        if self.screen == "network":
            self.save_network()
        elif self.screen == "mode":
            self.save_mode()
        elif self.screen == "spot":
            self.save_spot()
        elif self.screen == "avatar":
            self.save_avatar()
        elif self.screen == "update":
            self.save_update()
        elif self.screen == "reboot":
            self.save_reboot()

    def save_network(self):
        stop_animation = threading.Event()
        animation = threading.Thread(target=self.saving_animation, args=(stop_animation, "Saving network"), daemon=True)
        animation.start()
        try:
            apply_network(self.iface, self.cfg)
            self.status = "Saved. Re-reading..."
            self.refresh_iface()
            self.editing = False
            self.status = "Saved"
        except Exception as exc:
            self.status = f"ERR {exc}"[:21]
        finally:
            stop_animation.set()
            animation.join(timeout=1)
            self.mark_activity()

    def save_mode(self):
        stop_animation = threading.Event()
        animation = threading.Thread(target=self.saving_animation, args=(stop_animation, "Saving mode"), daemon=True)
        animation.start()
        reboot_needed = False
        target_profile = normalize_display_profile(self.display_profile)
        try:
            profile_changed = apply_kiosk_display_profile(target_profile)
            self.status = "Saved"
            if REBOOT_ON_PROFILE_SAVE:
                prepare_desktop_wallpaper_for_profile(target_profile)
                reboot_needed = True
                self.status = "Saved. Reboot..."
            elif profile_changed:
                restart_kiosk_service()
            self.display_profile = target_profile
            self.editing = False
        except Exception as exc:
            self.status = f"ERR {exc}"[:21]
        finally:
            stop_animation.set()
            animation.join(timeout=1)
            self.mark_activity()
        if reboot_needed:
            self.draw_message(["Mode saved", "Rebooting...", display_profile_label(self.display_profile)])
            threading.Thread(target=reboot_after_delay, args=(REBOOT_DELAY_SEC,), daemon=True).start()

    def save_spot(self):
        stop_animation = threading.Event()
        animation = threading.Thread(target=self.saving_animation, args=(stop_animation, "Saving spot"), daemon=True)
        animation.start()
        try:
            changed = apply_spot_inactivity_minutes(self.spot_minutes)
            self.spot_minutes = load_spot_inactivity_minutes()
            self.editing = False
            self.status = "Saved"
            if changed:
                restart_kiosk_service()
        except Exception as exc:
            self.status = f"ERR {exc}"[:21]
        finally:
            stop_animation.set()
            animation.join(timeout=1)
            self.mark_activity()

    def save_avatar(self):
        stop_animation = threading.Event()
        animation = threading.Thread(target=self.saving_animation, args=(stop_animation, "Saving avatar"), daemon=True)
        animation.start()
        try:
            changed = apply_athlete_placeholder_enabled(self.athlete_placeholder_enabled)
            self.athlete_placeholder_enabled = load_athlete_placeholder_enabled()
            self.editing = False
            self.status = "Saved"
            if changed:
                restart_kiosk_service()
        except Exception as exc:
            self.status = f"ERR {exc}"[:21]
        finally:
            stop_animation.set()
            animation.join(timeout=1)
            self.mark_activity()

    def perform_update(self):
        if self.update_running:
            return
        self.update_running = True
        self.update_reboot_available = False
        stop_animation = threading.Event()
        animation = threading.Thread(target=self.saving_animation, args=(stop_animation, "Git update"), daemon=True)
        animation.start()
        try:
            result = run_repository_update()
            self.update_lines = result["lines"][:6]
            self.update_reboot_available = bool(result["ok"] and result["updated"])
            self.status = "Updated" if self.update_reboot_available else ("No update" if result["ok"] else "Update ERR")
        except subprocess.TimeoutExpired:
            self.update_lines = ["PULL ERROR", "Timeout", "K1 indietro"]
            self.update_reboot_available = False
            self.status = "Update timeout"
        except Exception as exc:
            self.update_lines = ["UPDATE ERROR", str(exc)[:21], "K1 indietro"]
            self.update_reboot_available = False
            self.status = "Update ERR"
        finally:
            stop_animation.set()
            animation.join(timeout=1)
            self.update_running = False
            self.mark_activity()

    def save_update(self):
        if self.update_reboot_available:
            self.draw_message(["Rebooting...", "Update applied"])
            threading.Thread(target=reboot_after_delay, args=(REBOOT_DELAY_SEC,), daemon=True).start()
        else:
            self.perform_update()

    def save_reboot(self):
        self.draw_message(["Rebooting...", "Please wait"])
        threading.Thread(target=reboot_after_delay, args=(REBOOT_DELAY_SEC,), daemon=True).start()

    def handle_event(self, event):
        event = self.normalize_input_event(event)

        if self.screen == "logo":
            if event == "press":
                self.screen = "main_menu"
                self.status = ""
                self.mark_activity()
                self.reset_blink()
            return

        self.mark_activity()

        if event == "k1":
            if self.screen in ("network", "mode", "spot", "avatar", "manual", "version", "update", "reboot"):
                self.enter_screen("main_menu")
            elif self.screen == "main_menu":
                self.enter_screen("logo")
            return

        if self.screen == "main_menu":
            if event == "up":
                self.menu_selected = (self.menu_selected - 1) % len(MAIN_MENU_ITEMS)
            elif event == "down":
                self.menu_selected = (self.menu_selected + 1) % len(MAIN_MENU_ITEMS)
            elif event == "press":
                self.enter_selected_menu()
            return

        if event == "k2":
            self.save_current_screen()
            return

        if event == "k3_hold":
            if self.screen in ("manual", "version", "update", "reboot"):
                return
            self.editing = True
            if self.screen == "network":
                self.cfg["mode"] = "STATIC"
            self.status = "EDIT"
            self.reset_blink()
            return

        if event == "k3":
            return

        if event == "press":
            self.enter_screen("main_menu")
            return

        if not self.editing:
            if self.screen == "network":
                if event == "up":
                    self.network_selected = (self.network_selected - 1) % len(self.network_fields)
                elif event == "down":
                    self.network_selected = (self.network_selected + 1) % len(self.network_fields)
                elif event == "left":
                    self.move_cursor(-1)
                elif event == "right":
                    self.move_cursor(1)
            return

        step = 5 if self.screen == "spot" and event in ("left", "right") else 1
        if event == "up":
            self.change_digit(1)
        elif event == "down":
            self.change_digit(-1)
        elif event == "left":
            if self.screen == "spot":
                self.change_spot_minutes(-step)
            else:
                self.move_cursor(-1)
        elif event == "right":
            if self.screen == "spot":
                self.change_spot_minutes(step)
            else:
                self.move_cursor(1)

    def draw_logo(self):
        if self.logo_image:
            image = self.logo_image.copy()
        else:
            image = Image.new("1", (WIDTH, HEIGHT), 0)
            draw = ImageDraw.Draw(image)
            draw.text((0, 18), "FencingWallRack", font=self.font, fill=255)
            draw.text((0, 34), "Press joystick", font=self.font, fill=255)
        draw = ImageDraw.Draw(image)
        hostname = self.hostname_label[:21]
        hostname_font = self.hostname_font
        bbox = draw.textbbox((0, 0), hostname, font=hostname_font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = max(0, (WIDTH - text_width) // 2)
        y = HEIGHT - text_height - 2 - bbox[1]
        draw.rectangle((0, max(0, y + bbox[1] - 1), WIDTH - 1, HEIGHT - 1), fill=0)
        draw.text((x, y), hostname, font=hostname_font, fill=255)
        with self.render_lock:
            self.display_image(image)

    def draw_main_menu(self):
        image = Image.new("1", (WIDTH, HEIGHT), 0)
        draw = ImageDraw.Draw(image)
        draw.text((0, 0), "MENU", font=self.font, fill=255)
        visible_count = 3
        max_start = max(0, len(MAIN_MENU_ITEMS) - visible_count)
        start = min(max(0, self.menu_selected - visible_count + 1), max_start)
        visible_items = MAIN_MENU_ITEMS[start:start + visible_count]
        if start > 0:
            draw.text((116, 0), "^", font=self.font, fill=255)
        if start + visible_count < len(MAIN_MENU_ITEMS):
            draw.text((116, 54), "v", font=self.font, fill=255)
        for idx, item in enumerate(visible_items):
            item_index = start + idx
            selected = item_index == self.menu_selected
            prefix = ">" if selected else " "
            blink = selected and self.blink_on
            self.draw_line_with_cursor(draw, 16 + idx * 14, f"{prefix}{item}", None, blink)
        with self.render_lock:
            self.display_image(image)

    def draw_network(self):
        image = Image.new("1", (WIDTH, HEIGHT), 0)
        draw = ImageDraw.Draw(image)
        mode = "*" if self.editing else " "
        ip_line, ip_cursor, ip_blink = self.field_text_and_cursor("ip", f"{'>' if self.network_selected == 0 else ' '}IP ", self.display_value_for_field("ip"))
        netmask_line, netmask_cursor, netmask_blink = self.field_text_and_cursor("netmask", f"{'>' if self.network_selected == 1 else ' '}SN ", self.display_value_for_field("netmask"))
        gateway_line, gateway_cursor, gateway_blink = self.field_text_and_cursor("gateway", f"{'>' if self.network_selected == 2 else ' '}GW ", self.display_value_for_field("gateway"))
        lines = [
            (f"NET {self.iface} {self.cfg['mode']} {mode}", None, False),
            (ip_line, ip_cursor, ip_blink),
            (netmask_line, netmask_cursor, netmask_blink),
            (gateway_line, gateway_cursor, gateway_blink),
            (self.status, None, False),
        ]
        for idx, (line, cursor_offset, blink_line) in enumerate(lines):
            self.draw_line_with_cursor(draw, idx * 11, line, cursor_offset, blink_line)
        with self.render_lock:
            self.display_image(image)

    def draw_mode(self):
        image = Image.new("1", (WIDTH, HEIGHT), 0)
        draw = ImageDraw.Draw(image)
        mode = "*" if self.editing else " "
        line, cursor, blink = self.field_text_and_cursor("display_profile", ">OUT ", self.display_value_for_field("display_profile"))
        lines = [
            (f"MODE {mode}", None, False),
            (line, cursor, blink),
            ("K3 hold EDIT", None, False),
            ("K2 SAVE", None, False),
            (self.status, None, False),
        ]
        for idx, (text, cursor_offset, blink_line) in enumerate(lines):
            self.draw_line_with_cursor(draw, idx * 11, text, cursor_offset, blink_line)
        with self.render_lock:
            self.display_image(image)

    def draw_spot(self):
        image = Image.new("1", (WIDTH, HEIGHT), 0)
        draw = ImageDraw.Draw(image)
        mode = "*" if self.editing else " "
        line, cursor, blink = self.field_text_and_cursor("spot_minutes", ">AFTER ", self.display_value_for_field("spot_minutes"))
        lines = [
            (f"SPOT {mode}", None, False),
            (line, cursor, blink),
            (f"Range {SPOT_MIN_MINUTES}-{SPOT_MAX_MINUTES} min"[:21], None, False),
            ("K3 hold EDIT", None, False),
            ("K2 SAVE", None, False),
            (self.status, None, False),
        ]
        for idx, (text, cursor_offset, blink_line) in enumerate(lines):
            self.draw_line_with_cursor(draw, idx * 10, text, cursor_offset, blink_line)
        with self.render_lock:
            self.display_image(image)

    def draw_avatar(self):
        image = Image.new("1", (WIDTH, HEIGHT), 0)
        draw = ImageDraw.Draw(image)
        mode = "*" if self.editing else " "
        line, cursor, blink = self.field_text_and_cursor("athlete_placeholder", ">PLACEHOLDER ", self.display_value_for_field("athlete_placeholder"))
        lines = [
            (f"AVATAR ATLETA {mode}"[:21], None, False),
            (line, cursor, blink),
            ("SI = foto generica", None, False),
            ("NO = box vuoto", None, False),
            ("K3 hold EDIT", None, False),
            ("K2 SAVE", None, False),
            (self.status, None, False),
        ]
        for idx, (text, cursor_offset, blink_line) in enumerate(lines[:6]):
            self.draw_line_with_cursor(draw, idx * 10, text, cursor_offset, blink_line)
        with self.render_lock:
            self.display_image(image)

    def draw_manual(self):
        if self.manual_qr_image:
            image = self.manual_qr_image.copy()
            draw = ImageDraw.Draw(image)
            draw.text((68, 6), "MANUALE", font=self.font, fill=255)
            draw.text((68, 22), "Scan QR", font=self.font, fill=255)
            draw.text((68, 44), "K1 back", font=self.font, fill=255)
        else:
            image = Image.new("1", (WIDTH, HEIGHT), 0)
            draw = ImageDraw.Draw(image)
            lines = ["MANUALE", "QR non disp.", "Installa qrcode", "oppure URL:", MANUAL_URL[-21:], "K1 indietro"]
            for idx, line in enumerate(lines):
                self.draw_line_with_cursor(draw, idx * 10, line, None, False)
        with self.render_lock:
            self.display_image(image)

    def draw_version(self):
        image = Image.new("1", (WIDTH, HEIGHT), 0)
        draw = ImageDraw.Draw(image)
        version = load_firmware_version()
        revision = load_git_short_revision()
        hostname = socket.gethostname()[:21]
        lines = [
            "FIRMWARE",
            f"VERSIONE {version}"[:21],
            f"COMMIT {revision}"[:21],
            hostname,
            "K1 indietro",
        ]
        for idx, line in enumerate(lines):
            self.draw_line_with_cursor(draw, idx * 11, line, None, False)
        with self.render_lock:
            self.display_image(image)

    def draw_update(self):
        image = Image.new("1", (WIDTH, HEIGHT), 0)
        draw = ImageDraw.Draw(image)
        lines = self.update_lines or ["UPDATE", "K2 start"]
        for idx, line in enumerate(lines[:5]):
            self.draw_line_with_cursor(draw, idx * 10, line, None, False)
        footer = "K2 REBOOT" if self.update_reboot_available else "K2 UPDATE"
        self.draw_line_with_cursor(draw, 54, footer, None, False)
        with self.render_lock:
            self.display_image(image)

    def draw_reboot(self):
        image = Image.new("1", (WIDTH, HEIGHT), 0)
        draw = ImageDraw.Draw(image)
        lines = [
            "REBOOT",
            "K2 conferma",
            "K1 indietro",
            "",
            "Riavvia FENCEWALL",
        ]
        for idx, line in enumerate(lines):
            self.draw_line_with_cursor(draw, idx * 10, line, None, False)
        with self.render_lock:
            self.display_image(image)

    def draw(self):
        if self.screen == "logo":
            self.draw_logo()
        elif self.screen == "main_menu":
            self.draw_main_menu()
        elif self.screen == "network":
            self.draw_network()
        elif self.screen == "mode":
            self.draw_mode()
        elif self.screen == "spot":
            self.draw_spot()
        elif self.screen == "avatar":
            self.draw_avatar()
        elif self.screen == "manual":
            self.draw_manual()
        elif self.screen == "version":
            self.draw_version()
        elif self.screen == "update":
            self.draw_update()
        elif self.screen == "reboot":
            self.draw_reboot()

    def draw_message(self, lines):
        image = Image.new("1", (WIDTH, HEIGHT), 0)
        draw = ImageDraw.Draw(image)
        for idx, line in enumerate(lines[:6]):
            draw.text((0, idx * 10), line[:21], font=self.font, fill=255)
        with self.render_lock:
            self.display_image(image)

    def saving_animation(self, stop_event, title="Saving"):
        frames = ["|", "/", "-", "\\"]
        frame = 0
        while not stop_event.is_set():
            image = Image.new("1", (WIDTH, HEIGHT), 0)
            draw = ImageDraw.Draw(image)
            draw.text((0, 0), title[:21], font=self.font, fill=255)
            draw.text((0, 16), f"Please wait {frames[frame % len(frames)]}", font=self.font, fill=255)
            draw.text((0, 32), self.screen.upper()[:21], font=self.font, fill=255)
            draw.text((0, 48), self.iface[:21], font=self.font, fill=255)
            with self.render_lock:
                self.display_image(image)
            frame += 1
            stop_event.wait(0.2)

    def loop(self):
        self.draw()
        while self.running:
            try:
                event = self.events.get(timeout=0.2)
                self.handle_event(event)
                self.draw()
            except queue.Empty:
                should_blink = self.editing or self.screen == "main_menu"
                if should_blink and (time.monotonic() - self.last_blink_at) >= 0.5:
                    self.blink_on = not self.blink_on
                    self.last_blink_at = time.monotonic()
                    self.draw()
                elif self.screen != "logo" and not self.editing and (time.monotonic() - self.last_activity_at) >= LOGO_TIMEOUT_SEC:
                    self.screen = "logo"
                    self.draw()

def main():
    app = OledNetworkApp()

    def stop(_signum, _frame):
        app.running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    app.loop()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"oled_network_config error: {exc}", file=sys.stderr)
        raise
