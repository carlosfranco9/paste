from PySide2.QtCore import Qt, Signal
from PySide2.QtWidgets import QButtonGroup, QHBoxLayout, QPushButton, QWidget


class FilterBar(QWidget):
    filter_changed = Signal(str)

    FILTERS = (
        ("all", "All"),
        ("link", "URLs"),
        ("image", "Images"),
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons = {}
        for key, label in self.FILTERS:
            button = QPushButton(label, self)
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            button.setStyleSheet("""
                QPushButton {
                    color: #999;
                    background: #292929;
                    border: 1px solid #444;
                    border-radius: 6px;
                    padding: 4px 12px;
                }
                QPushButton:checked {
                    color: #fff;
                    background: #3a6fa5;
                    border-color: #4a7fb5;
                }
            """)
            button.clicked.connect(
                lambda checked=False, filter_key=key:
                self.filter_changed.emit(filter_key)
            )
            self._group.addButton(button)
            self._buttons[key] = button
            layout.addWidget(button)
        layout.addStretch()
        self._buttons["all"].setChecked(True)

    @property
    def current_filter(self):
        for key, button in self._buttons.items():
            if button.isChecked():
                return key
        return "all"
