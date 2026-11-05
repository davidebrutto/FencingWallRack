"""Isolated NetworkManager Wi-Fi trial; never modifies wired profiles."""

import os
import subprocess
import tempfile


PROFILE = "FENCEWALL-BLE-TEST"
IFACE = "wlan0"


class NetworkStepError(RuntimeError):
    """Safe-to-display failure without command arguments or credentials."""


def _run(args, timeout=20, step="nmcli"):
    try:
        return subprocess.run(args, check=True, text=True, capture_output=True, timeout=timeout)
    except subprocess.CalledProcessError as exc:
        raise NetworkStepError(f"{step}: nmcli codice {exc.returncode}") from None
    except subprocess.TimeoutExpired:
        raise NetworkStepError(f"{step}: timeout") from None


def validate(ssid, password):
    if not ssid or len(ssid.encode("utf-8")) > 32 or any(c in ssid for c in "\r\n\0"):
        raise ValueError("SSID non valido (massimo 32 byte)")
    if not 8 <= len(password.encode("utf-8")) <= 63 or any(c in password for c in "\r\n\0"):
        raise ValueError("Password WPA2 non valida (8-63 byte)")


def connect(ssid, password):
    validate(ssid, password)
    # Refuse to alter a pre-existing profile, including one from a previous trial.
    existing = _run(["nmcli", "-g", "GENERAL.STATE", "device", "show", IFACE],
                    step="verifica wlan0").stdout
    if not existing:
        raise NetworkStepError("Interfaccia wlan0 non disponibile")
    profiles = _run(["nmcli", "-g", "NAME", "connection", "show"],
                    step="elenco profili").stdout.splitlines()
    if PROFILE in profiles:
        raise NetworkStepError("Profilo di prova gia presente; rimuoverlo prima")

    _run(["nmcli", "connection", "add", "save", "yes", "type", "wifi", "ifname", IFACE,
          "con-name", PROFILE, "ssid", ssid, "connection.autoconnect", "no",
          "wifi-sec.key-mgmt", "wpa-psk", "ipv4.method", "auto", "ipv6.method", "auto",
          "ipv4.never-default", "yes", "ipv6.never-default", "yes"],
         step="creazione profilo")
    fd, path = tempfile.mkstemp(prefix="fencewall-wifi-", dir="/run")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write("802-11-wireless-security.psk:" + password + "\n")
        # The password is only in a root-readable temporary file, never argv or logs.
        _run(["nmcli", "--wait", "45", "connection", "up", "id", PROFILE,
              "ifname", IFACE, "passwd-file", path], timeout=55,
             step="attivazione Wi-Fi")
    finally:
        os.unlink(path)


def remove_trial_profile():
    _run(["nmcli", "connection", "delete", "id", PROFILE])
