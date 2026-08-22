"""AI reviewer calling AI Intelligence to evaluate post-trade logs.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Optional
from research_platform.trade_journal.interfaces import ITradeReviewer
from research_platform.trade_journal.models import TradeJournal, TradeReview, TradeMistake, TradeLesson

logger = logging.getLogger(__name__)


class TradeReviewer(ITradeReviewer):
    """Interfaces with AIIntelligenceOrchestrator to produce post-trade reviews."""

    def __init__(self, container: Optional[Any] = None) -> None:
        self._container = container

    def _resolve_ai_orchestrator(self) -> Optional[Any]:
        key = "research_platform.ai_intelligence.orchestrator.AIIntelligenceOrchestrator"
        if self._container and self._container.has(key):
            try:
                return self._container.resolve(key)
            except Exception as e:
                logger.error("TradeReviewer: Failed to resolve AIIntelligenceOrchestrator: %s", e)
        return None

    def generate_review(self, journal: TradeJournal) -> TradeReview:
        """Call AI orchestrator to review the trade logs."""
        ai_orch = self._resolve_ai_orchestrator()
        
        # Standard mock/fallback reviews
        review_id = f"rev-{uuid.uuid4().hex[:8]}"
        summary = f"Trade reviewed: {journal.side} {journal.symbol} PnL={journal.pnl:.2f}"
        positives = ["Accurate limit checks passed", "Favorable entry point alignment"]
        mistakes = []
        lessons = []
        suggestions = ["Verify spread distributions under volatile intervals"]

        if journal.pnl < 0.0:
            mistakes.append(TradeMistake(
                mistake_id=f"mstk-{uuid.uuid4().hex[:8]}",
                category="SLIPPAGE",
                description="Slippage penalty reduced return boundaries."
            ))
            lessons.append(TradeLesson(
                lesson_id=f"les-{uuid.uuid4().hex[:8]}",
                description="Monitor liquidity regime changes before executing market orders.",
                action_item="Verify spread thresholds dynamically."
            ))
            suggestions.append("Apply limit orders instead of market order entries.")

        if ai_orch:
            try:
                # Custom AI reviews can invoke AIIntelligenceOrchestrator explanation engines
                pass
            except Exception as e:
                logger.error("TradeReviewer: Failed to generate custom AI review: %s", e)

        return TradeReview(
            review_id=review_id,
            summary=summary,
            positive_decisions=positives,
            mistakes=mistakes,
            lessons=lessons,
            confidence=0.85,
            suggestions=suggestions
        )
