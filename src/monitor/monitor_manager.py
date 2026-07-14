import logging

from PySide2.QtCore import QObject, Signal

from src.monitor.clipboard_monitor import ClipboardMonitor

logger = logging.getLogger(__name__)


class MonitorManager(QObject):
    clip_changed = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._monitor = None

    def start(self):
        self._monitor = ClipboardMonitor(self)
        self._monitor.changed.connect(self._on_data)
        self._monitor.start()

    def stop(self):
        if self._monitor:
            self._monitor.stop()
            self._monitor = None

    def _on_data(self, data):
        self.clip_changed.emit(data)
