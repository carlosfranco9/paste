import logging
import time
from pathlib import Path

from PySide2.QtCore import Qt, QSize, Signal, QRect
from PySide2.QtGui import QPixmap, QFont, QColor, QPainter, QBrush, QPen, QFontMetrics
from PySide2.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QApplication, QSizePolicy,
)

from src.database.models import ClipboardEntry

logger = logging.getLogger(__name__)

TYPE_ICONS = {
    "text": "📝",
    "image": "🖼",
    "link": "🔗",
    "file": "📎",
}


class ElidedLabel(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self._full_text = text

    def set_full_text(self, text):
        self._full_text = text
        self._elide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._elide()

    def _elide(self):
        fm = QFontMetrics(self.font())
        elided = fm.elidedText(self._full_text, Qt.ElideRight, self.width())
        super().setText(elided)


class HistoryItemWidget(QFrame):
    clicked = Signal(str)
    pin_toggled = Signal(str)
    delete_requested = Signal(str)

    def __init__(self, entry: ClipboardEntry, parent=None):
        super().__init__(parent)
        self.entry = entry
        self._setup_ui()
        self.setCursor(Qt.PointingHandCursor)

    def _setup_ui(self):
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("""
            HistoryItemWidget {
                background: transparent;
                border: none;
                border-radius: 6px;
                padding: 4px;
            }
            HistoryItemWidget:hover {
                background: rgba(128, 128, 128, 0.15);
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        icon_label = QLabel(TYPE_ICONS.get(self.entry.type, "📄"))
        icon_label.setFont(QFont("", 16))
        icon_label.setFixedSize(32, 32)
        icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_label)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        self._title = ElidedLabel(self._format_title())
        self._title.setFont(QFont("", 10))
        self._title.setStyleSheet("color: #E0E0E0;")
        self._title.setFixedHeight(20)
        text_layout.addWidget(self._title)

        meta_layout = QHBoxLayout()
        meta_layout.setSpacing(12)

        time_label = QLabel(self._format_time())
        time_label.setFont(QFont("", 8))
        time_label.setStyleSheet("color: #888;")
        meta_layout.addWidget(time_label)

        if self.entry.source_app:
            app_label = QLabel(self.entry.source_app)
            app_label.setFont(QFont("", 8))
            app_label.setStyleSheet("color: #666;")
            meta_layout.addWidget(app_label)

        meta_layout.addStretch()
        text_layout.addLayout(meta_layout)

        layout.addLayout(text_layout, 1)

        if self.entry.pinned:
            pin_label = QLabel("📌")
            pin_label.setFixedSize(20, 20)
            layout.addWidget(pin_label)

        delete_button = QPushButton("✕")
        delete_button.setObjectName("delete_button")
        delete_button.setToolTip("Delete this entry")
        delete_button.setFixedSize(24, 24)
        delete_button.setCursor(Qt.PointingHandCursor)
        delete_button.setStyleSheet("""
            QPushButton {
                color: #777;
                background: transparent;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                color: #fff;
                background: #a94442;
            }
        """)
        delete_button.clicked.connect(
            lambda checked=False: self.delete_requested.emit(self.entry.id)
        )
        layout.addWidget(delete_button)

    def _format_title(self) -> str:
        if self.entry.type == "image":
            return "[Image]"
        if self.entry.type == "link":
            return self.entry.content
        if self.entry.type == "file":
            return Path(self.entry.content).name
        return self.entry.content.replace("\n", " ").strip()

    def _format_time(self) -> str:
        from datetime import datetime, timezone
        try:
            created = datetime.fromisoformat(self.entry.created_at)
            now = datetime.now(timezone.utc)
            delta = now - created
            days = delta.days
            if days == 0:
                seconds = delta.seconds
                if seconds < 60:
                    return "Just now"
                if seconds < 3600:
                    return f"{seconds // 60}m ago"
                return f"{seconds // 3600}h ago"
            if days == 1:
                return "Yesterday"
            if days < 7:
                return f"{days}d ago"
            if days < 30:
                return f"{days // 7}w ago"
            return created.strftime("%Y-%m-%d")
        except Exception:
            return ""

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.entry.id)
        super().mousePressEvent(event)


class HistoryListWidget(QScrollArea):
    entry_clicked = Signal(str)
    delete_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []
        self._seen_fingerprints = set()
        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(2)
        self._layout.addStretch()

        self.setWidget(self._container)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                width: 6px; background: transparent;
            }
            QScrollBar::handle:vertical {
                background: #555; border-radius: 3px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

    def set_entries(self, entries):
        started = time.monotonic()
        incoming_count = len(entries) if hasattr(entries, "__len__") else None
        self.setUpdatesEnabled(False)
        try:
            self._clear_items()
            self._seen_fingerprints.clear()
            for entry in entries:
                if entry.fingerprint in self._seen_fingerprints:
                    continue
                self._seen_fingerprints.add(entry.fingerprint)
                widget = HistoryItemWidget(entry)
                widget.clicked.connect(self._on_item_clicked)
                widget.delete_requested.connect(self.delete_requested.emit)
                self._items.append(widget)
                self._layout.insertWidget(self._layout.count() - 1, widget)
            self.scrollToTop()
        finally:
            self.setUpdatesEnabled(True)
            self._container.updateGeometry()
            self.viewport().update()
        logger.debug(
            "History widgets replaced: incoming=%s rendered=%d elapsed_ms=%.1f",
            incoming_count,
            len(self._items),
            (time.monotonic() - started) * 1000,
        )

    def append_entry(self, entry: ClipboardEntry):
        if entry.fingerprint in self._seen_fingerprints:
            return
        self._seen_fingerprints.add(entry.fingerprint)
        widget = HistoryItemWidget(entry)
        widget.clicked.connect(self._on_item_clicked)
        widget.delete_requested.connect(self.delete_requested.emit)
        self._items.insert(0, widget)
        self._layout.insertWidget(0, widget)
        self.scrollToTop()

    def _on_item_clicked(self, entry_id):
        self.entry_clicked.emit(entry_id)

    def _clear_items(self):
        for widget in self._items:
            # removeWidget() does not hide a widget, and deleteLater() only
            # destroys it after control returns to Qt's event loop.  Hide and
            # detach it synchronously so old and new rows can never be painted
            # in the same position during a list replacement.
            widget.hide()
            self._layout.removeWidget(widget)
            widget.setParent(None)
            widget.deleteLater()
        self._items.clear()

    def scrollToTop(self):
        self.verticalScrollBar().setValue(0)
