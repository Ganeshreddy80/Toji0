"""Thread-safe Operational Automation Telemetry Metrics Collector for Mission Control (Sprint 10C)."""

from __future__ import annotations

from datetime import datetime, timezone
import threading
from typing import Dict
from pydantic import BaseModel, ConfigDict, Field


class AutomationMetricsSnapshot(BaseModel):
    """Immutable snapshot of operational automation metrics."""

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Snapshot timestamp.",
    )
    recovery_count: int = Field(default=0, ge=0, description="Total recovery attempts initiated.")
    successful_recoveries_count: int = Field(default=0, ge=0, description="Successful recovery count.")
    failed_recoveries_count: int = Field(default=0, ge=0, description="Failed recovery count.")
    restart_count: int = Field(default=0, ge=0, description="Total restart count.")
    maintenance_count: int = Field(default=0, ge=0, description="Scheduled maintenance executions count.")
    escalations_count: int = Field(default=0, ge=0, description="Total incidents escalated.")

    model_config = ConfigDict(frozen=True)


class AutomationMetricsCollector:
    """Thread-safe collector for operational automation counters and telemetry."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._recovery_count: int = 0
        self._successful_recoveries: int = 0
        self._failed_recoveries: int = 0
        self._restart_count: int = 0
        self._maintenance_count: int = 0
        self._escalations_count: int = 0

    def record_recovery_attempt(self) -> None:
        """Increment total recovery attempt counter."""
        with self._lock:
            self._recovery_count += 1

    def record_recovery_success(self) -> None:
        """Increment successful recovery counter."""
        with self._lock:
            self._successful_recoveries += 1

    def record_recovery_failure(self) -> None:
        """Increment failed recovery counter."""
        with self._lock:
            self._failed_recoveries += 1

    def record_restart(self) -> None:
        """Increment restart counter."""
        with self._lock:
            self._restart_count += 1

    def record_maintenance(self) -> None:
        """Increment maintenance counter."""
        with self._lock:
            self._maintenance_count += 1

    def record_escalation(self) -> None:
        """Increment escalation counter."""
        with self._lock:
            self._escalations_count += 1

    def get_snapshot(self) -> AutomationMetricsSnapshot:
        """Generate immutable AutomationMetricsSnapshot under lock."""
        with self._lock:
            return AutomationMetricsSnapshot(
                timestamp=datetime.now(timezone.utc),
                recovery_count=self._recovery_count,
                successful_recoveries_count=self._successful_recoveries,
                failed_recoveries_count=self._failed_recoveries,
                restart_count=self._restart_count,
                maintenance_count=self._maintenance_count,
                escalations_count=self._escalations_count,
            )

    def reset(self) -> None:
        """Reset all metrics counters to zero."""
        with self._lock:
            self._recovery_count = 0
            self._successful_recoveries = 0
            self._failed_recoveries = 0
            self._restart_count = 0
            self._maintenance_count = 0
            self._escalations_count = 0
