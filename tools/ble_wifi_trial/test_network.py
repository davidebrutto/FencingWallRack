import unittest
from unittest.mock import patch

import network


class NetworkTrialTests(unittest.TestCase):
    def test_validation(self):
        network.validate("Gara WiFi", "password123")
        with self.assertRaises(ValueError):
            network.validate("", "password123")
        with self.assertRaises(ValueError):
            network.validate("Gara", "short")
        with self.assertRaises(ValueError):
            network.validate("Gara\nother", "password123")

    @patch("network._run")
    def test_existing_profile_is_never_overwritten(self, run):
        run.side_effect = [type("Result", (), {"stdout": "30 (disconnected)"})(),
                           type("Result", (), {"stdout": network.PROFILE + "\n"})()]
        with self.assertRaises(RuntimeError):
            network.connect("Gara", "password123")
        self.assertEqual(run.call_count, 2)


if __name__ == "__main__":
    unittest.main()
