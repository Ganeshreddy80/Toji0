"""Reversal Strategy logic."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from market_intelligence.core.models import MarketState
from price_action.core.enums import PatternDirection, PatternType
from price_action.core.models import PatternState
from confluence.core.models import ConfluenceState
from strategy.core.enums import StrategyDecision, StrategyType
from strategy.core.models import StrategySignal


class ReversalStrategy:
    """Strategy that triggers buy/sell signals on key structural reversal zones."""

    def __init__(self, confluence_min: float = 80.0) -> None:
        self.confluence_min = confluence_min

        self.bullish_patterns = {
            PatternType.DOUBLE_BOTTOM,
            PatternType.INVERSE_HEAD_AND_SHOULDERS,
            PatternType.TRIPLE_BOTTOM,
            PatternType.DIAMOND_BOTTOM,
            PatternType.ROUNDED_BOTTOM,
        }
        self.bearish_patterns = {
            PatternType.DOUBLE_TOP,
            PatternType.HEAD_AND_SHOULDERS,
            PatternType.TRIPLE_TOP,
            PatternType.DIAMOND_TOP,
            PatternType.ROUNDED_TOP,
        }

    @property
    def strategy_type(self) -> StrategyType:
        return StrategyType.REVERSAL

    @property
    def name(self) -> str:
        return "Reversal Strategy"

    def evaluate(
        self,
        market_state: MarketState,
        pattern_state: PatternState | None,
        confluence_state: ConfluenceState | None,
    ) -> StrategySignal | None:
        """Evaluate market state for a reversal setup."""
        if confluence_state is None:
            return None

        overall_confluence = confluence_state.score.overall_score
        if overall_confluence < self.confluence_min:
            return None

        # 1. Check for CHoCH
        has_bullish_choch = any(
            choch.direction == "BEARISH_TO_BULLISH"
            for choch in market_state.choch_history
        )
        has_bearish_choch = any(
            choch.direction == "BULLISH_TO_BEARISH"
            for choch in market_state.choch_history
        )

        if not (has_bullish_choch or has_bearish_choch):
            return None

        # 2. Check for Liquidity Sweep
        swept_low = False
        swept_high = False
        if market_state.liquidity is not None:
            swept_low = getattr(market_state.liquidity, "swept_low", False) or getattr(market_state.liquidity, "low_swept", False)
            swept_high = getattr(market_state.liquidity, "swept_high", False) or getattr(market_state.liquidity, "high_swept", False)

        # 3. Check for matching Reversal Patterns
        has_bullish_pattern = False
        has_bearish_pattern = False
        quality_score = 100.0

        if pattern_state:
            patterns = pattern_state.active_patterns + pattern_state.candidate_patterns
            for p in patterns:
                if p.pattern_type in self.bullish_patterns:
                    has_bullish_pattern = True
                    if p.quality is not None:
                        quality_score = p.quality.overall_score
                elif p.pattern_type in self.bearish_patterns:
                    has_bearish_pattern = True
                    if p.quality is not None:
                        quality_score = p.quality.overall_score

        # Determine alignment
        is_bullish = has_bullish_choch and swept_low and has_bullish_pattern
        is_bearish = has_bearish_choch and swept_high and has_bearish_pattern

        if not (is_bullish or is_bearish):
            return None

        direction = PatternDirection.BULLISH if is_bullish else PatternDirection.BEARISH
        decision = StrategyDecision.BUY if is_bullish else StrategyDecision.SELL

        # Calculate confidence
        confidence = (overall_confluence * 0.7) + (quality_score * 0.3)
        confidence = max(0.0, min(100.0, confidence))

        reasoning = (
            f"Detected {'Bullish' if is_bullish else 'Bearish'} structural reversal: "
            f"CHoCH, liquidity sweep, and reversal pattern confirmed."
        )

        return StrategySignal(
            signal_id=str(uuid.uuid4()),
            symbol=market_state.symbol,
            timeframe=market_state.timeframe,
            direction=direction,
            strategy_type=StrategyType.REVERSAL,
            decision=decision,
            confidence=round(confidence, 2),
            confluence_score=round(overall_confluence, 2),
            reasoning=reasoning,
            supporting_factors=[
                "Change of Character Reversal Shift",
                "Liquidity Sweep Execution",
                "Reversal Pattern Support",
            ],
            conflicting_factors=[],
            detected_at=datetime.now(timezone.utc),
        )
