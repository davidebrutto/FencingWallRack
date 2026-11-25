import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from oled_early_boot import ensure_early_oled_service


class EarlyOledServiceTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        root = Path(self.temp_dir.name)
        self.unit = root / "oled.service"

    def test_installs_once_for_old_network_dependent_unit(self):
        self.unit.write_text("[Unit]\nAfter=network-online.target\nWants=network-online.target\n[Service]\nExecStart=/custom/app\n")
        with patch.object(os, "geteuid", return_value=0), patch("oled_early_boot.subprocess.run") as run:
            self.assertTrue(ensure_early_oled_service(str(self.unit)))
            self.assertEqual(self.unit.read_text(), "[Unit]\nAfter=local-fs.target\n[Service]\nExecStart=/custom/app\n")
            self.assertFalse(ensure_early_oled_service(str(self.unit)))
            run.assert_called_once_with(["systemctl", "daemon-reload"], check=True, timeout=15)

    def test_leaves_unit_without_network_wait_untouched(self):
        self.unit.write_text("[Unit]\nAfter=local-fs.target\n")
        with patch.object(os, "geteuid", return_value=0), patch("oled_early_boot.subprocess.run") as run:
            self.assertFalse(ensure_early_oled_service(str(self.unit)))
            self.assertEqual(self.unit.read_text(), "[Unit]\nAfter=local-fs.target\n")
            run.assert_not_called()

    def test_non_root_does_not_change_service(self):
        self.unit.write_text("[Unit]\nAfter=network-online.target\n")
        with patch.object(os, "geteuid", return_value=1000):
            self.assertFalse(ensure_early_oled_service(str(self.unit)))
            self.assertEqual(self.unit.read_text(), "[Unit]\nAfter=network-online.target\n")


if __name__ == "__main__":
    unittest.main()
