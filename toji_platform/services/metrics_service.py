"""Metrics Service — continuously collects system and platform metrics.

Runs a background collection thread that samples CPU, memory, event
throughput, thread count, plugin health, and portfolio statistics.
Maintains a rolling window of snapshots for historical queries.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Optional

from toji_platform.core.lifecycle.interfaces import IHealthCheck, ILifecycle
from toji_platform.core.types import HealthStatus

logger = logging.getLogger(__name__)


class MetricsSnapshot:
    """Single point-in-time metrics sample."""

    __slots__ = (
        "timestamp", "cpu_percent", "memory_mb", "memory_rss_mb",
        "event_throughput", "active_threads", "plugin_health",
        "reconnect_counts", "latency_p50_ms", "latency_p95_ms",
        "latency_p99_ms", "portfolio_value", "total_realized_pnl",
        "total_unrealized_pnl", "open_positions", "events_total",
    )

    def __init__(self, **kwargs: Any) -> None:
        for slot in self.__slots__:
            setattr(self, slot, kwargs.get(slot, 0.0))

    def to_dict(self) -> dict[str, Any]:
        result = {}
        for s in self.__slots__:
            val = getattr(self, s)
            if isinstance(val, datetime):
                result[s] = val.isoformat()
            else:
                result[s] = val
        return result


class MetricsService(ILifecycle, IHealthCheck):
    """Collects system and platform metrics at a configurable interval.

    Metrics are stored in a rolling deque (default: 720 snapshots = 1 hour at 5s).
    """

    def __init__(
        self,
        collection_interval: float = 5.0,
        max_history: int = 720,
        container: Any = None,
    ) -> None:
        self._interval = collection_interval
        self._max_history = max_history
        self._container = container

        self._history: deque[MetricsSnapshot] = deque(maxlen=max_history)
        self._lock = threading.Lock()
        self._running = False
        self._shutdown_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._start_time: Optional[datetime] = None
        self._collection_count = 0

    # ── ILifecycle ─────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return "Metrics Service"

    def start(self) -> None:
        """Start the background metrics collection thread."""
        if self._running:
            return
        self._running = True
        self._shutdown_event.clear()
        self._start_time = datetime.now(timezone.utc)
        self._thread = threading.Thread(
            target=self._collection_loop, daemon=True, name="MetricsService"
        )
        self._thread.start()
        logger.info(
            "Metrics Service started ✓ (interval=%.1fs, max_history=%d)",
            self._interval,
            self._max_history,
        )

    def stop(self) -> None:
        """Stop metrics collection."""
        self._running = False
        self._shutdown_event.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
        logger.info(
            "Metrics Service stopped ✓ (%d snapshots collected)",
            self._collection_count,
        )

    # ── IHealthCheck ───────────────────────────────────────────────────

    def check_health(self) -> HealthStatus:
        if not self._running:
            return HealthStatus.UNHEALTHY
        if self._collection_count == 0:
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY

    # ── Public API ─────────────────────────────────────────────────────

    def get_current(self) -> dict[str, Any]:
        """Return the most recent metrics snapshot."""
        with self._lock:
            if self._history:
                return self._history[-1].to_dict()
        return {}

    def get_history(self, count: Optional[int] = None) -> list[dict[str, Any]]:
        """Return recent metrics history.

        Args:
            count: Max number of snapshots to return (default: all).
        """
        with self._lock:
            snapshots = list(self._history)
        if count is not None:
            snapshots = snapshots[-count:]
        return [s.to_dict() for s in snapshots]

    def get_summary(self) -> dict[str, Any]:
        """Return aggregated summary of metrics over the rolling window."""
        with self._lock:
            snapshots = list(self._history)

        if not snapshots:
            return {
                "uptime_seconds": 0,
                "collection_count": 0,
                "avg_cpu_percent": 0.0,
                "avg_memory_mb": 0.0,
                "peak_memory_mb": 0.0,
                "avg_event_throughput": 0.0,
                "avg_latency_p99_ms": 0.0,
            }

        uptime = 0.0
        if self._start_time:
            uptime = (datetime.now(timezone.utc) - self._start_time).total_seconds()

        cpu_vals = [s.cpu_percent for s in snapshots if isinstance(s.cpu_percent, (int, float))]
        mem_vals = [s.memory_mb for s in snapshots if isinstance(s.memory_mb, (int, float))]
        throughput_vals = [s.event_throughput for s in snapshots if isinstance(s.event_throughput, (int, float))]
        latency_vals = [s.latency_p99_ms for s in snapshots if isinstance(s.latency_p99_ms, (int, float))]

        return {
            "uptime_seconds": round(uptime, 1),
            "collection_count": self._collection_count,
            "avg_cpu_percent": round(sum(cpu_vals) / len(cpu_vals), 2) if cpu_vals else 0.0,
            "avg_memory_mb": round(sum(mem_vals) / len(mem_vals), 2) if mem_vals else 0.0,
            "peak_memory_mb": round(max(mem_vals), 2) if mem_vals else 0.0,
            "avg_event_throughput": round(sum(throughput_vals) / len(throughput_vals), 2) if throughput_vals else 0.0,
            "avg_latency_p99_ms": round(sum(latency_vals) / len(latency_vals), 2) if latency_vals else 0.0,
        }

    # ── Internal ───────────────────────────────────────────────────────

    def _collection_loop(self) -> None:
        """Background loop that collects metrics snapshots."""
        while self._running:
            try:
                snapshot = self._collect()
                with self._lock:
                    self._history.append(snapshot)
                self._collection_count += 1
            except Exception as exc:
                logger.error("Metrics collection failed: %s", exc)
            if self._shutdown_event.wait(self._interval):
                break

    def _collect(self) -> MetricsSnapshot:
        """Collect a single metrics snapshot."""
        import resource

        # CPU — use os.times() for process CPU
        times = os.times()
        cpu_percent = round((times.user + times.system) * 100.0 / max(times.elapsed, 0.01), 2)

        # Memory
        rusage = resource.getrusage(resource.RUSAGE_SELF)
        # maxrss is in bytes on macOS, KB on Linux
        import sys
        if sys.platform == "darwin":
            memory_rss_mb = rusage.ru_maxrss / (1024 * 1024)
        else:
            memory_rss_mb = rusage.ru_maxrss / 1024

        # Thread count
        active_threads = threading.active_count()

        # Event bus metrics
        event_throughput = 0.0
        events_total = 0
        latency_p50 = 0.0
        latency_p95 = 0.0
        latency_p99 = 0.0

        if self._container is not None:
            try:
                from toji_platform.core.event_bus.interfaces import IEventBus
                if self._container.has(IEventBus):
                    bus = self._container.resolve(IEventBus)
                    timeline = bus.get_timeline() if hasattr(bus, "get_timeline") else []
                    events_total = len(timeline)
                    if timeline:
                        latencies = sorted([
                            e.get("processing_latency_ms", 0.0)
                            for e in timeline
                            if isinstance(e.get("processing_latency_ms"), (int, float))
                        ])
                        if latencies:
                            latency_p50 = latencies[len(latencies) // 2]
                            latency_p95 = latencies[int(len(latencies) * 0.95)]
                            latency_p99 = latencies[int(len(latencies) * 0.99)]

                        # Throughput: events in last interval
                        now = datetime.now(timezone.utc)
                        recent = [
                            e for e in timeline
                            if self._parse_ts(e.get("timestamp")) is not None
                            and (now - self._parse_ts(e.get("timestamp"))).total_seconds() < self._interval
                        ]
                        event_throughput = len(recent) / self._interval if recent else 0.0
            except Exception:
                pass

        # Plugin health
        plugin_health: dict[str, str] = {}
        if self._container is not None:
            try:
                from toji_platform.core.plugin_manager.interfaces import IPluginManager
                if self._container.has(IPluginManager):
                    pm = self._container.resolve(IPluginManager)
                    for pid, status in pm.health_check_all().items():
                        plugin_health[str(pid)] = status.value
            except Exception:
                pass

        # Portfolio stats
        portfolio_value = 0.0
        total_realized = 0.0
        total_unrealized = 0.0
        open_positions = 0

        if self._container is not None:
            try:
                from portfolio_engine.core.state import PortfolioStateStore
                if self._container.has(PortfolioStateStore):
                    store = self._container.resolve(PortfolioStateStore)
                    snap = store.get_current_snapshot()
                    portfolio_value = snap.metrics.portfolio_value
                    total_realized = snap.metrics.total_realized_pnl
                    total_unrealized = snap.metrics.total_unrealized_pnl
                    open_positions = len(snap.positions)
            except Exception:
                pass

        return MetricsSnapshot(
            timestamp=datetime.now(timezone.utc),
            cpu_percent=cpu_percent,
            memory_mb=round(memory_rss_mb, 2),
            memory_rss_mb=round(memory_rss_mb, 2),
            event_throughput=round(event_throughput, 2),
            active_threads=active_threads,
            plugin_health=plugin_health,
            reconnect_counts=0,
            latency_p50_ms=round(latency_p50, 3),
            latency_p95_ms=round(latency_p95, 3),
            latency_p99_ms=round(latency_p99, 3),
            portfolio_value=portfolio_value,
            total_realized_pnl=total_realized,
            total_unrealized_pnl=total_unrealized,
            open_positions=open_positions,
            events_total=events_total,
        )

    @staticmethod
    def _parse_ts(ts_str: Any) -> Optional[datetime]:
        """Safely parse an ISO timestamp string."""
        if not ts_str or not isinstance(ts_str, str):
            return None
        try:
            return datetime.fromisoformat(ts_str)
        except (ValueError, TypeError):
            return None
