"""Thread-safe Dashboard Renderer for Mission Control (Sprint 10B)."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import threading
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from mission_control.resource_monitor import ResourceSnapshot
from mission_control.system_monitor import ServiceRegistration
from mission_control.trend_analyzer import TrendAnalysisSnapshot

logger = logging.getLogger(__name__)


class DashboardSnapshot(BaseModel):
    """Immutable Dashboard Data Snapshot model."""

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Dashboard rendering timestamp.",
    )
    controller_state: str = Field(..., description="Controller operational state.")
    uptime_seconds: float = Field(..., ge=0.0, description="System uptime in seconds.")
    total_services: int = Field(..., ge=0, description="Total registered service count.")
    failed_services_count: int = Field(..., ge=0, description="Failed services count.")
    health_summary: Dict[str, int] = Field(default_factory=dict, description="Count per health status.")
    services: List[ServiceRegistration] = Field(default_factory=list, description="Registered service summaries.")
    active_alerts: List[Dict[str, Any]] = Field(default_factory=list, description="Active alerts list.")
    resource_usage: Optional[ResourceSnapshot] = Field(default=None, description="Resource utilization snapshot.")
    trend_analysis: Optional[TrendAnalysisSnapshot] = Field(default=None, description="Trend analysis snapshot.")
    render_time_ms: float = Field(default=0.0, ge=0.0, description="Dashboard render time in milliseconds.")

    model_config = ConfigDict(frozen=True)


class DashboardRenderer:
    """Thread-safe Dashboard Renderer generating immutable data snapshots under strict SLAs (<500ms)."""

    def __init__(self) -> None:
        self._lock = threading.RLock()

    def render_dashboard(
        self,
        controller_state: str,
        uptime_seconds: float,
        services: List[ServiceRegistration],
        health_summary: Dict[str, int],
        active_alerts: List[Dict[str, Any]],
        resource_usage: Optional[ResourceSnapshot] = None,
        trend_analysis: Optional[TrendAnalysisSnapshot] = None,
    ) -> DashboardSnapshot:
        """Render immutable DashboardSnapshot."""
        start = time.perf_counter()
        with self._lock:
            failed_count = sum(
                1 for s in services if s.health_status.value in ("UNHEALTHY", "DEGRADED")
            )

            render_elapsed_ms = (time.perf_counter() - start) * 1000.0

            return DashboardSnapshot(
                timestamp=datetime.now(timezone.utc),
                controller_state=controller_state,
                uptime_seconds=round(uptime_seconds, 2),
                total_services=len(services),
                failed_services_count=failed_count,
                health_summary=dict(health_summary),
                services=list(services),
                active_alerts=list(active_alerts),
                resource_usage=resource_usage,
                trend_analysis=trend_analysis,
                render_time_ms=round(render_elapsed_ms, 3),
            )
