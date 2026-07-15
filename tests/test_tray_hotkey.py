import gc
import os
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide2.QtGui import QKeySequence
from PySide2.QtWidgets import QApplication, QSystemTrayIcon

from src.database.models import ClipboardEntry
from src.ui.main_window import MainWindow
from src.ui.settings.hotkey_dialog import HotkeyDialog
from src.ui.tray import TrayManager
from src.utils.hotkey import HotkeyManager
from src.utils import hotkey as hotkey_module


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


def make_entry(index, entry_type="text", content=None):
    return ClipboardEntry(
        id=f"entry-{index}",
        type=entry_type,
        content=content or f"recent item {index}",
        fingerprint=f"fingerprint-{index}",
        created_at="2026-07-15T00:00:00+00:00",
    )


def test_context_menu_actions_survive_garbage_collection(qt_app):
    tray = TrayManager(hotkey="Ctrl+Shift+V")
    gc.collect()

    actions = tray.contextMenu().actions()
    assert [action.text() for action in actions] == [
        "Show/Hide (Ctrl+Shift+V)",
        "Configure Hotkey...",
        "Recent",
        "",
        "Quit",
    ]
    assert tray._show_action.parent() is tray.contextMenu()
    assert tray._hotkey_action.parent() is tray.contextMenu()
    assert tray._quit_action.parent() is tray.contextMenu()
    assert tray._recent_submenu.parent() is tray.contextMenu()


def test_recent_menu_loads_five_items_and_emits_selected_id(
    qt_app, monkeypatch
):
    requested_limits = []
    entries = [make_entry(index) for index in range(7)]
    monkeypatch.setattr(
        "src.ui.tray.get_recent_entries",
        lambda limit: requested_limits.append(limit) or entries[:limit],
    )
    tray = TrayManager()
    selected = []
    tray.recent_entry_requested.connect(selected.append)

    tray._rebuild_recent_menu()
    actions = tray._recent_menu.actions()
    actions[2].trigger()

    assert requested_limits == [5]
    assert len(actions) == 5
    assert [action.data() for action in actions] == [
        f"entry-{index}" for index in range(5)
    ]
    assert selected == ["entry-2"]


def test_empty_recent_menu_has_disabled_placeholder(qt_app, monkeypatch):
    monkeypatch.setattr("src.ui.tray.get_recent_entries", lambda limit: [])
    tray = TrayManager()

    tray._rebuild_recent_menu()
    actions = tray._recent_menu.actions()

    assert len(actions) == 1
    assert actions[0].text() == "No recent items"
    assert not actions[0].isEnabled()


def test_only_left_click_activation_builds_recent_menu(qt_app):
    tray = TrayManager()
    calls = []
    tray._rebuild_recent_menu = lambda: calls.append("build")
    tray._recent_menu = SimpleNamespace(popup=lambda position: calls.append("popup"))

    tray._on_activated(QSystemTrayIcon.ActivationReason.Context)
    tray._on_activated(QSystemTrayIcon.ActivationReason.Trigger)

    assert calls == ["build", "popup"]


@pytest.mark.parametrize(
    "value, expected",
    [
        ("Ctrl+Shift+V", "Ctrl+Shift+V"),
        ("Meta+V", "Super+V"),
    ],
)
def test_hotkey_validation_accepts_supported_shortcuts(value, expected):
    hotkey, error = HotkeyDialog.validate_sequence(QKeySequence(value))

    assert hotkey == expected
    assert error is None


@pytest.mark.parametrize("value", ["", "V", "Ctrl+V, Ctrl+C"])
def test_hotkey_validation_rejects_unsafe_shortcuts(value):
    hotkey, error = HotkeyDialog.validate_sequence(QKeySequence(value))

    assert hotkey is None
    assert error


def test_super_hotkey_is_loaded_into_editor(qt_app):
    dialog = HotkeyDialog("Super+V")

    assert dialog._editor.keySequence().toString(QKeySequence.PortableText) == "Meta+V"


def test_rebind_restores_previous_hotkey_when_new_grab_fails(qt_app):
    manager = HotkeyManager()
    manager._current_hotkey = "Ctrl+Shift+V"
    manager._registered = True
    calls = []

    def unregister():
        calls.append("unregister")
        manager._current_hotkey = None
        manager._registered = False

    def register(hotkey):
        calls.append(("register", hotkey))
        if hotkey == "Ctrl+Alt+V":
            manager._last_error = "hotkey conflict"
            return False
        manager._current_hotkey = hotkey
        manager._registered = True
        manager._last_error = ""
        return True

    manager.unregister = unregister
    manager.register = register

    assert not manager.rebind("Ctrl+Alt+V")
    assert manager.current_hotkey == "Ctrl+Shift+V"
    assert manager.last_error == "hotkey conflict"
    assert calls == [
        "unregister",
        ("register", "Ctrl+Alt+V"),
        ("register", "Ctrl+Shift+V"),
    ]


