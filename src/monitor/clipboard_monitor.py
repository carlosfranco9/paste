import logging
import os
import subprocess

from PySide2.QtCore import QObject, Signal, QTimer, QBuffer
from PySide2.QtGui import QClipboard
from PySide2.QtWidgets import QApplication

from src.monitor.types import ClipboardData

logger = logging.getLogger(__name__)


class ClipboardMonitor(QObject):
    changed = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._clipboard = None
        self._seen_fingerprints = set()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll_timer)
        self._session = os.environ.get("XDG_SESSION_TYPE", "x11")

    def start(self):
        self._clipboard = QApplication.clipboard()
        self._clipboard.dataChanged.connect(self._on_clipboard_change)
        self._timer.start(800)
        logger.info("Clipboard monitor started (session=%s)", self._session)

    def stop(self):
        self._timer.stop()
        if self._clipboard:
            try:
                self._clipboard.dataChanged.disconnect(self._on_clipboard_change)
            except Exception:
                pass

    def _on_clipboard_change(self):
        if self._read_text() is not None:
            return
        if self._read_pixmap() is not None:
            return
        self._try_xclip_image()

    def _poll_timer(self):
        if self._read_text() is not None:
            return
        self._read_pixmap()
        self._try_xclip_image()
        if self._read_text() is not None:
            return
        if self._read_pixmap() is not None:
            return
        self._try_xclip_image()

    def _read_text(self):
        try:
            text = self._clipboard.text(mode=QClipboard.Clipboard)
            if text and text.strip():
                text = text.strip()
                import re as _re
                raw = _re.sub(r'\s+', ' ', text).strip()
                fp = self._fingerprint(raw.encode())
                if fp in self._seen_fingerprints:
                    return ""
                self._seen_fingerprints.add(fp)
                data = ClipboardData(
                    mime_type="text/plain",
                    raw_data=text.encode(),
                    text=text,
                )
                self.changed.emit(data)
                return text
        except Exception as e:
            logger.debug("Read text error: %s", e)
        return None

    def _read_pixmap(self):
        try:
            pixmap = self._clipboard.pixmap(mode=QClipboard.Clipboard)
            if pixmap and not pixmap.isNull():
                buf = QBuffer()
                buf.open(QBuffer.WriteOnly)
                pixmap.save(buf, "PNG")
                data_bytes = buf.data().data()
                buf.close()
                if len(data_bytes) < 50:
                    return None
                fp = self._fingerprint(data_bytes)
                if fp in self._seen_fingerprints:
                    return data_bytes
                self._seen_fingerprints.add(fp)
                data = ClipboardData(
                    mime_type="image/png",
                    raw_data=data_bytes,
                    image_data=data_bytes,
                )
                self.changed.emit(data)
                return data_bytes
        except Exception as e:
            logger.debug("Read pixmap error: %s", e)
        return None

    def _try_xclip_image(self):
        try:
            result = subprocess.run(
                ["xclip", "-selection", "clipboard", "-o", "-t", "image/png"],
                capture_output=True, timeout=1,
            )
            if result.returncode == 0 and len(result.stdout) > 50:
                data_bytes = result.stdout
                fp = self._fingerprint(data_bytes)
                if fp in self._seen_fingerprints:
                    return
                self._seen_fingerprints.add(fp)
                data = ClipboardData(
                    mime_type="image/png",
                    raw_data=data_bytes,
                    image_data=data_bytes,
                )
                self.changed.emit(data)
        except Exception:
            pass

    @staticmethod
    def _fingerprint(data: bytes) -> str:
        import hashlib
        return hashlib.sha256(data).hexdigest()
