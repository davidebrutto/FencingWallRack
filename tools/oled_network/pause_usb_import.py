"""Import pause media from a mounted USB stick without touching remote assets."""

import os
import shutil
import stat
import subprocess
import tempfile
import uuid
from pathlib import Path


MEDIA_EXTENSIONS = {".mp4", ".webm", ".mov", ".m4v", ".ogg", ".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".m4v", ".ogg"}
MOUNT_PREFIXES = ("/media/", "/run/media/", "/mnt/")
VIDEO_FILTER = "scale=w='min(768,iw)':h='min(432,ih)':force_original_aspect_ratio=decrease,scale=trunc(iw/2)*2:trunc(ih/2)*2"


def optimize_video(source, destination):
    command = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(source),
        "-vf", VIDEO_FILTER, "-map", "0:v:0", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        "-c:a", "aac", "-b:a", "128k", "-ac", "2", str(destination),
    ]
    try:
        subprocess.run(command, capture_output=True, text=True, check=True, timeout=900)
    except FileNotFoundError as exc:
        raise RuntimeError("ffmpeg mancante") from exc
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"Conversione video fallita: {source.name}") from exc


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
        used_names = set()
        original_mp4_names = {file.name for file in files if file.suffix.lower() == ".mp4"}
        for file in files:
            if file.suffix.lower() in VIDEO_EXTENSIONS:
                output_name = file.name if file.suffix.lower() == ".mp4" else f"{file.stem}.mp4"
                if output_name in used_names or (file.suffix.lower() != ".mp4" and output_name in original_mp4_names):
                    output_name = f"{file.stem}-{file.suffix[1:].lower()}.mp4"
                suffix = 2
                while output_name in used_names:
                    output_name = f"{file.stem}-{file.suffix[1:].lower()}-{suffix}.mp4"
                    suffix += 1
                copied = stage / output_name
                optimize_video(file, copied)
            else:
                copied = stage / file.name
                shutil.copyfile(file, copied)
            copied.chmod(0o644)
            used_names.add(copied.name)
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