def test_x11_grab_error_is_reported_as_hotkey_conflict(monkeypatch):
    class FakeRoot:
        def grab_key(self, *args, **kwargs):
            kwargs["onerror"](object(), object())

    class FakeDisplay:
        def __init__(self):
            self.root = FakeRoot()
            self.closed = False

        def screen(self):
            return SimpleNamespace(root=self.root)

        def keysym_to_keycode(self, keysym):
            return 55

        def sync(self):
            pass

        def close(self):
            self.closed = True

    fake_display = FakeDisplay()
    monkeypatch.setattr(
        "src.utils.hotkey.display.Display", lambda: fake_display
    )
    manager = HotkeyManager()

    assert not manager._register_x11("Ctrl+Shift+V")
    assert manager.last_error == "The hotkey is already in use."
    assert fake_display.closed


def test_hotkey_auto_repeat_is_ignored_until_key_release(qt_app):
    keycode = 55
    modifiers = hotkey_module.X.ControlMask
    events = [
        SimpleNamespace(
            type=hotkey_module.X.KeyPress,
            detail=keycode,
            state=modifiers,
        ),
        SimpleNamespace(
            type=hotkey_module.X.KeyPress,
            detail=keycode,
            state=modifiers,
        ),
        SimpleNamespace(
            type=hotkey_module.X.KeyRelease,
            detail=keycode,
            state=modifiers,
        ),
        SimpleNamespace(
            type=hotkey_module.X.KeyPress,
            detail=keycode,
            state=modifiers,
        ),
    ]
    manager = HotkeyManager()
    manager._registered = True
    manager._keycode = keycode
    manager._modifiers = modifiers
    manager._disp = SimpleNamespace(
        pending_events=lambda: len(events),
        next_event=lambda: events.pop(0),
    )
    activations = []
    manager.activated.connect(lambda: activations.append("activated"))

    assert manager.poll_event()
    assert manager.poll_event()

    assert activations == ["activated", "activated"]


def test_wayland_hotkey_settings_show_guidance_without_saving(monkeypatch):
    messages = []
    window = SimpleNamespace(
        _hotkey=SimpleNamespace(supports_global_hotkey=False)
    )
    monkeypatch.setattr(
        "src.ui.main_window.QMessageBox.information",
        lambda *args: messages.append(args),
    )
    config_sets = []
    monkeypatch.setattr(
        "src.ui.main_window.config.set",
        lambda *args: config_sets.append(args),
    )

    MainWindow.open_hotkey_settings(window)

    assert len(messages) == 1
    assert "paste --show" in messages[0][2]
    assert config_sets == []


def test_successful_hotkey_change_is_saved_and_announced(monkeypatch):
    class FakeSignal:
        def __init__(self):
            self.callback = None

        def connect(self, callback):
            self.callback = callback

        def emit(self, value):
            self.callback(value)

    class FakeDialog:
        def __init__(self, current, parent):
            self.current = current
            self.hotkey_submitted = FakeSignal()
            self.accepted = False

        def show_error(self, message):
            raise AssertionError(message)

        def accept(self):
            self.accepted = True

        def exec_(self):
            self.hotkey_submitted.emit("Ctrl+Alt+V")
            assert self.accepted

    saved = []
    announced = []
    monkeypatch.setattr("src.ui.main_window.HotkeyDialog", FakeDialog)
    monkeypatch.setattr(
        "src.ui.main_window.config.get", lambda *args, **kwargs: "Ctrl+Shift+V"
    )
    monkeypatch.setattr(
        "src.ui.main_window.config.set", lambda *args: saved.append(args)
    )
    window = SimpleNamespace(
        _hotkey=SimpleNamespace(
            supports_global_hotkey=True,
            rebind=lambda hotkey: hotkey == "Ctrl+Alt+V",
            last_error="",
        ),
        hotkey_changed=SimpleNamespace(emit=announced.append),
    )

    MainWindow.open_hotkey_settings(window)

    assert saved == [("hotkeys", "toggle_window", "Ctrl+Alt+V")]
    assert announced == ["Ctrl+Alt+V"]


def test_tray_entry_copy_uses_existing_clipboard_writer(monkeypatch):
    row = (
        "entry-1", "text", "copied value", None, None, None, None, None,
        "fingerprint", 0, None, 12, "2026-07-15T00:00:00+00:00", "", 0,
    )
    monkeypatch.setattr("src.ui.main_window.get_entry_by_id", lambda entry_id: row)
    copied = []
    window = SimpleNamespace(
        _write_to_clipboard=lambda entry: copied.append(entry) or True
    )

    assert MainWindow.copy_entry_by_id(window, "entry-1")
    assert copied[0].content == "copied value"
