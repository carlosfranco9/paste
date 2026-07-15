from PySide2.QtCore import Signal
from PySide2.QtGui import QKeySequence
from PySide2.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QKeySequenceEdit,
    QLabel,
    QVBoxLayout,
)


class HotkeyDialog(QDialog):
    hotkey_submitted = Signal(str)

    def __init__(self, current_hotkey, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configure Hotkey")
        self.setModal(True)
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Press a shortcut to show or hide Paste:"))

        qt_hotkey = current_hotkey.replace("Super+", "Meta+")
        self._editor = QKeySequenceEdit(QKeySequence(qt_hotkey), self)
        self._editor.keySequenceChanged.connect(self._clear_error)
        layout.addWidget(self._editor)

        hint = QLabel("Use one shortcut containing Ctrl, Alt, Shift, or Super.")
        hint.setStyleSheet("color: #888;")
        layout.addWidget(hint)

        self._error_label = QLabel()
        self._error_label.setWordWrap(True)
        self._error_label.setStyleSheet("color: #d9534f;")
        layout.addWidget(self._error_label)

        buttons = QDialogButtonBox(self)
        buttons.addButton(QDialogButtonBox.Save)
        buttons.addButton(QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._submit)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _submit(self):
        hotkey, error = self.validate_sequence(self._editor.keySequence())
        if error:
            self.show_error(error)
            return
        self.hotkey_submitted.emit(hotkey)

    def show_error(self, message):
        self._error_label.setText(message)

    def _clear_error(self, sequence=None):
        self._error_label.clear()

    @staticmethod
    def validate_sequence(sequence):
        text = sequence.toString(QKeySequence.PortableText).strip()
        if not text:
            return None, "Choose a hotkey before saving."
        if "," in text:
            return None, "Only one shortcut can be configured."

        text = text.replace("Meta+", "Super+")
        parts = text.split("+")
        modifiers = parts[:-1]
        key = parts[-1]
        allowed = {"Ctrl", "Alt", "Shift", "Super"}
        if not key or not modifiers:
            return None, "The hotkey must include a modifier and a key."
        if any(modifier not in allowed for modifier in modifiers):
            return None, "The hotkey contains an unsupported modifier."
        if key in allowed:
            return None, "The hotkey must end with a non-modifier key."
        return "+".join(modifiers + [key]), None
