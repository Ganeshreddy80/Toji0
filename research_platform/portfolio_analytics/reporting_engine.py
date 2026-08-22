"""Reporting engine compiling daily/weekly summaries and formatted reports.
"""

from __future__ import annotations

import json
from research_platform.portfolio_analytics.interfaces import IReportingEngine
from research_platform.portfolio_analytics.models import PortfolioAnalyticsReport


class ReportingEngine(IReportingEngine):
    """Compiles daily, strategy, and risk adjusted return formats."""

    def compile_report(self, report: PortfolioAnalyticsReport) -> str:
        """Format the report into JSON text representation."""
        # Clean serialization output
        data = {
            "report_id": report.report_id,
            "generated_at": report.generated_at.isoformat(),
            "total_return_pct": report.returns.total_return * 100.0,
            "cagr_pct": report.returns.cagr * 100.0,
            "sharpe_ratio": report.risk_metrics.sharpe_ratio,
            "sortino_ratio": report.risk_metrics.sortino_ratio,
            "max_drawdown_pct": report.drawdown.max_drawdown * 100.0,
            "attributions": [
                {
                    "strategy_id": a.strategy_id,
                    "contribution_pnl": a.contribution_pnl
                }
                for a in report.attributions
            ]
        }
        return json.dumps(data, indent=2)
