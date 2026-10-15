import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fin_tracker.config import Config


class ConfigTests(unittest.TestCase):
    def test_missing_token_clear_error(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(ValueError, "BOT_TOKEN"):
            Config.from_env()

    def test_environment_configures_token_and_database(self):
        values = {"BOT_TOKEN": "123456:unit-secret", "DATABASE_PATH": "/tmp/finance-unit.sqlite3"}
        with patch.dict(os.environ, values, clear=True):
            config = Config.from_env()
        self.assertEqual(config.token, values["BOT_TOKEN"])
        self.assertEqual(config.database_path, Path(values["DATABASE_PATH"]))

    def test_both_entry_points_fail_cleanly_without_token(self):
        environment = {key: value for key, value in os.environ.items() if key != "BOT_TOKEN"}
        environment["UNRELATED_SECRET"] = "DO_NOT_PRINT_THIS_SECRET"
        for command in ([sys.executable, "-m", "fin_tracker"], [str(Path(sys.executable).parent / "fin-tracker")]):
            with self.subTest(command=command):
                result = subprocess.run(command, env=environment, capture_output=True, text=True, timeout=10, check=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("BOT_TOKEN", result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertNotIn("DO_NOT_PRINT_THIS_SECRET", result.stdout + result.stderr)
