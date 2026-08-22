"""Trend-Following Strategy logic."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from market_intelligence.core.enums import TrendDirection
from market_intelligence.core.models import MarketState
from price_action.core.enums import PatternDirection
from price_action.core.models import PatternState
from confluence.core.models import ConfluenceState
from strategy.core.enums import StrategyDecision, StrategyType
from strategy.core.models import StrategySignal


class TrendFollowingStrategy:
    """Strategy that triggers buy/sell signals in alignment with a dominant trend."""

    def __init__(self, confluence_min: float = 75.0, quality_min: float = 70.0, conflict_max: float = 2.0) -> None:
        self.confluence_min = confluence_min
        self.quality_min = quality_min
        self.conflict_max = conflict_max

    @property
    def strategy_type(self) -> StrategyType:
        return StrategyType.TREND_FOLLOWING

    @property
    def name(self) -> str:
        return "Trend Following Strategy"

    def evaluate(
        self,
        market_state: MarketState,
        pattern_state: PatternState | None,
        confluence_state: ConfluenceState | None,
    ) -> StrategySignal | None:
        """Evaluate market state for a trend-following setup."""
        if confluence_state is None or market_state.trend is None:
            return None

        # Check confluence and conflict penalties
        overall_confluence = confluence_state.score.overall_score
        conflict_penalty = confluence_state.score.conflict_penalty
        if overall_confluence < self.confluence_min or conflict_penalty >= self.conflict_max:
            return None

        trend_dir = market_state.trend.direction
        if trend_dir == TrendDirection.SIDEWAYS:
            return None

        # Determine setup direction and required BOS direction
        is_bullish = trend_dir == TrendDirection.UP
        direction = PatternDirection.BULLISH if is_bullish else PatternDirection.BEARISH
        bos_dir_str = "UP" if is_bullish else "DOWN"

        # Check for matching BOS
        matching_bos = [bos for bos in market_state.bos_history if bos.direction == bos_dir_str]
        if not matching_bos:
            return None

        # Check for pattern quality if patterns exist
        quality_score = 100.0
        if pattern_state and (pattern_state.active_patterns or pattern_state.candidate_patterns):
            best_quality = 0.0
            patterns = pattern_state.active_patterns + pattern_state.candidate_patterns
            for p in patterns:
                if p.direction == direction and p.quality is not None:
                    best_quality = max(best_quality, p.quality.overall_score)
            
            if best_quality < self.quality_min and best_quality > 0.0:
                return None
            if best_quality > 0.0:
                quality_score = best_quality

        # Calculate strategy confidence
        trend_strength = market_state.trend.strength * 100.0
        confidence = (overall_confluence * 0.6) + (trend_strength * 0.2) + (quality_score * 0.2)
        confidence = max(0.0, min(100.0, confidence))

        reasoning = (
            f"Confirmed {'Bullish' if is_bullish else 'Bearish'} trend "
            f"with strength {trend_strength:.1f}% aligned with BOS and high confluence."
        )

        return StrategySignal(
            signal_id=str(uuid.uuid4()),
            symbol=market_state.symbol,
            timeframe=market_state.timeframe,
            direction=direction,
            strategy_type=StrategyType.TREND_FOLLOWING,
            decision=StrategyDecision.BUY if is_bullish else StrategyDecision.SELL,
            confidence=round(confidence, 2),
            confluence_score=round(overall_confluence, 2),
            reasoning=reasoning,
            supporting_factors=[
                "Trend Direction Alignment",
                "Break of Structure Confirmation",
                "High Confluence Setup",
            ],
            conflicting_factors=[],
            detected_at=datetime.now(timezone.utc),
        )
