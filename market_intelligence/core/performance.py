"""Performance Monitor for measuring processing latency, throughput, and memory metrics."""

from __future__ import annotations

import logging
import time
import tracemalloc
from datetime import datetime, timezone
import uuid

from market_intelligence.core.models import PerformanceReport

logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """Tracks latency metrics (mean, p99), throughput (events/sec), and memory utilization."""

    def __init__(self, track_memory: bool = False) -> None:
        self._track_memory = track_memory
        self._latencies: list[float] = []
        self._start_time = datetime.now(timezone.utc)
        self._total_candles = 0
        self._total_events = 0

        if self._track_memory:
            if not tracemalloc.is_tracing():
                tracemalloc.start()

    def record_candle_processed(self, latency_ms: float) -> None:
        """Record candle processing latency and increment candle counter."""
        self._latencies.append(latency_ms)
        self._total_candles += 1

    def record_event_published(self) -> None:
        """Record an event publication event to compute throughput."""
        self._total_events += 1

    def get_report(self, symbol: str = "") -> PerformanceReport:
        """Generate and return a performance report snapshot."""
        # Latency calculations
        if self._latencies:
            mean_latency = sum(self._latencies) / len(self._latencies)
            sorted_latencies = sorted(self._latencies)
            p99_idx = int(len(sorted_latencies) * 0.99)
            p99_latency = sorted_latencies[min(p99_idx, len(sorted_latencies) - 1)]
        else:
            mean_latency = 0.0
            p99_latency = 0.0

        # Throughput calculations
        elapsed_sec = (datetime.now(timezone.utc) - self._start_time).total_seconds()
        events_per_sec = self._total_events / max(1.0, elapsed_sec)

        # Memory usage
        memory_usage_mb = 0.0
        if self._track_memory:
            try:
                current, _ = tracemalloc.get_traced_memory()
                memory_usage_mb = current / (1024 * 1024)
            except Exception as e:
                logger.error("Failed to get traced memory usage: %s", e)

        return PerformanceReport(
            report_id=str(uuid.uuid4()),
            symbol=symbol,
            mean_latency_ms=mean_latency,
            p99_latency_ms=p99_latency,
            events_per_sec=events_per_sec,
            memory_usage_mb=memory_usage_mb,
            total_candles=self._total_candles,
            timestamp=datetime.now(timezone.utc),
        )

    def reset(self) -> None:
        """Reset internal performance metrics."""
        self._latencies.clear()
        self._start_time = datetime.now(timezone.utc)
        self._total_candles = 0
        self._total_events = 0
        if self._track_memory and tracemalloc.is_tracing():
            tracemalloc.reset_peak()
