"""R55 Metrics Orchestrator — periodic metric collection and publishing."""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

from research_platform.metrics.registry import MetricsRegistry
from research_platform.metrics.collectors import SystemMetricsCollector, TradingMetricsCollector
from research_platform.metrics.snapshot import SnapshotBuilder

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL_SEC = 15.0


class MetricsOrchestrator:
    """Periodically collects platform metrics and publishes snapshots to the EventBus."""

    def __init__(
        self,
        registry: Optional[MetricsRegistry] = None,
        interval_sec: float = DEFAULT_INTERVAL_SEC,
    ) -> None:
        self._registry = registry or MetricsRegistry()
        self._interval = interval_sec
        self._sys_collector = SystemMetricsCollector()
        self._trade_collector = TradingMetricsCollector()
        self._snapshot_builder = SnapshotBuilder()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="MetricsOrchestrator")
        self._thread.start()
        logger.info("MetricsOrchestrator started (interval=%.1fs).", self._interval)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        logger.info("MetricsOrchestrator stopped.")

    def collect_once(self) -> None:
        """Single collection cycle — useful for testing."""
        try:
            # System metrics
            for point in [
                self._sys_collector.collect_cpu(),
                self._sys_collector.collect_memory(),
                self._sys_collector.collect_disk(),
                self._sys_collector.collect_threads(),
            ]:
                self._registry.record(point)

            # Trading metrics (graceful)
            for collector_fn in [
                self._trade_collector.collect_portfolio_value,
                self._trade_collector.collect_daily_pnl,
                self._trade_collector.collect_open_orders,
            ]:
                try:
                    point = collector_fn()
                    if point:
                        self._registry.record(point)
                except Exception:
                    pass

            # Build and publish snapshot
            snapshot = self._snapshot_builder.build()
            self._publish_snapshot(snapshot)

        except Exception as e:
            logger.error("Metrics collection cycle error: %s", e)

    def get_snapshot(self):
        return self._snapshot_builder.build()

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            self.collect_once()
            self._stop_event.wait(self._interval)

    def _publish_snapshot(self, snapshot) -> None:
        try:
            from research_platform.platform.service_registry import ServiceRegistry
            from research_platform.metrics.events import SnapshotPublished
            eb = ServiceRegistry().get_service("EventBus")
            if eb:
                ev = SnapshotPublished(
                    cpu_pct=snapshot.cpu_pct,
                    memory_mb=snapshot.memory_mb,
                    certification_status=snapshot.certification_status,
                    uptime_sec=snapshot.uptime_sec,
                )
                eb.publish("MetricsSnapshot", ev.model_dump())
        except Exception:
            pass

    @property
    def registry(self) -> MetricsRegistry:
        return self._registry
