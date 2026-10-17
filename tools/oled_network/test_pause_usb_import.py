import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pause_usb_import import import_pause_media


class PauseUsbImportTests(unittest.TestCase):
    def test_replaces_previous_cache_with_images_and_videos(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "stick" / "PAUSA"
            source.mkdir(parents=True)
            (source / "01-intro.mp4").write_bytes(b"video")
            (source / "02-photo.jpg").write_bytes(b"image")
            (source / "notes.txt").write_bytes(b"ignored")
            destination = root / "static" / "pause-usb"
            destination.mkdir(parents=True)
            (destination / "old.mp4").write_bytes(b"old")

            self.assertEqual(import_pause_media(destination, [source.parent]), 2)
            self.assertEqual(sorted(path.name for path in destination.iterdir()), ["01-intro.mp4", "02-photo.jpg"])
            self.assertEqual((destination / "02-photo.jpg").read_bytes(), b"image")

    def test_empty_folder_keeps_previous_cache(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "stick" / "PAUSA"
            source.mkdir(parents=True)
            destination = root / "pause-usb"
            destination.mkdir()
            (destination / "old.mp4").write_bytes(b"old")

            with self.assertRaises(ValueError):
                import_pause_media(destination, [source.parent])
            self.assertEqual((destination / "old.mp4").read_bytes(), b"old")

    def test_copy_failure_keeps_previous_cache(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "stick" / "PAUSA"
            source.mkdir(parents=True)
            (source / "new.mp4").write_bytes(b"video")
            destination = root / "pause-usb"
            destination.mkdir()
            (destination / "old.mp4").write_bytes(b"old")

            with patch("pause_usb_import.shutil.copyfile", side_effect=OSError("copy failed")):
                with self.assertRaises(OSError):
                    import_pause_media(destination, [source.parent])
            self.assertEqual((destination / "old.mp4").read_bytes(), b"old")


if __name__ == "__main__":
    unittest.main()
