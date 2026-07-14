import json
import os
from pathlib import Path
from typing import Any, Dict, List

CONFIG_PATH = Path.home() / ".paste" / "config.json"

DEFAULT_CONFIG = {
    "appearance": {
        "theme": "system",
        "max_width": 800,
        "show_thumbnail": True,
    },
    "clipboard": {
        "max_history": 1000,
        "max_days": 30,
        "watch_images": True,
        "watch_files": False,
        "dedup_exact": True,
        "dedup_normalize": True,
        "dedup_interval_ms": 3000,
    },
    "hotkeys": {
        "toggle_window": "Ctrl+Shift+V",
        "paste_previous": "Ctrl+Shift+P",
    },
    "storage": {
        "media_limit_mb": 2000,
        "auto_clean_days": 30,
    },
    "behavior": {
        "auto_start": False,
        "close_to_tray": True,
        "hide_on_focus_lost": True,
    },
    "exclusions": [
        {"type": "app_name", "pattern": "keepassxc"},
        {"type": "app_name", "pattern": "1password"},
        {"type": "app_name", "pattern": "bitwarden"},
        {"type": "app_name", "pattern": "gopass"},
    ],
}


class Config:
    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._load()

    def _load(self):
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        if CONFIG_PATH.exists():
            try:
                self._data = json.loads(CONFIG_PATH.read_text())
            except (json.JSONDecodeError, OSError):
                self._data = {}
        self._apply_defaults()

    def _apply_defaults(self):
        def _merge(default, target):
            for k, v in default.items():
                if k not in target:
                    target[k] = v
                elif isinstance(v, dict):
                    _merge(v, target[k])
        _merge(DEFAULT_CONFIG, self._data)

    def _save(self):
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False)
        )

    def get(self, *keys: str, default=None):
        val = self._data
        for k in keys:
            if isinstance(val, dict):
                val = val.get(k)
            else:
                return default
        return val if val is not None else default

    def set(self, *keys_and_value):
        keys = keys_and_value[:-1]
        value = keys_and_value[-1]
        val = self._data
        for k in keys[:-1]:
            if k not in val or not isinstance(val[k], dict):
                val[k] = {}
            val = val[k]
        val[keys[-1]] = value
        self._save()

    @property
    def data(self) -> dict:
        return self._data

    def get_exclusions(self) -> List[dict]:
        return self._data.get("exclusions", [])

    def add_exclusion(self, rule_type: str, pattern: str):
        exclusions = self._data.setdefault("exclusions", [])
        exclusions.append({"type": rule_type, "pattern": pattern})
        self._save()


config = Config()
