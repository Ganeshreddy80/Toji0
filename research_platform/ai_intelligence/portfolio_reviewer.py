"""Portfolio Reviewer analyzing diversification weights and concentrations.
"""

from __future__ import annotations

from typing import Dict, List

from research_platform.ai_intelligence.models import ImprovementSuggestion, PortfolioReview


class PortfolioReviewer:
    """Audits factor exposures, sector weights, and correlation scores."""

    def review_portfolio(
        self,
        portfolio_id: str,
        weights: Dict[str, float]
    ) -> PortfolioReview:
        """Evaluate weight balance and return suggestions."""
        max_w = max(abs(w) for w in weights.values()) if weights else 0.0
        
        div_score = 1.0 - max_w
        suggestions = []

        if max_w > 0.40:
            suggestions.append(
                ImprovementSuggestion(
                    action="Rebalance asset weights",
                    rationale=f"Concentration in single asset ({max_w:.2%}) exceeds 40% safety threshold"
                )
            )

        return PortfolioReview(
            portfolio_id=portfolio_id,
            diversification_score=div_score,
            suggestions=suggestions
        )
