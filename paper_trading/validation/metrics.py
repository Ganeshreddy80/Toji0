"""Operational Metrics & Telemetry Collector for Sprint 9C Paper Trading Validation."""

from __future__ import annotations

from datetime import datetime, timezone
import threading
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class OperationalMetrics(BaseModel):
    """Immutable snapshot of operational telemetry metrics."""

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Metrics snapshot creation timestamp.",
    )
    uptime_seconds: float = Field(default=0.0, ge=0.0, description="Total elapsed runtime in seconds.")
    throughput_ticks_per_sec: float = Field(default=0.0, ge=0.0, description="Current processed tick rate per second.")
    processed_ticks_count: int = Field(default=0, ge=0, description="Total processed ticks.")
    completed_candles_count: int = Field(default=0, ge=0, description="Total completed candles closed.")
    submitted_orders_count: int = Field(default=0, ge=0, description="Total paper orders submitted.")
    executed_fills_count: int = Field(default=0, ge=0, description="Total paper order fills executed.")
    reconnect_count: int = Field(default=0, ge=0, description="Total reconnection events.")
    error_count: int = Field(default=0, ge=0, description="Total recorded error/exception count.")
    peak_memory_mb: float = Field(default=0.0, ge=0.0, description="Peak memory allocation in MB.")
    avg_memory_mb: float = Field(default=0.0, ge=0.0, description="Average memory allocation in MB.")
    latency_summary: Dict[str, Dict[str, float]] = Field(
        default_factory=dict,
        description="Latency statistics summary map (average, median, p95, p99, max) per category.",
    )

    model_config = ConfigDict(frozen=True)


class MetricsCollector:
    """Thread-safe operational telemetry collector."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._start_time: datetime = datetime.now(timezone.utc)
        self._processed_ticks: int = 0
        self._completed_candles: int = 0
        self._submitted_orders: int = 0
        self._executed_fills: int = 0
        self._reconnect_count: int = 0
        self._error_count: int = 0
        self._memory_samples: List[float] = []

    def record_tick(self) -> None:
        """Increment processed ticks count."""
        with self._lock:
            self._processed_ticks += 1

    def record_candle(self) -> None:
        """Increment completed candles count."""
        with self._lock:
            self._completed_candles += 1

    def record_order(self) -> None:
        """Increment submitted orders count."""
        with self._lock:
            self._submitted_orders += 1

    def record_fill(self) -> None:
        """Increment executed fills count."""
        with self._lock:
            self._executed_fills += 1

    def record_reconnect(self) -> None:
        """Increment reconnect count."""
        with self._lock:
            self._reconnect_count += 1

    def record_error(self) -> None:
        """Increment error count."""
        with self._lock:
            self._error_count += 1

    def record_memory_sample(self, memory_mb: float) -> None:
        """Record a memory usage sample in MB."""
        with self._lock:
            if memory_mb >= 0.0:
                self._memory_samples.append(memory_mb)

    def get_uptime_seconds(self) -> float:
        """Get current elapsed runtime in seconds."""
        with self._lock:
            now = datetime.now(timezone.utc)
            return max(0.0, (now - self._start_time).total_seconds())

    def get_throughput(self) -> float:
        """Calculate current overall tick processing throughput (ticks/sec)."""
        with self._lock:
            uptime = self.get_uptime_seconds()
            if uptime <= 0.0:
                return 0.0
            return self._processed_ticks / uptime

    def reset(self) -> None:
        """Reset all counters and telemetry state."""
        with self._lock:
            self._start_time = datetime.now(timezone.utc)
            self._processed_ticks = 0
            self._completed_candles = 0
            self._submitted_orders = 0
            self._executed_fills = 0
            self._reconnect_count = 0
            self._error_count = 0
            self._memory_samples.clear()

    def get_metrics_snapshot(self, latency_summary: Optional[Dict[str, Dict[str, float]]] = None) -> OperationalMetrics:
        """Generate immutable OperationalMetrics snapshot."""
        with self._lock:
            uptime = self.get_uptime_seconds()
            throughput = self._processed_ticks / uptime if uptime > 0.0 else 0.0

            peak_mem = max(self._memory_samples) if self._memory_samples else 0.0
            avg_mem = sum(self._memory_samples) / len(self._memory_samples) if self._memory_samples else 0.0

            return OperationalMetrics(
                timestamp=datetime.now(timezone.utc),
                uptime_seconds=uptime,
                throughput_ticks_per_sec=throughput,
                processed_ticks_count=self._processed_ticks,
                completed_candles_count=self._completed_candles,
                submitted_orders_count=self._submitted_orders,
                executed_fills_count=self._executed_fills,
                reconnect_count=self._reconnect_count,
                error_count=self._error_count,
                peak_memory_mb=peak_mem,
                avg_memory_mb=avg_mem,
                latency_summary=latency_summary or {},
            )
