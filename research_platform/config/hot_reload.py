"""R51 Hot reload helper.
"""

from __future__ import annotations

import os
import logging
import threading
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class ConfigHotReloader:
    """Monitors configurations files modifications, executing reloads."""

    def __init__(self, file_path: str, callback: Callable[[], None], interval_sec: float = 2.0) -> None:
        self.file_path = file_path
        self.callback = callback
        self.interval_sec = interval_sec
        self._last_modified: float = self._get_mtime()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def _get_mtime(self) -> float:
        if os.path.exists(self.file_path):
            try:
                return os.path.getmtime(self.file_path)
            except Exception:
                pass
        return 0.0

    def start(self) -> None:
        """Start background monitoring thread."""
        if self._thread:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_monitor, name="TOJI_Config_HotReload", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop background thread."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _run_monitor(self) -> None:
        while not self._stop_event.is_set():
            if self._stop_event.wait(self.interval_sec):
                break
            current_mtime = self._get_mtime()
            if current_mtime > self._last_modified:
                logger.info("Configuration file update detected: %s. Triggering reload callback...", self.file_path)
                self._last_modified = current_mtime
                try:
                    self.callback()
                except Exception as e:
                    logger.error("Error executing reload callback: %s", e)
