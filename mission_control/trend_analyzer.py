"""Thread-safe System Metrics Trend & Stability Analyzer for Mission Control (Sprint 10B)."""

from __future__ import annotations

import collections
from datetime import datetime, timezone
import threading
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class TrendAnalysisSnapshot(BaseModel):
    """Immutable trend analysis result snapshot."""

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Analysis calculation timestamp.",
    )
    uptime_trend_seconds: float = Field(default=0.0, ge=0.0, description="Total system uptime in seconds.")
    alert_frequency_per_minute: float = Field(default=0.0, ge=0.0, description="Alert generation rate per minute.")
    service_stability_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Service stability rating (0.0 unhealthy to 1.0 perfectly stable).",
    )
    health_trend_ratio: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Ratio of HEALTHY services to total registered services.",
    )
    moving_average_cpu_percent: float = Field(default=0.0, ge=0.0, description="Moving average CPU utilization.")
    moving_average_memory_mb: float = Field(default=0.0, ge=0.0, description="Moving average Memory usage in MB.")
    moving_average_latency_ms: float = Field(default=0.0, ge=0.0, description="Moving average heartbeat latency in ms.")

    model_config = ConfigDict(frozen=True)


class TrendAnalyzer:
    """Thread-safe Trend Analyzer computing moving averages, alert frequencies, and service stability scores."""

    def __init__(self, window_size: int = 50) -> None:
        self._lock = threading.RLock()
        self._window_size = window_size
        self._cpu_samples: collections.deque[float] = collections.deque(maxlen=window_size)
        self._memory_samples: collections.deque[float] = collections.deque(maxlen=window_size)
        self._latency_samples: collections.deque[float] = collections.deque(maxlen=window_size)
        self._alert_timestamps: collections.deque[datetime] = collections.deque(maxlen=200)

    def record_cpu_sample(self, cpu_percent: float) -> None:
        """Record a CPU percentage sample for moving average calculation."""
        with self._lock:
            if cpu_percent >= 0.0:
                self._cpu_samples.append(cpu_percent)

    def record_memory_sample(self, memory_mb: float) -> None:
        """Record a Memory MB sample for moving average calculation."""
        with self._lock:
            if memory_mb >= 0.0:
                self._memory_samples.append(memory_mb)

    def record_latency_sample(self, latency_ms: float) -> None:
        """Record a heartbeat latency sample for moving average calculation."""
        with self._lock:
            if latency_ms >= 0.0:
                self._latency_samples.append(latency_ms)

    def record_alert_event(self, timestamp: Optional[datetime] = None) -> None:
        """Record an alert timestamp to compute alert frequency."""
        with self._lock:
            self._alert_timestamps.append(timestamp or datetime.now(timezone.utc))

    def calculate_moving_average_cpu(self) -> float:
        """Compute moving average CPU utilization percentage."""
        with self._lock:
            if not self._cpu_samples:
                return 0.0
            return sum(self._cpu_samples) / len(self._cpu_samples)

    def calculate_moving_average_memory(self) -> float:
        """Compute moving average Memory usage in MB."""
        with self._lock:
            if not self._memory_samples:
                return 0.0
            return sum(self._memory_samples) / len(self._memory_samples)

    def calculate_moving_average_latency(self) -> float:
        """Compute moving average latency in milliseconds."""
        with self._lock:
            if not self._latency_samples:
                return 0.0
            return sum(self._latency_samples) / len(self._latency_samples)

    def calculate_alert_frequency_per_minute(self) -> float:
        """Compute alert frequency per minute over recent sample window."""
        with self._lock:
            if len(self._alert_timestamps) < 2:
                return 0.0

            first_t = self._alert_timestamps[0]
            last_t = self._alert_timestamps[-1]
            elapsed_minutes = (last_t - first_t).total_seconds() / 60.0

            if elapsed_minutes <= 0.0:
                return 0.0

            return (len(self._alert_timestamps) - 1) / elapsed_minutes

    def calculate_service_stability_score(
        self,
        total_services: int,
        failed_services_count: int,
        recent_alert_count: int = 0,
    ) -> float:
        """Compute normalized stability score (0.0 to 1.0)."""
        with self._lock:
            if total_services <= 0:
                return 1.0

            healthy_count = max(0, total_services - failed_services_count)
            base_ratio = healthy_count / total_services

            # Penalty for recent alerts
            penalty = min(0.5, recent_alert_count * 0.05)
            stability = max(0.0, base_ratio - penalty)
            return round(stability, 4)

    def analyze_trends(
        self,
        uptime_seconds: float,
        total_services: int,
        failed_services_count: int,
    ) -> TrendAnalysisSnapshot:
        """Generate comprehensive TrendAnalysisSnapshot.

        All sub-calculations are inlined under this single lock acquisition to
        avoid nested RLock re-entry (M-02). Formulas are identical to the
        individual helper methods.
        """
        with self._lock:
            # Inline: calculate_moving_average_cpu
            avg_cpu = sum(self._cpu_samples) / len(self._cpu_samples) if self._cpu_samples else 0.0

            # Inline: calculate_moving_average_memory
            avg_mem = sum(self._memory_samples) / len(self._memory_samples) if self._memory_samples else 0.0

            # Inline: calculate_moving_average_latency
            avg_lat = sum(self._latency_samples) / len(self._latency_samples) if self._latency_samples else 0.0

            # Inline: calculate_alert_frequency_per_minute
            if len(self._alert_timestamps) >= 2:
                elapsed_minutes = (self._alert_timestamps[-1] - self._alert_timestamps[0]).total_seconds() / 60.0
                alert_freq = (len(self._alert_timestamps) - 1) / elapsed_minutes if elapsed_minutes > 0.0 else 0.0
            else:
                alert_freq = 0.0

            # Inline: calculate_service_stability_score
            if total_services <= 0:
                stability_score = 1.0
            else:
                healthy_count = max(0, total_services - failed_services_count)
                base_ratio = healthy_count / total_services
                penalty = min(0.5, len(self._alert_timestamps) * 0.05)
                stability_score = round(max(0.0, base_ratio - penalty), 4)

            health_ratio = (
                max(0, total_services - failed_services_count) / total_services
                if total_services > 0
                else 1.0
            )

            return TrendAnalysisSnapshot(
                timestamp=datetime.now(timezone.utc),
                uptime_trend_seconds=uptime_seconds,
                alert_frequency_per_minute=round(alert_freq, 2),
                service_stability_score=stability_score,
                health_trend_ratio=round(health_ratio, 4),
                moving_average_cpu_percent=round(avg_cpu, 2),
                moving_average_memory_mb=round(avg_mem, 2),
                moving_average_latency_ms=round(avg_lat, 2),
            )
