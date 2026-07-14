from pathlib import Path

from PySide2.QtCore import Qt, QUrl
from PySide2.QtGui import QPixmap, QFont, QDesktopServices
from PySide2.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QScrollArea, QFrame,
    QSizePolicy, QApplication,
)

from src.database.models import ClipboardEntry


class PreviewPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self.setMinimumWidth(280)
        self.setMaximumWidth(400)

    def _setup_ui(self):
        self.setStyleSheet("""
            PreviewPanel {
                background: rgba(30, 30, 30, 0.9);
                border: none;
                border-radius: 8px;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        self._title = QLabel("Preview")
        self._title.setFont(QFont("", 12, QFont.Bold))
        self._title.setStyleSheet("color: #CCC;")
        layout.addWidget(self._title)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._content_widget = QWidget()
        self._content_layout = QVBoxLayout(self._content_widget)
        self._content_layout.setContentsMargins(0, 0, 0, 0)

        self._preview_label = QLabel("Select an item to preview")
        self._preview_label.setWordWrap(True)
        self._preview_label.setFont(QFont("", 10))
        self._preview_label.setStyleSheet("color: #888;")
        self._preview_label.setAlignment(Qt.AlignCenter)
        self._content_layout.addWidget(self._preview_label)
        self._content_layout.addStretch()

        self._scroll.setWidget(self._content_widget)
        layout.addWidget(self._scroll, 1)

        self._meta_label = QLabel()
        self._meta_label.setFont(QFont("", 9))
        self._meta_label.setStyleSheet("color: #666;")
        self._meta_label.setWordWrap(True)
        layout.addWidget(self._meta_label)

    def show_entry(self, entry: ClipboardEntry):
        self._update_meta(entry)
        self._clear_content()

        if entry.type == "image":
            self._show_image(entry)
        elif entry.type == "link":
            self._show_link(entry)
        elif entry.type == "file":
            self._show_file(entry)
        else:
            self._show_text(entry)

    def _show_text(self, entry: ClipboardEntry):
        label = QLabel(entry.content)
        label.setWordWrap(True)
        label.setFont(QFont("monospace", 10))
        label.setStyleSheet("color: #E0E0E0;")
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._content_layout.insertWidget(0, label)

    def _show_image(self, entry: ClipboardEntry):
        pixmap = QPixmap(entry.content)
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                360, 400, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            label = QLabel()
            label.setPixmap(scaled)
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("background: transparent;")
            self._content_layout.insertWidget(0, label)

    def _show_link(self, entry: ClipboardEntry):
        label = QLabel(f'<a href="{entry.content}" style="color: #4a6fa5;">{entry.content}</a>')
        label.setOpenExternalLinks(True)
        label.setWordWrap(True)
        label.setFont(QFont("", 10))
        self._content_layout.insertWidget(0, label)

    def _show_file(self, entry: ClipboardEntry):
        path = Path(entry.content)
        label = QLabel(f"📎 {path.name}\n{path.parent}")
        label.setWordWrap(True)
        label.setFont(QFont("monospace", 9))
        label.setStyleSheet("color: #CCC;")
        self._content_layout.insertWidget(0, label)

    def _update_meta(self, entry: ClipboardEntry):
        parts = []
        if entry.source_app:
            parts.append(f"From: {entry.source_app}")
        parts.append(f"Size: {self._format_size(entry.byte_size)}")
        if entry.created_at:
            parts.append(f"Copied: {entry.created_at[:19]}")
        self._meta_label.setText("  |  ".join(parts))

    def _clear_content(self):
        while self._content_layout.count() > 1:
            item = self._content_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

    @staticmethod
    def _format_size(size: int) -> str:
        if size < 1024:
            return f"{size} B"
        if size < 1024 * 1024:
            return f"{size/1024:.1f} KB"
        return f"{size/(1024*1024):.1f} MB"
