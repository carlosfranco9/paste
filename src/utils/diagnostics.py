import faulthandler
import logging
import os
import signal
import sys
import threading
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path


LOG_DIR = Path.home() / ".paste" / "logs"
LOG_PATH = LOG_DIR / "paste.log"
HANG_LOG_PATH = LOG_DIR / "hang.log"

_configured = False


def configure_logging(debug=False):
    global _configured
    if _configured:
        return LOG_PATH

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] pid=%(process)d %(threadName)s "
        "%(name)s: %(message)s"
    )
    file_handler = RotatingFileHandler(
        str(LOG_PATH),
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG if debug else logging.INFO)
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    _configured = True
    logging.getLogger(__name__).info("Logging initialized: %s", LOG_PATH)
    return LOG_PATH


def install_exception_hooks():
    logger = logging.getLogger("paste.crash")
    original_hook = sys.excepthook

    def handle_exception(exc_type, exc_value, traceback):
        logger.critical(
            "Unhandled exception",
            exc_info=(exc_type, exc_value, traceback),
        )
        original_hook(exc_type, exc_value, traceback)

    sys.excepthook = handle_exception

    if hasattr(threading, "excepthook"):
        original_thread_hook = threading.excepthook

        def handle_thread_exception(args):
            logger.critical(
                "Unhandled thread exception in %s",
                args.thread.name if args.thread else "unknown",
                exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
            )
            original_thread_hook(args)

        threading.excepthook = handle_thread_exception


class HangWatchdog:
    def __init__(self, timeout_seconds=8.0, heartbeat_ms=1000):
        self._timeout = timeout_seconds
        self._heartbeat_ms = heartbeat_ms
        self._last_heartbeat = time.monotonic()
        self._stop_event = threading.Event()
        self._reported = False
        self._thread = None
        self._timer = None
        self._hang_file = None
        self._logger = logging.getLogger("paste.watchdog")

    def start(self):
        from PySide2.QtCore import QTimer

        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self._hang_file = HANG_LOG_PATH.open("a", encoding="utf-8", buffering=1)
        faulthandler.enable(file=self._hang_file, all_threads=True)
        if hasattr(signal, "SIGUSR2"):
            faulthandler.register(
                signal.SIGUSR2,
                file=self._hang_file,
                all_threads=True,
                chain=False,
            )

        self._timer = QTimer()
        self._timer.timeout.connect(self._heartbeat)
        self._timer.start(self._heartbeat_ms)
        self._thread = threading.Thread(
            target=self._watch,
            name="ui-hang-watchdog",
            daemon=True,
        )
        self._thread.start()
        self._logger.info(
            "UI watchdog started: timeout=%.1fs hang_log=%s",
            self._timeout,
            HANG_LOG_PATH,
        )

    def _heartbeat(self):
        if self._reported:
            self._logger.warning("UI event loop recovered")
        self._reported = False
        self._last_heartbeat = time.monotonic()

    def _watch(self):
        while not self._stop_event.wait(1.0):
            delay = time.monotonic() - self._last_heartbeat
            if delay < self._timeout or self._reported:
                continue
            self._reported = True
            self._logger.critical(
                "UI event loop unresponsive for %.1fs; dumping all thread stacks",
                delay,
            )
            try:
                faulthandler.dump_traceback(file=self._hang_file, all_threads=True)
                self._hang_file.flush()
            except Exception:
                self._logger.exception("Failed to dump hang traceback")

    def stop(self):
        self._stop_event.set()
        if self._timer is not None:
            self._timer.stop()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        if hasattr(signal, "SIGUSR2"):
            try:
                faulthandler.unregister(signal.SIGUSR2)
            except Exception:
                pass
        faulthandler.disable()
        if self._hang_file is not None:
            self._hang_file.close()
            self._hang_file = None
        self._logger.info("UI watchdog stopped")
