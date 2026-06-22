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


WIDTH = int(os.getenv("OLED_WIDTH", "128"))
HEIGHT = int(os.getenv("OLED_HEIGHT", "64"))
ROTATE = int(os.getenv("OLED_ROTATE", "0"))
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
PREFERRED_IFACE = os.getenv("NET_IFACE", "").strip()


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
        if dev != "lo" and typ in ("ethernet", "wifi") and state == "connected":
            result.append(dev)
    if result:
        return result

    route = cmd_ok(["ip", "route", "show", "default"])
    fallback = []
    for match in re.finditer(r"\bdev\s+(\S+)", route):
        dev = match.group(1)
        if dev != "lo" and dev not in fallback:
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

    return {"ip": ip, "prefix": prefix, "gateway": gateway, "mode": mode}


def valid_ip(value):
    try:
        ipaddress.IPv4Address(value)
        return True
    except ValueError:
        return False


def apply_network(iface, cfg):
    conn = active_connection_for_iface(iface)
    if not conn:
        raise RuntimeError(f"No active NetworkManager connection for {iface}")

    if cfg["mode"] == "DHCP":
        run(["nmcli", "con", "mod", conn, "ipv4.method", "auto", "ipv4.addresses", "", "ipv4.gateway", "", "ipv4.dns", ""])
    else:
        if not valid_ip(cfg["ip"]) or not valid_ip(cfg["gateway"]):
            raise RuntimeError("IP or gateway is not valid")
        if not (1 <= int(cfg["prefix"]) <= 32):
            raise RuntimeError("Subnet prefix must be 1-32")
        run([
            "nmcli", "con", "mod", conn,
            "ipv4.method", "manual",
            "ipv4.addresses", f'{cfg["ip"]}/{cfg["prefix"]}',
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


class OledNetworkApp:
    fields = ["ip", "prefix", "gateway"]

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
        self.selected = 0
        self.editing = False
        self.ip_chars = ip_to_chars(self.cfg["ip"])
        self.gw_chars = ip_to_chars(self.cfg["gateway"])
        self.cursor = 0
        self.status = "K1 save K2 mode K3 iface"
        self.render_lock = threading.Lock()
        self.blink_on = True
        self.last_blink_at = time.monotonic()

        self.setup_buttons()

    def setup_buttons(self):
        for name, pin in PINS.items():
            button = Button(pin, pull_up=True, bounce_time=0.08)
            button.when_pressed = lambda event=name: self.events.put(event)
            self.buttons.append(button)

    def refresh_iface(self):
        self.ifaces = list_connected_ifaces()
        if not self.ifaces:
            self.ifaces = ["eth0"]
        self.iface_index %= len(self.ifaces)
        self.iface = self.ifaces[self.iface_index]
        self.cfg = get_ipv4_config(self.iface)
        self.ip_chars = ip_to_chars(self.cfg["ip"])
        self.gw_chars = ip_to_chars(self.cfg["gateway"])
        self.cursor = 0

    def move_cursor(self, delta):
        field = self.fields[self.selected]
        if field == "prefix":
            self.cfg["prefix"] = max(1, min(32, self.cfg["prefix"] + delta))
            return
        chars = self.ip_chars if field == "ip" else self.gw_chars
        positions = numeric_positions(chars)
        if not positions:
            return
        current = positions.index(self.cursor) if self.cursor in positions else 0
        self.cursor = positions[(current + delta) % len(positions)]

    def change_digit(self, delta):
        field = self.fields[self.selected]
        if field == "prefix":
            self.cfg["prefix"] = max(1, min(32, self.cfg["prefix"] + delta))
            return
        chars = self.ip_chars if field == "ip" else self.gw_chars
        if self.cursor >= len(chars) or not chars[self.cursor].isdigit():
            positions = numeric_positions(chars)
            self.cursor = positions[0]
        value = (int(chars[self.cursor]) + delta) % 10
        chars[self.cursor] = str(value)
        if field == "ip":
            self.cfg["ip"] = chars_to_ip(chars)
        else:
            self.cfg["gateway"] = chars_to_ip(chars)

    def field_text_and_cursor(self, field_name, prefix, value):
        text = f"{prefix}{value}"
        if not self.editing or self.fields[self.selected] != field_name:
            return text, None

        if field_name == "prefix":
            cursor_offset = len(prefix) + max(0, len(str(value)) - 1)
        else:
            cursor_offset = len(prefix) + self.cursor
        return text, cursor_offset

    def draw_line_with_cursor(self, draw, y, text, cursor_offset=None):
        draw.text((0, y), text[:21], font=self.font, fill=255)
        if cursor_offset is None or not self.blink_on:
            return

        visible_text = text[:21]
        if cursor_offset < 0 or cursor_offset >= len(visible_text):
            return

        left = self.font.getlength(visible_text[:cursor_offset])
        char = visible_text[cursor_offset]
        char_width = max(6, int(self.font.getlength(char)) + 1)
        draw.rectangle((left, y, left + char_width, y + 8), fill=255)
        draw.text((left, y), char, font=self.font, fill=0)

    def handle_event(self, event):
        if event == "k1":
            stop_animation = threading.Event()
            animation = threading.Thread(target=self.saving_animation, args=(stop_animation,), daemon=True)
            animation.start()
            try:
                apply_network(self.iface, self.cfg)
                self.status = "Saved. Re-reading..."
                self.refresh_iface()
                self.status = "Saved"
            except Exception as exc:
                self.status = f"ERR {exc}"[:21]
            finally:
                stop_animation.set()
                animation.join(timeout=1)
            return

        if event == "k2":
            self.cfg["mode"] = "STATIC" if self.cfg["mode"] == "DHCP" else "DHCP"
            self.status = f"Mode {self.cfg['mode']}"
            return

        if event == "k3":
            self.iface_index = (self.iface_index + 1) % max(1, len(self.ifaces))
            self.refresh_iface()
            self.status = f"Iface {self.iface}"
            return

        if event == "press":
            self.editing = not self.editing
            self.status = "EDIT" if self.editing else "SELECT"
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

    def draw(self):
        image = Image.new("1", (WIDTH, HEIGHT), 0)
        draw = ImageDraw.Draw(image)
        mode = "*" if self.editing else " "
        ip_line, ip_cursor = self.field_text_and_cursor("ip", f"{'>' if self.selected == 0 else ' '}IP ", self.cfg["ip"])
        prefix_line, prefix_cursor = self.field_text_and_cursor("prefix", f"{'>' if self.selected == 1 else ' '}SN /", self.cfg["prefix"])
        gateway_line, gateway_cursor = self.field_text_and_cursor("gateway", f"{'>' if self.selected == 2 else ' '}GW ", self.cfg["gateway"])
        lines = [
            (f"{self.iface} {self.cfg['mode']} {mode}", None),
            (ip_line, ip_cursor),
            (prefix_line, prefix_cursor),
            (gateway_line, gateway_cursor),
            ("K1 Save K2 Mode", None),
            ((self.status or "")[:21], None),
        ]
        for idx, (line, cursor_offset) in enumerate(lines):
            self.draw_line_with_cursor(draw, idx * 10, line, cursor_offset)
        with self.render_lock:
            self.device.display(image)

    def saving_animation(self, stop_event):
        frames = ["|", "/", "-", "\\"]
        frame = 0
        while not stop_event.is_set():
            image = Image.new("1", (WIDTH, HEIGHT), 0)
            draw = ImageDraw.Draw(image)
            draw.text((0, 0), "Saving network", font=self.font, fill=255)
            draw.text((0, 16), f"Please wait {frames[frame % len(frames)]}", font=self.font, fill=255)
            draw.text((0, 32), self.iface[:21], font=self.font, fill=255)
            draw.text((0, 48), f"{self.cfg['ip']}/{self.cfg['prefix']}"[:21], font=self.font, fill=255)
            with self.render_lock:
                self.device.display(image)
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
