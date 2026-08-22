"""Continuous Scheduler executing timed loop intervals.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, List, Optional

from research_platform.live_trading.interfaces import ISessionScheduler

logger = logging.getLogger(__name__)


class ContinuousScheduler(ISessionScheduler):
    """Executes background loop timers without blocking main thread."""

    def __init__(self, interval_seconds: float = 1.0) -> None:
        self.interval_seconds = interval_seconds
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._tasks: List[Callable[[], None]] = []
        self._stop_event = threading.Event()

    def register_task(self, task: Callable[[], None]) -> None:
        self._tasks.append(task)

    def start_scheduler(self) -> None:
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("Continuous Scheduler started.")

    def stop_scheduler(self) -> None:
        self._running = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        logger.info("Continuous Scheduler stopped.")

    def _run_loop(self) -> None:
        while self._running:
            for task in self._tasks:
                try:
                    task()
                except Exception as e:
                    logger.error("Error executing scheduler task: %s", e)
            if self._stop_event.wait(self.interval_seconds):
                break
