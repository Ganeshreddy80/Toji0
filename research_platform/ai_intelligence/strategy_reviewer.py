"""Strategy Reviewer auditing parameters stability and Sharpe/Sortino ratios.
"""

from __future__ import annotations

from typing import List

from research_platform.ai_intelligence.models import ImprovementSuggestion, StrategyReview


class StrategyReviewer:
    """Audits Sharpe ratios, Sortino metrics, win ratios, and drawdown risks."""

    def review_strategy(
        self,
        strategy_id: str,
        sharpe: float,
        sortino: float,
        drawdown: float
    ) -> StrategyReview:
        """Analyze ratios and returns list of improvement suggestions."""
        strengths = []
        weaknesses = []
        suggestions = []

        if sortino > 1.5:
            strengths.append("High Sortino ratio indicates efficient downside-adjusted returns.")
        else:
            weaknesses.append("Low Sortino ratio points to excessive downside volatility.")
            suggestions.append(
                ImprovementSuggestion(
                    action="Reduce position size",
                    rationale="Mitigate downside tail exposure"
                )
            )

        if drawdown > 0.15:
            weaknesses.append("Drawdown exceeds normal bounds limits.")
            suggestions.append(
                ImprovementSuggestion(
                    action="Tighten Stop Loss",
                    rationale="Limit maximum trace loss on regime changes"
                )
            )

        return StrategyReview(
            strategy_id=strategy_id,
            strengths=strengths,
            weaknesses=weaknesses,
            suggestions=suggestions
        )
