#!/usr/bin/env python3
import sys
import os
import signal
import logging
import io as stdlib_io

os.environ["XDG_CURRENT_DESKTOP"] = os.environ.get("XDG_CURRENT_DESKTOP", "GNOME")


class _StderrFilter(stdlib_io.IOBase):
    def __init__(self):
        self._stderr = sys.stderr

    def write(self, text):
        if "FIXME" in text or "Subscripted generics" in text:
            return len(text)
        return self._stderr.write(text)

    def flush(self):
        self._stderr.flush()


sys.stderr = _StderrFilter()

from PySide2.QtCore import QTimer

from src.app import PasteApplication
from src.database.models import dedup_entries
from src.ui.main_window import MainWindow
from src.ui.tray import TrayManager
from src.monitor.monitor_manager import MonitorManager
from src.monitor.clip_processor import ClipProcessor
from src.storage.config import config

logger = logging.getLogger(__name__)


def main():
    app = PasteApplication(sys.argv)

    import fcntl
    sig_r, sig_w = os.pipe()
    for fd in (sig_r, sig_w):
        fcntl.fcntl(fd, fcntl.F_SETFL, os.O_NONBLOCK)
    signal.set_wakeup_fd(sig_w)

    def check_signal():
        try:
            data = os.read(sig_r, 65536)
            if data:
                logger.info("SIGINT received, quitting...")
                app.quit()
        except (BlockingIOError, OSError):
            pass

    poller = QTimer()
    poller.timeout.connect(check_signal)
    poller.start(300)

    signal.signal(signal.SIGINT, lambda s, f: None)

    window = MainWindow()
    hotkey = config.get("hotkeys", "toggle_window", default="Ctrl+Shift+V")
    tray = TrayManager(hotkey=hotkey)
    monitor = MonitorManager()

    clip_processor = ClipProcessor()

    tray.show_requested.connect(window.toggle_visibility)
    tray.recent_entry_requested.connect(window.copy_entry_by_id)
    tray.hotkey_settings_requested.connect(window.open_hotkey_settings)
    tray.quit_requested.connect(app.quit)
    window.hotkey_changed.connect(tray.set_hotkey)

    monitor.clip_changed.connect(window.add_clipboard_data)

    dedup_entries()
    tray.show()
    monitor.start()

    if "--show" in sys.argv:
        window.toggle_visibility()

    app.aboutToQuit.connect(lambda: cleanup(monitor, window, tray))

    sys.exit(app.exec_())


def cleanup(monitor, window, tray):
    logger.info("Shutting down...")
    monitor.stop()
    window.hide()
    tray.hide()


if __name__ == "__main__":
    main()
