from PySide2.QtCore import Qt, QTimer, Signal
from PySide2.QtGui import QFont
from PySide2.QtWidgets import QLineEdit


class SearchBar(QLineEdit):
    search_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("🔍  Search clipboard history...")
        self.setClearButtonEnabled(True)
        self.setFont(QFont("", 13))
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._emit_search)

        self.setStyleSheet("""
            QLineEdit {
                background: rgba(40, 40, 40, 0.95);
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                color: #E0E0E0;
                font-size: 14px;
                selection-background-color: #4a6fa5;
            }
            QLineEdit:focus {
                border: 1px solid #4a6fa5;
            }
        """)
        self.textChanged.connect(self._on_text_changed)

    def _on_text_changed(self, text: str):
        self._debounce_timer.start(300)

    def _emit_search(self):
        self.search_requested.emit(self.text().strip())

    def cancel_pending_search(self):
        self._debounce_timer.stop()
