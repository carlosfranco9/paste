import logging
import os

from PySide2.QtCore import QObject, Signal

logger = logging.getLogger(__name__)

try:
    from Xlib import display, X, XK
    HAS_XLIB = True
except ImportError:
    HAS_XLIB = False


class HotkeyManager(QObject):
    activated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._disp = None
        self._keycode = None
        self._modifiers = None
        self._registered = False
        self._current_hotkey = None
        self._last_error = ""

    @property
    def current_hotkey(self):
        return self._current_hotkey

    @property
    def last_error(self):
        return self._last_error

    @property
    def supports_global_hotkey(self):
        return self.session_type == "x11" and HAS_XLIB

    @property
    def session_type(self):
        return os.environ.get("XDG_SESSION_TYPE", "x11")

    def register(self, hotkey: str = "Ctrl+Shift+V"):
        self._last_error = ""
        if not self.supports_global_hotkey:
            self._last_error = (
                f"Global hotkeys are not supported on {self.session_type}."
            )
            logger.info(
                "%s Please configure '%s' in your desktop environment's "
                "keyboard settings.",
                self._last_error, hotkey,
            )
            return False
        return self._register_x11(hotkey)

    def _register_x11(self, hotkey: str):
        disp = None
        try:
            disp = display.Display()
            root = disp.screen().root

            keys = {
                "Ctrl": X.ControlMask,
                "Shift": X.ShiftMask,
                "Alt": X.Mod1Mask,
                "Super": X.Mod4Mask,
            }

            parts = [part.strip() for part in hotkey.split("+")]
            if len(parts) < 2 or not parts[-1]:
                raise ValueError("Hotkey must include a modifier and a key.")

            key_name = self._x11_key_name(parts[-1])
            mod_mask = 0
            for mod in parts[:-1]:
                if mod not in keys:
                    raise ValueError(f"Unsupported modifier: {mod}")
                mod_mask |= keys[mod]
            if not mod_mask:
                raise ValueError("Hotkey must include a modifier.")

            keycode = disp.keysym_to_keycode(
                XK.string_to_keysym(key_name)
            )
            if not keycode:
                raise ValueError(f"Unsupported key: {parts[-1]}")

            grab_errors = []

            def handle_grab_error(error, request):
                grab_errors.append(error)

            for ignored_mask in (
                0,
                X.Mod2Mask,
                X.LockMask,
                X.Mod2Mask | X.LockMask,
            ):
                root.grab_key(
                    keycode,
                    mod_mask | ignored_mask,
                    1,
                    X.GrabModeAsync,
                    X.GrabModeAsync,
                    onerror=handle_grab_error,
                )
            disp.sync()
            if grab_errors:
                raise RuntimeError("The hotkey is already in use.")

            self._disp = disp
            self._keycode = keycode
            self._modifiers = mod_mask
            self._registered = True
            self._current_hotkey = hotkey
            self._last_error = ""

            logger.info("Hotkey registered: %s", hotkey)
            return True
        except Exception as e:
            if disp is not None:
                try:
                    disp.close()
                except Exception:
                    pass
            self._disp = None
            self._keycode = None
            self._modifiers = None
            self._registered = False
            self._current_hotkey = None
            self._last_error = str(e) or "The hotkey is already in use."
            logger.error("Failed to register hotkey %s: %s", hotkey, e)
            return False

    def rebind(self, hotkey):
        if hotkey == self._current_hotkey and self._registered:
            self._last_error = ""
            return True

        previous = self._current_hotkey if self._registered else None
        self.unregister()
        if self.register(hotkey):
            return True

        new_error = self._last_error
        if previous and not self.register(previous):
            restore_error = self._last_error
            self._last_error = (
                f"{new_error} The previous hotkey could not be restored: "
                f"{restore_error}"
            )
        else:
            self._last_error = new_error
        return False

    @staticmethod
    def _x11_key_name(key_name):
        aliases = {
            "Esc": "Escape",
            "Del": "Delete",
            "Ins": "Insert",
            "PgUp": "Prior",
            "PgDown": "Next",
            "Space": "space",
        }
        return aliases.get(key_name, key_name)

    def poll_event(self):
        if not self._registered or not self._disp:
            return False
        try:
            while self._disp.pending_events():
                event = self._disp.next_event()
                if event.type == X.KeyPress:
                    if (event.detail == self._keycode and
                            event.state & ~(X.Mod2Mask | X.LockMask) ==
                            self._modifiers):
                        self.activated.emit()
                        return True
        except Exception:
            pass
        return False

    def unregister(self):
        self._registered = False
        if self._disp:
            self._disp.close()
            self._disp = None
        self._keycode = None
        self._modifiers = None
        self._current_hotkey = None
