"""Incremental trigger scheduler for feature updates.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Dict, List

from research_platform.feature_platform.interfaces import IFeatureScheduler

logger = logging.getLogger(__name__)


class FeatureScheduler(IFeatureScheduler):
    """Schedules background recalculation loops based on frequency profiles."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._schedules: Dict[str, List[str]] = {}
        self._running = False
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def schedule(self, trigger_type: str, interval_sec: int, names: List[str]) -> None:
        """Setup trigger rules for a list of features."""
        with self._lock:
            self._schedules[trigger_type] = list(names)
            logger.info("Scheduled features %s on trigger profile '%s'", names, trigger_type)

    def start(self, callback: Callable[[List[str]], None]) -> None:
        """Start the background scheduler loop thread."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run_loop,
                args=(callback,),
                daemon=True,
                name="FeatureSchedulerLoop"
            )
            self._thread.start()
            logger.info("Feature Scheduler thread started ✓")

    def stop(self) -> None:
        """Stop the background scheduler loop."""
        with self._lock:
            self._running = False
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            logger.info("Feature Scheduler thread stopped ✓")

    def _run_loop(self, callback: Callable[[List[str]], None]) -> None:
        """Simple tick evaluation loop running in a background thread."""
        ticks = 0
        while True:
            with self._lock:
                if not self._running:
                    break
            
            ticks += 1
            # Run scheduled minute updates every 60 seconds (simulated as ticks here)
            if self._stop_event.wait(1.0):
                break
            
            # Simple demonstration trigger
            if ticks % 5 == 0:
                with self._lock:
                    minute_feats = self._schedules.get("minute", [])
                if minute_feats:
                    try:
                        callback(minute_feats)
                    except Exception as e:
                        logger.error("Error executing scheduled feature callbacks: %s", e)
