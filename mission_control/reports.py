"""Immutable Monitoring Report Models & Generator for Mission Control (Sprint 10B)."""

from __future__ import annotations

from datetime import datetime, timezone
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from mission_control.resource_monitor import ResourceSnapshot
from mission_control.system_monitor import ServiceRegistration
from mission_control.trend_analyzer import TrendAnalysisSnapshot


class SystemStatusReport(BaseModel):
    """Immutable comprehensive system monitoring report model."""

    report_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique report UUID identifier.",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Report generation timestamp.",
    )
    controller_state: str = Field(..., description="Mission Control controller state.")
    uptime_seconds: float = Field(..., ge=0.0, description="Total system uptime in seconds.")
    total_services_count: int = Field(..., ge=0, description="Total registered services.")
    failed_services_count: int = Field(..., ge=0, description="Currently failed or degraded services count.")
    health_summary: Dict[str, int] = Field(default_factory=dict, description="Count per health status state.")
    services: List[ServiceRegistration] = Field(default_factory=list, description="List of registered service details.")
    resource_usage: Optional[ResourceSnapshot] = Field(default=None, description="Current resource usage snapshot.")
    trend_analysis: Optional[TrendAnalysisSnapshot] = Field(default=None, description="Trend analysis snapshot.")
    active_alerts_count: int = Field(default=0, ge=0, description="Active alerts count.")
    recent_alerts: List[Dict[str, Any]] = Field(default_factory=list, description="List of recent alert records.")
    warnings: List[str] = Field(default_factory=list, description="Operational warnings.")
    recommendations: List[str] = Field(default_factory=list, description="Operational recommendations.")

    model_config = ConfigDict(frozen=True)


class ReportGenerator:
    """Builder generating immutable SystemStatusReport instances."""

    @staticmethod
    def build_report(
        controller_state: str,
        uptime_seconds: float,
        services: List[ServiceRegistration],
        health_summary: Dict[str, int],
        failed_services: List[str],
        resource_usage: Optional[ResourceSnapshot] = None,
        trend_analysis: Optional[TrendAnalysisSnapshot] = None,
        recent_alerts: Optional[List[Dict[str, Any]]] = None,
        warnings: Optional[List[str]] = None,
        recommendations: Optional[List[str]] = None,
    ) -> SystemStatusReport:
        """Build an immutable SystemStatusReport."""
        warns = list(warnings or [])
        recs = list(recommendations or [])
        alerts = list(recent_alerts or [])

        if failed_services:
            warns.append(f"{len(failed_services)} service(s) currently degraded or failed: {', '.join(failed_services)}")
            recs.append("Inspect failed service logs and execute service recovery procedures.")

        if resource_usage and resource_usage.cpu_percent > 80.0:
            warns.append(f"High CPU utilization detected ({resource_usage.cpu_percent:.1f}%).")
            recs.append("Consider scaling infrastructure or balancing service workloads.")

        if trend_analysis and trend_analysis.service_stability_score < 0.7:
            warns.append(f"Service stability score is low ({trend_analysis.service_stability_score:.2f}).")
            recs.append("Investigate recurring heartbeat timeouts or service restart loops.")

        if not recs:
            recs.append("All services and resources are operating within nominal thresholds.")

        return SystemStatusReport(
            controller_state=controller_state,
            uptime_seconds=uptime_seconds,
            total_services_count=len(services),
            failed_services_count=len(failed_services),
            health_summary=health_summary,
            services=services,
            resource_usage=resource_usage,
            trend_analysis=trend_analysis,
            active_alerts_count=len(alerts),
            recent_alerts=alerts,
            warnings=warns,
            recommendations=recs,
        )

    @staticmethod
    def export_report_json(report: SystemStatusReport) -> str:
        """Export SystemStatusReport as formatted JSON string."""
        return report.model_dump_json(indent=2)
