"""Dashboard API aggregating risk scores and violations counts.
"""

from __future__ import annotations

from research_platform.risk_management.models import DashboardMetrics, RiskProfile


class RiskDashboardApi:
    """Aggregates active scores and lists alerts metrics for UI layouts."""

    @staticmethod
    def compile_metrics(
        score: float,
        profile: RiskProfile,
        alerts_count: int = 0
    ) -> DashboardMetrics:
        """Construct DashboardMetrics snapshot."""
        return DashboardMetrics(
            risk_score=score,
            var_95=profile.var_report.parametric_var,
            cvar_95=profile.cvar_report.expected_shortfall,
            open_alerts_count=alerts_count
        )
