"""Remove the old network wait from already-installed OLED service units."""

import os
import stat
import subprocess
import tempfile


UNIT_PATH = "/etc/systemd/system/fencingwallrack-oled-network.service"
EARLY_UNIT_SOURCE = os.path.join(os.path.dirname(__file__), "fencingwallrack-oled-early-splash.service")
EARLY_UNIT_PATH = "/etc/systemd/system/fencingwallrack-oled-early-splash.service"
EARLY_UNIT_LINK = "/etc/systemd/system/basic.target.wants/fencingwallrack-oled-early-splash.service"


def ensure_early_oled_service(unit_path=UNIT_PATH):
    if os.geteuid() != 0 or os.path.islink(unit_path):
        return False

    try:
        with open(unit_path, "r", encoding="utf-8") as file:
            unit = file.read()
    except FileNotFoundError:
        return False
    old_ordering = "After=network-online.target\n"
    old_wants = "Wants=network-online.target\n"
    if old_ordering not in unit or old_wants not in unit:
        return False

    updated = unit.replace(old_ordering, "After=local-fs.target\n", 1).replace(old_wants, "", 1)
    directory = os.path.dirname(unit_path)
    fd, temporary_path = tempfile.mkstemp(prefix=".fencingwallrack-oled-", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            file.write(updated)
        os.chmod(temporary_path, stat.S_IMODE(os.stat(unit_path).st_mode))
        os.replace(temporary_path, unit_path)
    finally:
        if os.path.exists(temporary_path):
            os.unlink(temporary_path)

    subprocess.run(["systemctl", "daemon-reload"], check=True, timeout=15)
    return True


def ensure_early_splash_service(
    source_path=EARLY_UNIT_SOURCE,
    unit_path=EARLY_UNIT_PATH,
    enabled_link=EARLY_UNIT_LINK,
):
    if os.geteuid() != 0 or os.path.islink(unit_path):
        return False

    with open(source_path, "r", encoding="utf-8") as file:
        desired = file.read()
    try:
        with open(unit_path, "r", encoding="utf-8") as file:
            current = file.read()
    except FileNotFoundError:
        current = ""
    if current and not current.startswith("# Managed by FENCEWALL OLED\n"):
        raise RuntimeError(f"Refusing to replace custom unit: {unit_path}")

    changed = current != desired
    if changed:
        fd, temporary_path = tempfile.mkstemp(prefix=".fencingwallrack-oled-splash-", dir=os.path.dirname(unit_path))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                file.write(desired)
            os.chmod(temporary_path, 0o644)
            os.replace(temporary_path, unit_path)
        finally:
            if os.path.exists(temporary_path):
                os.unlink(temporary_path)
        subprocess.run(["systemctl", "daemon-reload"], check=True, timeout=15)

    if not os.path.islink(enabled_link):
        subprocess.run(["systemctl", "enable", os.path.basename(unit_path)], check=True, timeout=15)
        return True
    return changed
