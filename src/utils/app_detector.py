import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


def get_active_window_app() -> str:
    session = os.environ.get("XDG_SESSION_TYPE", "x11")
    if session == "wayland":
        return _detect_wayland()
    return _detect_x11()


def _detect_x11() -> str:
    try:
        result = subprocess.run(
            ["xdotool", "getactivewindow", "getwindowpid"],
            capture_output=True, timeout=2, text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            pid = int(result.stdout.strip())
            return _pid_to_app(pid)
    except FileNotFoundError:
        pass

    try:
        result = subprocess.run(
            ["xprop", "-root", "_NET_ACTIVE_WINDOW"],
            capture_output=True, timeout=2, text=True,
        )
        if result.returncode != 0:
            return ""
        wid = result.stdout.strip().split()[-1]
        if wid == "0x0":
            return ""
        result = subprocess.run(
            ["xprop", "-id", wid, "_NET_WM_PID"],
            capture_output=True, timeout=2, text=True,
        )
        if result.returncode == 0 and "PID" in result.stdout:
            pid = int(result.stdout.split()[-1])
            return _pid_to_app(pid)
    except Exception as e:
        logger.debug("xprop detection error: %s", e)

    return ""


def _detect_wayland() -> str:
    if os.environ.get("SWAYSOCK"):
        try:
            result = subprocess.run(
                ["swaymsg", "-t", "get_tree"],
                capture_output=True, timeout=2, text=True,
            )
            if result.returncode == 0:
                return "sway"
        except FileNotFoundError:
            pass
    return ""


def _pid_to_app(pid: int) -> str:
    if HAS_PSUTIL:
        try:
            proc = psutil.Process(pid)
            return proc.name()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    try:
        comm_path = Path(f"/proc/{pid}/comm")
        if comm_path.exists():
            return comm_path.read_text().strip()
    except OSError:
        pass

    return ""
