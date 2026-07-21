#!/usr/bin/env python3
import ipaddress
import os
import queue
import re
import signal
import subprocess
import sys
import threading
import time

from gpiozero import Button
from luma.core.interface.serial import spi
from luma.oled.device import sh1106
from PIL import Image, ImageDraw, ImageFont


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WIDTH = int(os.getenv("OLED_WIDTH", "128"))
HEIGHT = int(os.getenv("OLED_HEIGHT", "64"))
ROTATE = int(os.getenv("OLED_ROTATE", "0"))
FLIP_180 = os.getenv("OLED_FLIP_180", "1").strip().lower() not in ("0", "false", "no", "off")
INPUT_FLIP_180 = os.getenv("OLED_INPUT_FLIP_180", "1" if FLIP_180 else "0").strip().lower() not in ("0", "false", "no", "off")
LOGO_PATH = os.getenv("OLED_LOGO_PATH", os.path.join(SCRIPT_DIR, "logo.png"))
LOGO_TIMEOUT_SEC = float(os.getenv("OLED_LOGO_TIMEOUT_SEC", "10"))
KIOSK_ENV_PATH = os.getenv("KIOSK_ENV_PATH", "/etc/default/fencingwallrack-kiosk")
KIOSK_SERVICE = os.getenv("KIOSK_SERVICE", "fencingwallrack-kiosk.service")
RESTART_KIOSK_ON_PROFILE_SAVE = os.getenv("OLED_RESTART_KIOSK_ON_PROFILE_SAVE", "1").strip().lower() not in ("0", "false", "no", "off")
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
PREFERRED_IFACE = os.getenv("NET_IFACE", "").strip()
DISPLAY_PROFILES = ["ledwall", "sottopedana"]


def run(cmd, check=True):
    return subprocess.run(cmd, text=True, capture_output=True, check=check)


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


def restart_kiosk_service():
    if not RESTART_KIOSK_ON_PROFILE_SAVE:
        return
    run(["systemctl", "restart", KIOSK_SERVICE])


