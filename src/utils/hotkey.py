import logging
import os
import subprocess

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

    def register(self, hotkey: str = "Ctrl+Shift+V"):
        session = os.environ.get("XDG_SESSION_TYPE", "x11")
        if session == "x11" and HAS_XLIB:
            self._register_x11(hotkey)
        else:
            logger.info(
                "Global hotkey not supported on %s. "
                "Please configure '%s' in your desktop environment's keyboard settings.",
                session, hotkey,
            )

    def _register_x11(self, hotkey: str):
        try:
            self._disp = display.Display()
            root = self._disp.screen().root

            keys = {
                "Ctrl": X.ControlMask,
                "Shift": X.ShiftMask,
                "Alt": X.Mod1Mask,
                "Super": X.Mod4Mask,
            }

            parts = hotkey.split("+")
            key_name = parts[-1]
            mod_mask = 0
            for mod in parts[:-1]:
                if mod in keys:
                    mod_mask |= keys[mod]

            keycode = self._disp.keysym_to_keycode(
                XK.string_to_keysym(key_name)
            )
            if not keycode:
                logger.error("Failed to resolve key: %s", key_name)
                return

            root.grab_key(keycode, mod_mask, 1, X.GrabModeAsync, X.GrabModeAsync)
            root.grab_key(keycode, mod_mask | X.Mod2Mask, 1, X.GrabModeAsync, X.GrabModeAsync)

            self._keycode = keycode
            self._modifiers = mod_mask
            self._registered = True

            logger.info("Hotkey registered: %s", hotkey)
        except Exception as e:
            logger.error("Failed to register hotkey: %s", e)

    def poll_event(self):
        if not self._registered or not self._disp:
            return False
        try:
            while self._disp.pending_events():
                event = self._disp.next_event()
                if event.type == X.KeyPress:
                    if (event.detail == self._keycode and
                            (event.state & (self._modifiers | X.Mod2Mask)) in
                            (self._modifiers, self._modifiers | X.Mod2Mask)):
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
