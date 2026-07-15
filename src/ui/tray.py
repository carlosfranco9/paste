import logging
from datetime import datetime, timezone
from pathlib import Path

from PySide2.QtCore import Qt, Signal, QRect
from PySide2.QtGui import QCursor, QIcon
from PySide2.QtWidgets import (
    QSystemTrayIcon, QMenu, QAction,
)

from src.database.models import get_recent_entries

logger = logging.getLogger(__name__)


class TrayManager(QSystemTrayIcon):
    show_requested = Signal()
    quit_requested = Signal()
    recent_entry_requested = Signal(str)
    hotkey_settings_requested = Signal()

    def __init__(self, hotkey="Ctrl+Shift+V", parent=None):
        super().__init__(parent)
        self._hotkey = hotkey
        self._recent_menu = None
        self._recent_actions = []
        self._setup()

    def _setup(self):
        self.setToolTip("Paste — Clipboard Manager")

        icon = QIcon.fromTheme("edit-paste")
        if icon.isNull():
            icon = self._create_fallback_icon()
        self.setIcon(icon)

        # Keep menus and actions as instance-owned objects.  Actions without a
        # parent can be garbage-collected by PySide after this method returns,
        # leaving the tray context menu empty.
        self._context_menu = QMenu()
        self._show_action = QAction(self._show_action_text(), self._context_menu)
        self._show_action.triggered.connect(self.show_requested.emit)
        self._context_menu.addAction(self._show_action)

        self._hotkey_action = QAction("Configure Hotkey...", self._context_menu)
        self._hotkey_action.triggered.connect(self.hotkey_settings_requested.emit)
        self._context_menu.addAction(self._hotkey_action)

        self._recent_submenu = QMenu("Recent", self._context_menu)
        self._context_menu.addMenu(self._recent_submenu)

        self._context_menu.addSeparator()
        self._quit_action = QAction("Quit", self._context_menu)
        self._quit_action.triggered.connect(self.quit_requested.emit)
        self._context_menu.addAction(self._quit_action)

        self.setContextMenu(self._context_menu)
        self._context_menu.aboutToShow.connect(self._on_context_menu_about_to_show)
        self.activated.connect(self._on_activated)

    def _on_activated(self, reason):
        reason_names = {
            QSystemTrayIcon.ActivationReason.Unknown: "Unknown",
            QSystemTrayIcon.ActivationReason.Context: "Context",
            QSystemTrayIcon.ActivationReason.DoubleClick: "DoubleClick",
            QSystemTrayIcon.ActivationReason.Trigger: "Trigger",
            QSystemTrayIcon.ActivationReason.MiddleClick: "MiddleClick",
        }
        logger.info(
            "Tray activated: reason=%s(%s)",
            reason_names.get(reason, "unmapped"),
            int(reason),
        )
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._rebuild_recent_menu()
            self._recent_menu.popup(QCursor.pos())

    def _on_context_menu_about_to_show(self):
        logger.info("Tray context menu opening")
        self._populate_recent_menu(self._recent_submenu)

    def _rebuild_recent_menu(self):
        if self._recent_menu is not None:
            self._recent_menu.hide()
            self._recent_menu.deleteLater()

        self._recent_menu = QMenu()
        self._populate_recent_menu(self._recent_menu, track_actions=True)

    def _populate_recent_menu(self, menu, track_actions=False):
        menu.clear()
        if track_actions:
            self._recent_actions = []
        entries = get_recent_entries(limit=5)
        logger.debug("Building recent tray menu: rows=%d", len(entries))

        if not entries:
            action = QAction("No recent items", menu)
            action.setEnabled(False)
            menu.addAction(action)
            if track_actions:
                self._recent_actions.append(action)
            return

        for entry in entries:
            action = QAction(self._format_entry(entry), menu)
            action.setData(entry.id)
            action.triggered.connect(
                lambda checked=False, entry_id=entry.id:
                self._select_recent_entry(entry_id)
            )
            menu.addAction(action)
            if track_actions:
                self._recent_actions.append(action)

    def _select_recent_entry(self, entry_id):
        logger.info("Recent tray entry selected: id=%s", entry_id)
        self.recent_entry_requested.emit(entry_id)

    def set_hotkey(self, hotkey):
        logger.info("Tray hotkey label updated: %s", hotkey)
        self._hotkey = hotkey
        self._show_action.setText(self._show_action_text())

    def _show_action_text(self):
        return f"Show/Hide ({self._hotkey})"

    @classmethod
    def _format_entry(cls, entry):
        icons = {
            "text": "📝",
            "image": "🖼",
            "link": "🔗",
            "file": "📎",
        }
        if entry.type == "image":
            summary = "Image"
        elif entry.type == "file":
            summary = Path(entry.content).name or entry.content
        else:
            summary = " ".join(entry.content.split())
        if len(summary) > 60:
            summary = summary[:57] + "..."
        summary = summary or "(empty)"
        return (
            f"{icons.get(entry.type, '📄')} {summary}"
            f"  —  {cls._format_time(entry.created_at)}"
        )

    @staticmethod
    def _format_time(value):
        try:
            created = datetime.fromisoformat(value)
            now = datetime.now(created.tzinfo or timezone.utc)
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            seconds = max(0, int((now - created).total_seconds()))
            if seconds < 60:
                return "Just now"
            if seconds < 3600:
                return f"{seconds // 60}m ago"
            if seconds < 86400:
                return f"{seconds // 3600}h ago"
            if seconds < 172800:
                return "Yesterday"
            if seconds < 604800:
                return f"{seconds // 86400}d ago"
            return created.strftime("%Y-%m-%d")
        except (TypeError, ValueError):
            return ""

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
