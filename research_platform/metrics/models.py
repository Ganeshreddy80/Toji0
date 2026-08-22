"""R55 Metrics & Observability Framework — models."""

from __future__ import annotations

import uuid
from enum import Enum
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MetricType(str, Enum):
    COUNTER = "COUNTER"
    GAUGE = "GAUGE"
    HISTOGRAM = "HISTOGRAM"
    SUMMARY = "SUMMARY"
    TIMER = "TIMER"


class MetricUnit(str, Enum):
    COUNT = "count"
    MILLISECONDS = "ms"
    SECONDS = "s"
    BYTES = "bytes"
    MEGABYTES = "MB"
    PERCENT = "%"
    DOLLARS = "USD"
    RATIO = "ratio"
    BPS = "bps"


class MetricPoint(BaseModel):
    """A single timestamped metric observation."""
    metric_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    value: float
    metric_type: MetricType = MetricType.GAUGE
    unit: MetricUnit = MetricUnit.COUNT
    tags: Dict[str, str] = Field(default_factory=dict)
    component: str = "TOJI"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MetricSeries(BaseModel):
    """A named series of MetricPoints."""
    name: str
    points: List[MetricPoint] = Field(default_factory=list)
    unit: MetricUnit = MetricUnit.COUNT

    def latest(self) -> Optional[MetricPoint]:
        return self.points[-1] if self.points else None

    def values(self) -> List[float]:
        return [p.value for p in self.points]


class PlatformSnapshot(BaseModel):
    """Point-in-time snapshot of core platform KPIs."""
    snapshot_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # System
    cpu_pct: float = 0.0
    memory_mb: float = 0.0
    free_disk_gb: float = 0.0
    active_threads: int = 0

    # Trading
    open_orders: int = 0
    filled_orders: int = 0
    portfolio_value: float = 0.0
    daily_pnl: float = 0.0
    drawdown_pct: float = 0.0

    # Platform
    strategy_count: int = 0
    certification_status: str = "UNKNOWN"
    uptime_sec: float = 0.0
