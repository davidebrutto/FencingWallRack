import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import oled_boot_splash
from oled_early_boot import ensure_early_oled_service, ensure_early_splash_service


class EarlyOledServiceTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        root = Path(self.temp_dir.name)
        self.unit = root / "oled.service"
        self.early_source = root / "early-source.service"
        self.early_unit = root / "early-installed.service"
        self.early_link = root / "basic.target.wants" / "early-installed.service"

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

    def test_early_splash_is_installed_and_enabled_once(self):
        content = "# Managed by FENCEWALL OLED\n[Unit]\nDescription=Test\n"
        self.early_source.write_text(content)
        with patch.object(os, "geteuid", return_value=0), patch("oled_early_boot.subprocess.run") as run:
            self.assertTrue(ensure_early_splash_service(
                str(self.early_source), str(self.early_unit), str(self.early_link)))
            self.assertEqual(self.early_unit.read_text(), content)
            self.assertEqual(run.call_count, 2)
            self.assertEqual(run.call_args_list[0].args[0], ["systemctl", "daemon-reload"])
            self.assertEqual(run.call_args_list[1].args[0], ["systemctl", "enable", "early-installed.service"])

            self.early_link.parent.mkdir()
            self.early_link.symlink_to(self.early_unit)
            run.reset_mock()
            self.assertFalse(ensure_early_splash_service(
                str(self.early_source), str(self.early_unit), str(self.early_link)))
            run.assert_not_called()

    def test_early_splash_preserves_custom_unit(self):
        self.early_source.write_text("# Managed by FENCEWALL OLED\n[Unit]\n")
        self.early_unit.write_text("[Unit]\nDescription=Custom\n")
        with patch.object(os, "geteuid", return_value=0), patch("oled_early_boot.subprocess.run") as run:
            with self.assertRaises(RuntimeError):
                ensure_early_splash_service(
                    str(self.early_source), str(self.early_unit), str(self.early_link))
            self.assertEqual(self.early_unit.read_text(), "[Unit]\nDescription=Custom\n")
            run.assert_not_called()

    def test_splash_skips_when_spi_is_not_ready(self):
        with patch("oled_boot_splash.os.path.exists", return_value=False), \
             patch("oled_boot_splash.time.monotonic", side_effect=[0, 7]), \
             patch("oled_boot_splash.time.sleep") as sleep:
            self.assertEqual(oled_boot_splash.main(), 0)
            sleep.assert_not_called()

    def test_splash_skips_when_menu_is_already_active(self):
        with patch("oled_boot_splash.os.path.exists", return_value=True), \
             patch("oled_boot_splash.menu_is_active", return_value=True):
            self.assertEqual(oled_boot_splash.main(), 0)


if __name__ == "__main__":
    unittest.main()
