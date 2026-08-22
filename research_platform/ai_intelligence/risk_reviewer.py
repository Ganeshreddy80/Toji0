"""Risk Reviewer evaluating VaR budgets and leverage utilization metrics.
"""

from __future__ import annotations

from typing import List

from research_platform.ai_intelligence.models import ImprovementSuggestion, RiskReview


class RiskReviewer:
    """Reviews compliance, VaR usage, and margin safety thresholds."""

    def review_risk(
        self,
        var_utilization: float,
        leverage: float
    ) -> RiskReview:
        """Evaluate margins and list improvements suggestions."""
        lev_status = "SAFE"
        suggestions = []

        if leverage > 1.5:
            lev_status = "HIGH"
            suggestions.append(
                ImprovementSuggestion(
                    action="Reduce leverage limit",
                    rationale=f"Effective leverage {leverage:.2f} increases margin liquidation risk"
                )
            )

        if var_utilization > 0.80:
            suggestions.append(
                ImprovementSuggestion(
                    action="Reduce absolute exposure",
                    rationale=f"Value-at-Risk utilization {var_utilization:.2%} approaches daily budget caps"
                )
            )

        return RiskReview(
            var_utilization=var_utilization,
            leverage_status=lev_status,
            suggestions=suggestions
        )
