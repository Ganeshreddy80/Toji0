"""Runtime execution status, configuration, and loop metric models.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, Any
from pydantic import BaseModel, Field


class RuntimeStatus(str, Enum):
    """Execution status states of the Runtime Engine."""
    BOOTING = "BOOTING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"
    SHUTTING_DOWN = "SHUTTING_DOWN"


class LoopMetrics(BaseModel):
    """Execution latency and component telemetry metrics."""
    loop_latency_ms: float = 0.0
    cpu_time_ms: float = 0.0
    memory_mb: float = 0.0
    event_count: int = 0
    recovery_count: int = 0
    execution_times_ms: Dict[str, float] = Field(default_factory=dict)


class SubsystemHealth(BaseModel):
    """Heartbeat telemetry check of single subsystem loop component."""
    name: str
    status: str  # HEALTHY, DEGRADED, FAILED
    error_count: int = 0
    last_run_success: bool = True
