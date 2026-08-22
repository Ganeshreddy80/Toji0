"""Trade Reviewer evaluating completed trades entry timings and slippage.
"""

from __future__ import annotations

from typing import List

from research_platform.ai_intelligence.models import ImprovementSuggestion, TradeReview


class TradeReviewer:
    """Audits execution quality, entry pricing, and slippage levels."""

    def review_trade(
        self,
        trade_id: str,
        slippage_ms: float,
        entry_price: float,
        filled_price: float
    ) -> TradeReview:
        """Evaluate entry cost quality and list improvements suggestions."""
        diff = abs(filled_price - entry_price) / entry_price if entry_price > 0.0 else 0.0
        
        quality = "EXCELLENT"
        suggestions = []

        if diff > 0.01:
            quality = "POOR"
            suggestions.append(
                ImprovementSuggestion(
                    action="Use limit orders",
                    rationale="Reduce market impact and entry slippage price"
                )
            )

        if slippage_ms > 200.0:
            suggestions.append(
                ImprovementSuggestion(
                    action="Route to alternative exchange",
                    rationale="High connectivity latency detected on default exchange"
                )
            )

        return TradeReview(
            trade_id=trade_id,
            entry_quality=quality,
            exit_quality="GOOD",
            slippage_ms=slippage_ms,
            suggestions=suggestions
        )
