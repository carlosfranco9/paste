import hashlib
import logging
import time

from PySide2.QtCore import Qt, QTimer, QPoint, QBuffer, Signal
from PySide2.QtGui import QFont, QKeySequence, QPixmap
from PySide2.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QApplication,
    QLabel, QPushButton, QFrame, QSizePolicy, QShortcut, QMessageBox,
)

from src.ui.search_bar import SearchBar
from src.ui.history_list import HistoryListWidget
from src.ui.filter_bar import FilterBar
from src.ui.preview import PreviewPanel
from src.ui.settings.hotkey_dialog import HotkeyDialog
from src.database.models import (
    ClipboardEntry,
    clear_entries,
    delete_entry,
    get_entry_by_id,
    get_recent_entries,
)
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
    hotkey_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._clip_processor = ClipProcessor()
        self._hotkey = HotkeyManager(self)
        self._drag_pos = QPoint()
        self._skip_fingerprint = None
        self._recent_hashes = set()
        self._active_filter = None
        self._list_loaded = False
        self._list_dirty = True
        self._show_pending = False
        self._last_toggle_at = 0.0
        self._setup_ui()
        self._setup_hotkey()
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

        self._filter_bar = FilterBar()
        self._filter_bar.filter_changed.connect(self._on_filter_changed)
        layout.addWidget(self._filter_bar)

        content = QHBoxLayout()
        content.setSpacing(8)

        self._list = HistoryListWidget()
        self._list.entry_clicked.connect(self._on_entry_clicked)
        self._list.delete_requested.connect(self._delete_entry)
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

        clear_btn = QPushButton("Clear All")
        clear_btn.setToolTip("Clear all clipboard history")
        clear_btn.clicked.connect(self._clear_history)
        layout.addWidget(clear_btn)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(26, 26)
        close_btn.clicked.connect(self.hide)
        layout.addWidget(close_btn)

        return header

    def _setup_hotkey(self):
        hotkey_str = config.get("hotkeys", "toggle_window", default="Ctrl+Shift+V")
        self._hotkey.register(hotkey_str)
        self._hotkey.activated.connect(
            lambda: self.toggle_visibility("hotkey")
        )

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

    def toggle_visibility(self, source="unknown"):
        now = time.monotonic()
        logger.info(
            "Visibility toggle requested: source=%s visible=%s pending=%s",
            source,
            self.isVisible(),
            self._show_pending,
        )
        if now - self._last_toggle_at < 0.25:
            logger.warning("Ignoring rapid repeated visibility toggle: source=%s", source)
            return
        self._last_toggle_at = now
        if self._show_pending:
            logger.warning("Ignoring duplicate show request while one is pending")
            return
        if self.isVisible():
            self.hide()
            logger.info("Main window hidden: source=%s", source)
        else:
            self._show_pending = True
            QTimer.singleShot(0, lambda: self._show_window(source))

    def _show_window(self, source):
        started = time.monotonic()
        self._show_pending = False
        self._focus_timer.stop()
        self.center_on_screen()
        self.show()
        self.raise_()
        self.activateWindow()
        self._search_bar.setFocus()
        self._search_bar.selectAll()
        logger.info(
            "Main window shown: source=%s elapsed_ms=%.1f",
            source,
            (time.monotonic() - started) * 1000,
        )

    def center_on_screen(self):
        screen = QApplication.primaryScreen()
        if screen:
            geometry = screen.availableGeometry()
            x = (geometry.width() - self.width()) // 2 + geometry.x()
            y = geometry.y() + geometry.height() // 4
            self.move(x, y)

    def showEvent(self, event):
        started = time.monotonic()
        super().showEvent(event)
        logger.info(
            "showEvent: loaded=%s dirty=%s query=%r filter=%s",
            self._list_loaded,
            self._list_dirty,
            self._search_bar.text().strip(),
            self._active_filter or "all",
        )
        if not self._list_loaded or self._list_dirty:
            self._refresh_list(self._search_bar.text().strip())
        else:
            logger.debug("Skipping unchanged history rebuild on showEvent")
        logger.debug(
            "showEvent completed: elapsed_ms=%.1f",
            (time.monotonic() - started) * 1000,
        )

    def hideEvent(self, event):
        logger.info("hideEvent")
        super().hideEvent(event)

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
            if not getattr(self, "_list_loaded", True):
                self._list_dirty = True
                return
            query = self._search_bar.text().strip()
            active_filter = getattr(self, "_active_filter", None)
            if query or active_filter:
                if getattr(self, "isVisible", lambda: True)():
                    self._refresh_list(query)
                else:
                    self._list_dirty = True
            else:
                self._list.append_entry(entry)
                self._update_count()

    def _on_search(self, query: str):
        self._refresh_list(query)

    def _on_filter_changed(self, filter_key):
        self._active_filter = None if filter_key == "all" else filter_key
        logger.info("History filter changed: %s", filter_key)
        self._refresh_list(self._search_bar.text().strip())

    def _on_search_confirm(self):
        self._search_bar.cancel_pending_search()
        query = self._search_bar.text().strip()
        entries = self._refresh_list(query)
        if not query:
            return
        if entries and self._list._items:
            first = self._list._items[0]
            self._on_entry_clicked(first.entry.id)

    def _refresh_list(self, query: str = ""):
        started = time.monotonic()
        entry_type = self._active_filter
        if query:
            rows = fts_search(query, entry_type=entry_type)
            entries = [ClipboardEntry.from_row(r) for r in rows]
        else:
            entries = get_recent_entries(limit=100, entry_type=entry_type)
        self._list.set_entries(entries)
        self._list_loaded = True
        self._list_dirty = False
        self._update_count(entry_type)
        logger.info(
            "History refreshed: query=%r filter=%s rows=%d elapsed_ms=%.1f",
            query,
            entry_type or "all",
            len(entries),
            (time.monotonic() - started) * 1000,
        )
        return entries

    def _update_count(self, entry_type=None):
        label = self.findChild(QLabel, "count_label")
        if label:
            if entry_type is None:
                entry_type = getattr(self, "_active_filter", None)
            label.setText(f"{count_entries(entry_type)} items")

    def _on_entry_clicked(self, entry_id):
        row = get_entry_by_id(entry_id)
        if row:
            entry = ClipboardEntry.from_row(row)
            self._preview.show_entry(entry)
            self._write_to_clipboard(entry)

    def copy_entry_by_id(self, entry_id):
        row = get_entry_by_id(entry_id)
        if not row:
            return False
        return self._write_to_clipboard(ClipboardEntry.from_row(row))

    def _delete_entry(self, entry_id):
        started = time.monotonic()
        if not delete_entry(entry_id):
            logger.warning("Delete requested for missing entry: id=%s", entry_id)
            return
        self._recent_hashes.clear()
        if self._preview.current_entry_id == entry_id:
            self._preview.clear()
        self._list_dirty = True
        self._refresh_list(self._search_bar.text().strip())
        logger.info(
            "History entry deleted: id=%s elapsed_ms=%.1f",
            entry_id,
            (time.monotonic() - started) * 1000,
        )

    def _clear_history(self):
        answer = QMessageBox.question(
            self,
            "Clear Clipboard History",
            "Delete all clipboard history? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            logger.info("Clear history cancelled")
            return
        started = time.monotonic()
        deleted_count = clear_entries()
        self._recent_hashes.clear()
        self._preview.clear()
        self._list_dirty = True
        self._refresh_list(self._search_bar.text().strip())
        logger.info(
            "Clipboard history cleared: rows=%d elapsed_ms=%.1f",
            deleted_count,
            (time.monotonic() - started) * 1000,
        )

    def open_hotkey_settings(self):
        if not self._hotkey.supports_global_hotkey:
            QMessageBox.information(
                self,
                "Configure Hotkey",
                "Paste cannot register global hotkeys directly on Wayland.\n\n"
                "Open your desktop keyboard settings, add a custom shortcut, "
                "and use this command:\n\n"
                "paste --show",
            )
            return

        current = config.get(
            "hotkeys", "toggle_window", default="Ctrl+Shift+V"
        )
        dialog = HotkeyDialog(current, self)

        def apply_hotkey(hotkey):
            if not self._hotkey.rebind(hotkey):
                error = self._hotkey.last_error or "The hotkey is already in use."
                dialog.show_error(f"Could not register this hotkey: {error}")
                return
            try:
                config.set("hotkeys", "toggle_window", hotkey)
            except OSError as error:
                self._hotkey.rebind(current)
                dialog.show_error(f"Could not save the hotkey: {error}")
                return
            self.hotkey_changed.emit(hotkey)
            dialog.accept()

        dialog.hotkey_submitted.connect(apply_hotkey)
        dialog.exec_()

    def _write_to_clipboard(self, entry):
        clipboard = QApplication.clipboard()
        if entry.type == "image":
            pix = QPixmap(entry.content)
            if pix.isNull():
                return False
            buf = QBuffer()
            buf.open(QBuffer.WriteOnly)
            pix.save(buf, "PNG")
            self._skip_fingerprint = hashlib.sha256(buf.data().data()).hexdigest()
            buf.close()
            clipboard.setPixmap(pix)
        else:
            self._skip_fingerprint = hashlib.sha256(entry.content.encode()).hexdigest()
            clipboard.setText(entry.content)
        return True
