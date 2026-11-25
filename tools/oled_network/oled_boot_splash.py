#!/usr/bin/env python3
"""Show a brief OLED boot indicator without waiting for the full menu service."""

import os
import subprocess
import sys
import time


def env_int(name, default):
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def menu_is_active():
    return subprocess.run(
        ["systemctl", "is-active", "--quiet", "fencingwallrack-oled-network.service"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0


def main():
    port = env_int("OLED_SPI_PORT", 0)
    spi_device = env_int("OLED_SPI_DEVICE", 0)
    spi_path = f"/dev/spidev{port}.{spi_device}"
    deadline = time.monotonic() + 6
    while not os.path.exists(spi_path) and time.monotonic() < deadline:
        time.sleep(0.15)
    if not os.path.exists(spi_path):
        print(f"OLED early splash: {spi_path} not ready", file=sys.stderr)
        return 0
    if menu_is_active():
        return 0

    from luma.core.interface.serial import spi
    from luma.oled.device import sh1106
    from PIL import Image, ImageDraw, ImageFont

    serial = spi(
        port=port,
        device=spi_device,
        gpio_DC=env_int("OLED_GPIO_DC", 24),
        gpio_RST=env_int("OLED_GPIO_RST", 25),
    )
    width = env_int("OLED_WIDTH", 128)
    height = env_int("OLED_HEIGHT", 64)
    display = sh1106(
        serial,
        width=width,
        height=height,
        rotate=env_int("OLED_ROTATE", 0),
    )

    image = Image.new("1", (width, height), 0)
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    draw.text((8, 14), "FENCEWALL", font=font, fill=255)
    draw.text((8, 36), "AVVIO...", font=font, fill=255)
    if os.getenv("OLED_FLIP_180", "1").strip().lower() not in ("0", "false", "no", "off"):
        rotate_180 = getattr(getattr(Image, "Transpose", Image), "ROTATE_180")
        image = image.transpose(rotate_180)

    if not menu_is_active():
        display.display(image)
        print("OLED early splash displayed")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"OLED early splash error: {exc}", file=sys.stderr)
        sys.exit(1)
