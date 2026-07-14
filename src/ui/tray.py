import logging

from PySide2.QtCore import Qt, Signal, QRect
from PySide2.QtGui import QIcon
from PySide2.QtWidgets import (
    QSystemTrayIcon, QMenu, QApplication, QAction,
)

logger = logging.getLogger(__name__)


class TrayManager(QSystemTrayIcon):
    show_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup()

    def _setup(self):
        self.setToolTip("Paste — Clipboard Manager")

        icon = QIcon.fromTheme("edit-paste")
        if icon.isNull():
            icon = self._create_fallback_icon()
        self.setIcon(icon)

        menu = QMenu()

        show_action = QAction("Show/Hide (Ctrl+Shift+V)", None)
        show_action.triggered.connect(self.show_requested.emit)
        menu.addAction(show_action)

        menu.addSeparator()
        quit_action = QAction("Quit", None)
        quit_action.triggered.connect(self.quit_requested.emit)
        menu.addAction(quit_action)

        self.setContextMenu(menu)
        self.activated.connect(self._on_activated)

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_requested.emit()

    def _create_fallback_icon(self):
        from PySide2.QtGui import QPixmap, QPainter, QColor, QBrush, QFont
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QBrush(QColor("#4a6fa5")))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(2, 2, 60, 60, 8, 8)
        painter.setPen(QColor("white"))
        painter.setFont(QFont("", 32, QFont.Bold))
        painter.drawText(QRect(0, 0, 64, 64), Qt.AlignCenter, "P")
        painter.end()
        return QIcon(pixmap)
