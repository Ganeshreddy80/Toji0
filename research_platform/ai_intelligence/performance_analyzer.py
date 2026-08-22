"""Performance Analyzer compiling equity diagnostics and rolling summary.
"""

from __future__ import annotations

from research_platform.ai_intelligence.models import PerformanceSummary


class PerformanceAnalyzer:
    """Summarizes rolling metrics and ranks strategy Sharpe scores."""

    def compile_diagnostics(
        self,
        cagr: float,
        sharpe: float,
        sortino: float
    ) -> PerformanceSummary:
        """Construct PerformanceSummary diagnostics."""
        return PerformanceSummary(
            cagr=cagr,
            sharpe=sharpe,
            sortino=sortino
        )
