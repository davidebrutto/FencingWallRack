"""Remove the old network wait from already-installed OLED service units."""

import os
import stat
import subprocess
import tempfile


UNIT_PATH = "/etc/systemd/system/fencingwallrack-oled-network.service"


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