class OledNetworkApp:
    fields = ["display_profile", "ip", "netmask", "gateway"]

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
        self.selected = 0
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
        self.logo_image = self.load_logo_image()

        self.setup_buttons()

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

    def refresh_iface(self):
        self.ifaces = list_connected_ifaces()
        if not self.ifaces:
            self.ifaces = ["eth0"]
        self.iface_index %= len(self.ifaces)
        self.iface = self.ifaces[self.iface_index]
        self.cfg = get_ipv4_config(self.iface)
        self.display_profile = load_kiosk_display_profile()
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

    def display_value_for_field(self, field):
        if field == "display_profile":
            return display_profile_label(self.display_profile)
        if self.editing and self.fields[self.selected] == field:
            return "".join(self.chars_for_field(field))
        return str(self.cfg["gateway"] if field == "gateway" else self.cfg[field])

    def move_cursor(self, delta):
        field = self.fields[self.selected]
        if field == "display_profile":
            self.toggle_display_profile(delta)
            return
        chars = self.chars_for_field(field)
        positions = numeric_positions(chars)
        if not positions:
            return
        current = positions.index(self.cursor) if self.cursor in positions else 0
        self.cursor = positions[(current + delta) % len(positions)]

    def change_digit(self, delta):
        field = self.fields[self.selected]
        if field == "display_profile":
            self.toggle_display_profile(delta)
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
        if not self.editing or self.fields[self.selected] != field_name:
            return text, None, False

        if field_name == "display_profile":
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

    def handle_event(self, event):
        event = self.normalize_input_event(event)

        if self.screen == "logo":
            if event == "press":
                self.screen = "config"
                self.mark_activity()
            return

        self.mark_activity()

        if event == "k2":
            stop_animation = threading.Event()
            animation = threading.Thread(target=self.saving_animation, args=(stop_animation,), daemon=True)
            animation.start()
            try:
                apply_network(self.iface, self.cfg)
                profile_changed = apply_kiosk_display_profile(self.display_profile)
                self.status = "Saved. Re-reading..."
                self.refresh_iface()
                if profile_changed:
                    restart_kiosk_service()
                self.editing = False
                self.status = "Saved"
            except Exception as exc:
                self.status = f"ERR {exc}"[:21]
            finally:
                stop_animation.set()
                animation.join(timeout=1)
                self.mark_activity()
            return

        if event == "k3_hold":
            self.editing = True
            self.cfg["mode"] = "STATIC"
            self.status = "EDIT"
            return

        if event in ("k1", "k3"):
            return

        if event == "press":
            return

        if not self.editing:
            if event == "up":
                self.selected = (self.selected - 1) % len(self.fields)
            elif event == "down":
                self.selected = (self.selected + 1) % len(self.fields)
            elif event == "left":
                self.move_cursor(-1)
            elif event == "right":
                self.move_cursor(1)
            return

        if event == "up":
            self.change_digit(1)
        elif event == "down":
            self.change_digit(-1)
        elif event == "left":
            self.move_cursor(-1)
        elif event == "right":
            self.move_cursor(1)

    def draw_logo(self):
        if self.logo_image:
            image = self.logo_image.copy()
        else:
            image = Image.new("1", (WIDTH, HEIGHT), 0)
            draw = ImageDraw.Draw(image)
            draw.text((0, 18), "FencingWallRack", font=self.font, fill=255)
            draw.text((0, 34), "Press joystick", font=self.font, fill=255)
        with self.render_lock:
            self.display_image(image)

    def draw_config(self):
        image = Image.new("1", (WIDTH, HEIGHT), 0)
        draw = ImageDraw.Draw(image)
        mode = "*" if self.editing else " "
        profile_line, profile_cursor, profile_blink = self.field_text_and_cursor("display_profile", f"{'>' if self.selected == 0 else ' '}OUT ", self.display_value_for_field("display_profile"))
        ip_line, ip_cursor, ip_blink = self.field_text_and_cursor("ip", f"{'>' if self.selected == 1 else ' '}IP ", self.display_value_for_field("ip"))
        netmask_line, netmask_cursor, netmask_blink = self.field_text_and_cursor("netmask", f"{'>' if self.selected == 2 else ' '}SN ", self.display_value_for_field("netmask"))
        gateway_line, gateway_cursor, gateway_blink = self.field_text_and_cursor("gateway", f"{'>' if self.selected == 3 else ' '}GW ", self.display_value_for_field("gateway"))
        lines = [
            (f"{self.iface} {self.cfg['mode']} {mode}", None, False),
            (profile_line, profile_cursor, profile_blink),
            (ip_line, ip_cursor, ip_blink),
            (netmask_line, netmask_cursor, netmask_blink),
            (gateway_line, gateway_cursor, gateway_blink),
        ]
        for idx, (line, cursor_offset, blink_line) in enumerate(lines):
            self.draw_line_with_cursor(draw, idx * 10, line, cursor_offset, blink_line)
        with self.render_lock:
            self.display_image(image)

    def draw(self):
        if self.screen == "logo":
            self.draw_logo()
        else:
            self.draw_config()

    def saving_animation(self, stop_event):
        frames = ["|", "/", "-", "\\"]
        frame = 0
        while not stop_event.is_set():
            image = Image.new("1", (WIDTH, HEIGHT), 0)
            draw = ImageDraw.Draw(image)
            draw.text((0, 0), "Saving network", font=self.font, fill=255)
            draw.text((0, 16), f"Please wait {frames[frame % len(frames)]}", font=self.font, fill=255)
            draw.text((0, 32), self.iface[:21], font=self.font, fill=255)
            draw.text((0, 48), f"SN {self.cfg['netmask']}"[:21], font=self.font, fill=255)
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
                if self.editing and (time.monotonic() - self.last_blink_at) >= 0.5:
                    self.blink_on = not self.blink_on
                    self.last_blink_at = time.monotonic()
                    self.draw()
                elif self.screen == "config" and not self.editing and (time.monotonic() - self.last_activity_at) >= LOGO_TIMEOUT_SEC:
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
