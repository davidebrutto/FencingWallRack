"""Install repository pause images once, using the same pipeline as OLED USB import."""

import hashlib
import os
from pathlib import Path

from pause_usb_import import import_pause_media, media_files


APP_DIR = Path(__file__).resolve().parents[2]
BUNDLE_ROOT = APP_DIR / "static" / "pause-bundle"
PAUSE_DIR = APP_DIR / "static" / "pause-usb"
STATE_FILE = APP_DIR / "static" / ".pause-bundle-sha256"


def bundle_digest(files):
    digest = hashlib.sha256()
    for file in files:
        digest.update(file.name.encode("utf-8"))
        digest.update(b"\0")
        with file.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def install_bundle(bundle_root=BUNDLE_ROOT, pause_dir=PAUSE_DIR, state_file=STATE_FILE):
    files = media_files(bundle_root / "PAUSA")
    if not files:
        return 0
    current_digest = bundle_digest(files)
    if (
        state_file.exists()
        and state_file.read_text(encoding="ascii").strip() == current_digest
        and pause_dir.is_dir()
        and media_files(pause_dir)
    ):
        print("Pacchetto pausa gia installato", flush=True)
        return 0

    count = import_pause_media(pause_dir, roots=[bundle_root])
    temporary_state = state_file.with_name(f"{state_file.name}.{os.getpid()}.tmp")
    try:
        temporary_state.write_text(f"{current_digest}\n", encoding="ascii")
        os.replace(temporary_state, state_file)
    finally:
        temporary_state.unlink(missing_ok=True)
    print(f"Pacchetto pausa installato: {count} immagini", flush=True)
    return count


if __name__ == "__main__":
    install_bundle()
