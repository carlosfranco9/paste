import logging

from PySide2.QtCore import qInstallMessageHandler
from PySide2.QtWidgets import QApplication

from src.storage.config import config
from src.database.db import DatabaseManager

logger = logging.getLogger(__name__)


def _qt_message_handler(mode, context, message):
    if "BadWindow" in message or "SelectionRequest too old" in message:
        logger.debug("Qt transient warning: %s", message)
        return
    if "FIXME" in message:
        logger.debug("Qt FIXME: %s", message)
        return
    logger.debug("Qt: %s", message)


class PasteApplication(QApplication):
    def __init__(self, argv):
        qInstallMessageHandler(_qt_message_handler)
        super().__init__(argv)
        self.setApplicationName("Paste")
        self.setApplicationDisplayName("Paste - Clipboard Manager")
        self.setQuitOnLastWindowClosed(False)
        self._init_style()

    def _init_style(self):
        self.setStyle("Fusion")
        theme = config.get("appearance", "theme", default="system")
        if theme == "dark":
            self._apply_dark_theme()

    def _apply_dark_theme(self):
        palette = self.palette()
        from PySide2.QtGui import QColor, QPalette
        palette.setColor(QPalette.Window, QColor(26, 26, 26))
        palette.setColor(QPalette.WindowText, QColor(224, 224, 224))
        palette.setColor(QPalette.Base, QColor(20, 20, 20))
        palette.setColor(QPalette.Text, QColor(224, 224, 224))
        palette.setColor(QPalette.Button, QColor(40, 40, 40))
        palette.setColor(QPalette.ButtonText, QColor(224, 224, 224))
        palette.setColor(QPalette.Highlight, QColor(74, 111, 165))
        self.setPalette(palette)

    @staticmethod
    def instance() -> "PasteApplication":
        return QApplication.instance()
