"""Immutable Validation Report Generator for Sprint 9C Paper Trading Validation."""

from __future__ import annotations

from datetime import datetime, timezone
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from paper_trading.validation.metrics import OperationalMetrics


class ValidationReport(BaseModel):
    """Immutable validation summary report model."""

    report_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique report UUID.")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Report generation timestamp.",
    )
    simulation_name: str = Field(..., description="Target simulation/endurance test name.")
    duration_seconds: float = Field(..., ge=0.0, description="Configured simulation duration in seconds.")
    passed: bool = Field(..., description="Overall validation pass/fail result flag.")
    warnings: List[str] = Field(default_factory=list, description="List of recorded operational warnings.")
    recommendations: List[str] = Field(default_factory=list, description="List of operational recommendations.")
    statistics: Dict[str, Any] = Field(default_factory=dict, description="Summary statistics dict.")
    metrics: Optional[OperationalMetrics] = Field(default=None, description="Operational telemetry snapshot.")

    model_config = ConfigDict(frozen=True)


class ReportGenerator:
    """Immutable validation report builder and exporter."""

    @staticmethod
    def build_report(
        simulation_name: str,
        duration_seconds: float,
        passed: bool,
        metrics: Optional[OperationalMetrics] = None,
        statistics: Optional[Dict[str, Any]] = None,
        warnings: Optional[List[str]] = None,
        recommendations: Optional[List[str]] = None,
    ) -> ValidationReport:
        """Build an immutable ValidationReport."""
        warns = list(warnings or [])
        recs = list(recommendations or [])
        stats = dict(statistics or {})

        if metrics and metrics.error_count > 0:
            warns.append(f"Recorded {metrics.error_count} operational errors during test execution.")

        if metrics and metrics.reconnect_count > 0:
            warns.append(f"Recorded {metrics.reconnect_count} feed reconnection events.")

        if not recs:
            if passed:
                recs.append("System validated successfully under sustained load.")
            else:
                recs.append("Review error logs and memory growth metrics to resolve failures.")

        return ValidationReport(
            simulation_name=simulation_name,
            duration_seconds=duration_seconds,
            passed=passed,
            warnings=warns,
            recommendations=recs,
            statistics=stats,
            metrics=metrics,
        )

    @staticmethod
    def export_report_json(report: ValidationReport) -> str:
        """Export ValidationReport as formatted JSON string."""
        return report.model_dump_json(indent=2)
