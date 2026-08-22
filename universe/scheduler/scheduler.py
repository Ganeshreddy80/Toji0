"""Periodic universe scan scheduler.

Listens for SchedulerTick events from the orchestrator scheduler
and triggers full universe scans at configurable intervals.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from toji_platform.core.event_bus.interfaces import IEvent, IEventBus
from universe.core.models import UniverseConfig

logger = logging.getLogger(__name__)


class UniverseScheduler:
    """Triggers periodic universe scans.

    Integrates with the existing orchestrator scheduler by subscribing
    to SchedulerTick events. Also supports direct manual triggering.

    The scheduler does NOT run the scan itself — it calls the
    scan_callback (typically UniverseManager.run_scan).
    """

    def __init__(
        self,
        event_bus: IEventBus,
        scan_callback: callable,  # type: ignore[type-arg]
        config: UniverseConfig | None = None,
    ) -> None:
        self._event_bus = event_bus
        self._scan_callback = scan_callback
        self._config = config or UniverseConfig()
        self._last_scan: datetime | None = None
        self._scan_count = 0
        self._enabled = True

    def start(self) -> None:
        """Subscribe to scheduler tick events."""
        self._event_bus.subscribe(
            "system.scheduler_tick", self._on_tick
        )
        self._enabled = True
        logger.info(
            "Universe Scheduler: Started (interval=%ds)",
            self._config.scan_interval_seconds,
        )

    def stop(self) -> None:
        """Unsubscribe from scheduler tick events."""
        self._event_bus.unsubscribe(
            "system.scheduler_tick", self._on_tick
        )
        self._enabled = False
        logger.info("Universe Scheduler: Stopped")

    def trigger_scan(self) -> None:
        """Manually trigger a universe scan."""
        if not self._enabled:
            logger.warning("Universe Scheduler: Scan triggered but scheduler is disabled")
            return

        logger.info("Universe Scheduler: Manual scan triggered")
        self._execute_scan()

    @property
    def last_scan(self) -> datetime | None:
        """Timestamp of the last executed scan."""
        return self._last_scan

    @property
    def scan_count(self) -> int:
        """Total number of scans executed."""
        return self._scan_count

    def _on_tick(self, event: IEvent) -> None:
        """Handle incoming scheduler tick events.

        Only triggers a scan if enough time has elapsed since the last scan.
        """
        if not self._enabled:
            return

        now = datetime.now(UTC)
        if self._last_scan:
            elapsed = (now - self._last_scan).total_seconds()
            if elapsed < self._config.scan_interval_seconds:
                return  # Too soon, skip

        logger.info("Universe Scheduler: Tick triggered scan")
        self._execute_scan()

    def _execute_scan(self) -> None:
        """Execute the scan callback and update tracking state."""
        try:
            self._scan_callback()
            self._last_scan = datetime.now(UTC)
            self._scan_count += 1
            logger.info(
                "Universe Scheduler: Scan #%d completed", self._scan_count
            )
        except Exception as e:
            logger.error("Universe Scheduler: Scan failed: %s", e)
