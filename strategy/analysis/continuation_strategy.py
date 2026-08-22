"""Continuation Strategy logic."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from market_intelligence.core.enums import TrendDirection
from market_intelligence.core.models import MarketState
from price_action.core.enums import PatternDirection, PatternType
from price_action.core.models import PatternState
from confluence.core.models import ConfluenceState
from strategy.core.enums import StrategyDecision, StrategyType
from strategy.core.models import StrategySignal


class ContinuationStrategy:
    """Strategy that triggers buy/sell signals on continuation pattern validations."""

    def __init__(self, confluence_min: float = 70.0) -> None:
        self.confluence_min = confluence_min

        self.continuation_patterns = {
            PatternType.BULL_FLAG,
            PatternType.BEAR_FLAG,
            PatternType.PENNANT,
            PatternType.CUP_AND_HANDLE,
            PatternType.RECTANGLE,
            PatternType.ASC_TRIANGLE,
            PatternType.DESC_TRIANGLE,
            PatternType.SYMMETRIC_TRIANGLE,
        }

    @property
    def strategy_type(self) -> StrategyType:
        return StrategyType.CONTINUATION

    @property
    def name(self) -> str:
        return "Continuation Strategy"

    def evaluate(
        self,
        market_state: MarketState,
        pattern_state: PatternState | None,
        confluence_state: ConfluenceState | None,
    ) -> StrategySignal | None:
        """Evaluate market state for a continuation setup."""
        if confluence_state is None or market_state.trend is None:
            return None

        overall_confluence = confluence_state.score.overall_score
        if overall_confluence < self.confluence_min:
            return None

        # 1. Check for Active Continuation Pattern
        matching_pattern = None
        if pattern_state:
            patterns = pattern_state.active_patterns + pattern_state.candidate_patterns
            for p in patterns:
                if p.pattern_type in self.continuation_patterns:
                    matching_pattern = p
                    break

        if not matching_pattern:
            return None

        direction = matching_pattern.direction
        is_bullish = direction == PatternDirection.BULLISH

        # 2. Check for Trend Alignment
        trend_dir = market_state.trend.direction
        is_aligned = False
        if is_bullish and trend_dir == TrendDirection.UP:
            is_aligned = True
        elif not is_bullish and trend_dir == TrendDirection.DOWN:
            is_aligned = True

        if not is_aligned:
            return None

        # Calculate confidence
        quality_score = matching_pattern.quality.overall_score if matching_pattern.quality else 100.0
        confidence = (overall_confluence * 0.6) + (quality_score * 0.4)
        confidence = max(0.0, min(100.0, confidence))

        reasoning = (
            f"Confirmed {'Bullish' if is_bullish else 'Bearish'} continuation: "
            f"{matching_pattern.pattern_type.name} aligns with dominant trend."
        )

        return StrategySignal(
            signal_id=str(uuid.uuid4()),
            symbol=market_state.symbol,
            timeframe=market_state.timeframe,
            direction=direction,
            strategy_type=StrategyType.CONTINUATION,
            decision=StrategyDecision.BUY if is_bullish else StrategyDecision.SELL,
            confidence=round(confidence, 2),
            confluence_score=round(overall_confluence, 2),
            reasoning=reasoning,
            supporting_factors=[
                "Continuation Pattern Match",
                "Trend Alignment Verified",
            ],
            conflicting_factors=[],
            detected_at=datetime.now(timezone.utc),
        )
