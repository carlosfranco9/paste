import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tempfile
import json
from src.storage.config import Config, CONFIG_PATH


class TestConfig:
    def test_default_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            import src.storage.config as cfg
            original = cfg.CONFIG_PATH
            cfg.CONFIG_PATH = Path(tmp) / "config.json"

            c = Config()
            assert c.get("clipboard", "max_history") == 1000
            assert c.get("behavior", "close_to_tray") is True

            cfg.CONFIG_PATH = original

    def test_set_and_get(self):
        with tempfile.TemporaryDirectory() as tmp:
            import src.storage.config as cfg
            original = cfg.CONFIG_PATH
            cfg.CONFIG_PATH = Path(tmp) / "config.json"

            c = Config()
            c.set("appearance", "theme", "dark")
            assert c.get("appearance", "theme") == "dark"

            cfg.CONFIG_PATH = original

    def test_persist_to_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            import src.storage.config as cfg
            original = cfg.CONFIG_PATH
            cfg.CONFIG_PATH = Path(tmp) / "config.json"

            c = Config()
            c.set("behavior", "auto_start", True)

            c2 = Config()
            assert c2.get("behavior", "auto_start") is True

            cfg.CONFIG_PATH = original
