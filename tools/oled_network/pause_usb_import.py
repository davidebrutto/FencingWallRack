"""Import pause media from a mounted USB stick without touching remote assets."""

import os
import shutil
import stat
import tempfile
import uuid
from pathlib import Path


MEDIA_EXTENSIONS = {".mp4", ".webm", ".mov", ".m4v", ".ogg", ".jpg", ".jpeg", ".png", ".webp"}
MOUNT_PREFIXES = ("/media/", "/run/media/", "/mnt/")


def mounted_usb_roots():
    roots = []
    with open("/proc/mounts", "r", encoding="utf-8") as mounts:
        for line in mounts:
            parts = line.split()
            if len(parts) < 2:
                continue
            mountpoint = parts[1].replace("\\040", " ")
            if mountpoint.startswith(MOUNT_PREFIXES) and os.path.ismount(mountpoint):
                roots.append(Path(mountpoint))
    return sorted(set(roots))


def find_pause_folder(roots=None):
    for root in mounted_usb_roots() if roots is None else roots:
        root = Path(root)
        if not root.is_dir():
            continue
        for entry in root.iterdir():
            if entry.name.casefold() == "pausa" and entry.is_dir() and not entry.is_symlink():
                return entry
    raise FileNotFoundError("USB: cartella PAUSA non trovata")


def media_files(folder):
    files = []
    for entry in Path(folder).iterdir():
        if entry.suffix.lower() not in MEDIA_EXTENSIONS or entry.is_symlink():
            continue
        if stat.S_ISREG(entry.stat(follow_symlinks=False).st_mode):
            files.append(entry)
    return sorted(files, key=lambda path: path.name.casefold())


def import_pause_media(destination, roots=None):
    source = find_pause_folder(roots)
    files = media_files(source)
    if not files:
        raise ValueError("PAUSA: nessun video o immagine")

    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    total_bytes = sum(file.stat().st_size for file in files)
    if shutil.disk_usage(destination.parent).free < total_bytes + 50 * 1024 * 1024:
        raise OSError("Spazio locale insufficiente")

    stage = Path(tempfile.mkdtemp(prefix=".pause-usb-stage-", dir=destination.parent))
    backup = destination.parent / f".pause-usb-backup-{uuid.uuid4().hex}"
    moved_old = False
    try:
        stage.chmod(0o755)
        for file in files:
            copied = stage / file.name
            shutil.copyfile(file, copied)
            copied.chmod(0o644)
        if destination.exists():
            os.replace(destination, backup)
            moved_old = True
        try:
            os.replace(stage, destination)
        except OSError:
            if moved_old:
                os.replace(backup, destination)
                moved_old = False
            raise
        if moved_old:
            shutil.rmtree(backup)
        return len(files)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
