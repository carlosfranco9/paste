import hashlib
import logging

from PySide2.QtCore import Qt, QTimer, QPoint, QBuffer
from PySide2.QtGui import QFont, QKeySequence, QPixmap
from PySide2.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QApplication,
    QLabel, QPushButton, QFrame, QSizePolicy, QShortcut,
)

from src.ui.search_bar import SearchBar
from src.ui.history_list import HistoryListWidget
from src.ui.preview import PreviewPanel
from src.database.models import get_recent_entries, ClipboardEntry, get_entry_by_id
from src.database.search import fts_search, count_entries
from src.storage.config import config
from src.monitor.types import ClipboardData
from src.monitor.clip_processor import ClipProcessor
from src.utils.hotkey import HotkeyManager

logger = logging.getLogger(__name__)

STYLESHEET = """
QWidget {
    background-color: #1e1e1e;
    color: #e0e0e0;
    font-family: "Noto Sans", "Ubuntu", "DejaVu Sans", sans-serif;
    font-size: 13px;
}
MainWindow {
    border: 1px solid #444;
    border-radius: 10px;
}
QLineEdit {
    background-color: #2a2a2a;
    color: #e0e0e0;
    border: 1px solid #555;
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 14px;
    selection-background-color: #3a6fa5;
}
QLineEdit:focus {
    border: 1px solid #4a6fa5;
}
QPushButton {
    background: transparent;
    border: none;
    color: #888;
    font-size: 14px;
}
QPushButton:hover {
    color: #e0e0e0;
}
QLabel {
    background: transparent;
    color: #e0e0e0;
}
QScrollArea {
    background: transparent;
    border: none;
}
QScrollBar:vertical {
    width: 6px;
    background: #2a2a2a;
}
QScrollBar::handle:vertical {
    background: #555;
    border-radius: 3px;
    min-height: 30px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal { height: 0; }
"""


class MainWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._clip_processor = ClipProcessor()
        self._hotkey = HotkeyManager(self)
        self._drag_pos = QPoint()
        self._skip_fingerprint = None
        self._recent_hashes = set()
        self._setup_ui()
        self._setup_hotkey()
        self._load_history()
        self._setup_auto_hide()

    def _setup_ui(self):
        self.setWindowTitle("Paste")
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.resize(720, 520)
        self.setMinimumSize(500, 400)
        self.setStyleSheet(STYLESHEET)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 10)
        layout.setSpacing(6)

        self._search_bar = SearchBar()
        self._search_bar.search_requested.connect(self._on_search)
        self._search_bar.returnPressed.connect(self._on_search_confirm)
        layout.addWidget(self._search_bar)

        header = self._build_header()
        layout.addWidget(header)

        content = QHBoxLayout()
        content.setSpacing(8)

        self._list = HistoryListWidget()
        self._list.entry_clicked.connect(self._on_entry_clicked)
        content.addWidget(self._list, 3)

        self._preview = PreviewPanel()
        content.addWidget(self._preview, 2)

        layout.addLayout(content, 1)

    def _build_header(self):
        header = QWidget()
        header.setFixedHeight(28)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(4, 0, 4, 0)

        title = QLabel("Paste")
        title.setFont(QFont("", 13, QFont.Bold))
        layout.addWidget(title)

        layout.addStretch()

        count_label = QLabel()
        count_label.setStyleSheet("color: #888; font-size: 11px;")
        count_label.setObjectName("count_label")
        layout.addWidget(count_label)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(26, 26)
        close_btn.clicked.connect(self.hide)
        layout.addWidget(close_btn)

        return header

    def _setup_hotkey(self):
        hotkey_str = config.get("hotkeys", "toggle_window", default="Ctrl+Shift+V")
        self._hotkey.register(hotkey_str)
        self._hotkey.activated.connect(self.toggle_visibility)

        self._hotkey_poll = QTimer(self)
        self._hotkey_poll.timeout.connect(self._hotkey.poll_event)
        self._hotkey_poll.start(100)

        esc_shortcut = QShortcut(QKeySequence("Escape"), self)
        esc_shortcut.activated.connect(self.hide)

    def _setup_auto_hide(self):
        self._focus_timer = QTimer(self)
        self._focus_timer.setSingleShot(True)
        self._focus_timer.timeout.connect(self._check_focus)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = QPoint()

    def toggle_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            self.center_on_screen()
            self.show()
            self.raise_()
            self.activateWindow()
            self._search_bar.setFocus()
            self._search_bar.selectAll()

    def center_on_screen(self):
        screen = QApplication.primaryScreen()
        if screen:
            geometry = screen.availableGeometry()
            x = (geometry.width() - self.width()) // 2 + geometry.x()
            y = geometry.y() + geometry.height() // 4
            self.move(x, y)

    def showEvent(self, event):
        super().showEvent(event)
        self._load_history()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        if config.get("behavior", "hide_on_focus_lost", default=True):
            self._focus_timer.start(200)

    def _check_focus(self):
        if not self.isActiveWindow() and self.isVisible():
            self.hide()

    def add_clipboard_data(self, data: ClipboardData):
        if self._skip_fingerprint:
            fp = hashlib.sha256(data.fingerprint_data).hexdigest()
            if fp == self._skip_fingerprint:
                self._skip_fingerprint = None
                return
            self._skip_fingerprint = None
        content_hash = hashlib.md5(data.fingerprint_data).hexdigest()
        if content_hash in self._recent_hashes:
            return
        self._recent_hashes.add(content_hash)
        if len(self._recent_hashes) > 200:
            self._recent_hashes.clear()
        entry = self._clip_processor.process(data)
        if entry:
            self._list.append_entry(entry)
            self._update_count()

    def _on_search(self, query: str):
        if query:
            rows = fts_search(query)
            entries = [ClipboardEntry.from_row(r) for r in rows]
            self._list.set_entries(entries)
        else:
            self._load_history()

    def _on_search_confirm(self):
        query = self._search_bar.text().strip()
        if not query:
            return self._load_history()
        rows = fts_search(query)
        entries = [ClipboardEntry.from_row(r) for r in rows]
        self._list.set_entries(entries)
        if entries and self._list._items:
            first = self._list._items[0]
            self._on_entry_clicked(first.entry.id)

    def _load_history(self):
        entries = get_recent_entries(limit=100)
        self._list.set_entries(entries)
        self._update_count()

    def _update_count(self):
        label = self.findChild(QLabel, "count_label")
        if label:
            label.setText(f"{count_entries()} items")

    def _on_entry_clicked(self, entry_id):
        row = get_entry_by_id(entry_id)
        if row:
            entry = ClipboardEntry.from_row(row)
            self._preview.show_entry(entry)
            self._write_to_clipboard(entry)

    def _write_to_clipboard(self, entry):
        clipboard = QApplication.clipboard()
        if entry.type == "image":
            pix = QPixmap(entry.content)
            if pix.isNull():
                return
            buf = QBuffer()
            buf.open(QBuffer.WriteOnly)
            pix.save(buf, "PNG")
            self._skip_fingerprint = hashlib.sha256(buf.data().data()).hexdigest()
            buf.close()
            clipboard.setPixmap(pix)
        else:
            self._skip_fingerprint = hashlib.sha256(entry.content.encode()).hexdigest()
            clipboard.setText(entry.content)
