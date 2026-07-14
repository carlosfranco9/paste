import sys
from pathlib import Path

AUTOSTART_DIR = Path.home() / ".config" / "autostart"
DESKTOP_FILE = AUTOSTART_DIR / "paste.desktop"


def is_autostart_enabled() -> bool:
    return DESKTOP_FILE.exists()


def enable_autostart():
    AUTOSTART_DIR.mkdir(parents=True, exist_ok=True)
    content = f"""[Desktop Entry]
Type=Application
Name=Paste
Comment=Clipboard Manager
Exec={sys.argv[0]}
Terminal=false
Categories=Utility;
X-GNOME-Autostart-enabled=true
"""
    DESKTOP_FILE.write_text(content)


def disable_autostart():
    if DESKTOP_FILE.exists():
        DESKTOP_FILE.unlink()
