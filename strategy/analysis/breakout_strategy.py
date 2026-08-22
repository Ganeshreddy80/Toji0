"""Breakout Strategy logic."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from market_intelligence.core.models import MarketState
from price_action.core.enums import PatternDirection, PatternStatus
from price_action.core.models import PatternState
from confluence.core.models import ConfluenceState
from strategy.core.enums import StrategyDecision, StrategyType
from strategy.core.models import StrategySignal


class BreakoutStrategy:
    """Strategy that triggers buy/sell signals on high volume breakouts."""

    def __init__(self, rvol_min: float = 1.5, confluence_min: float = 70.0) -> None:
        self.rvol_min = rvol_min
        self.confluence_min = confluence_min

    @property
    def strategy_type(self) -> StrategyType:
        return StrategyType.BREAKOUT

    @property
    def name(self) -> str:
        return "Breakout Strategy"

    def evaluate(
        self,
        market_state: MarketState,
        pattern_state: PatternState | None,
        confluence_state: ConfluenceState | None,
    ) -> StrategySignal | None:
        """Evaluate market state for a breakout setup."""
        if confluence_state is None:
            return None

        overall_confluence = confluence_state.score.overall_score
        if overall_confluence < self.confluence_min:
            return None

        # 1. Check for Volume Expansion
        rvol = 1.0
        if market_state.volume is not None:
            rvol = getattr(market_state.volume, "relative_volume", None) or getattr(market_state.volume, "normalized_volume", 1.0)

        if rvol < self.rvol_min:
            return None

        # 2. Check for Confirmed Breakout Patterns
        confirmed_pattern = None
        if pattern_state:
            for p in pattern_state.active_patterns:
                if p.status == PatternStatus.CONFIRMED:
                    confirmed_pattern = p
                    break

        if not confirmed_pattern:
            return None

        direction = confirmed_pattern.direction
        is_bullish = direction == PatternDirection.BULLISH

        # Verify there is a recent BOS or CHoCH in that direction
        # Or check if session range was broken
        has_break = False
        if is_bullish:
            has_break = any(bos.direction == "UP" for bos in market_state.bos_history) or \
                        any(choch.direction == "BEARISH_TO_BULLISH" for choch in market_state.choch_history) or \
                        (market_state.session and getattr(market_state.session, "is_broken", False))
        else:
            has_break = any(bos.direction == "DOWN" for bos in market_state.bos_history) or \
                        any(choch.direction == "BULLISH_TO_BEARISH" for choch in market_state.choch_history) or \
                        (market_state.session and getattr(market_state.session, "is_broken", False))

        if not has_break:
            return None

        # Calculate confidence
        quality_score = confirmed_pattern.quality.overall_score if confirmed_pattern.quality else 100.0
        confidence = (overall_confluence * 0.5) + (min(rvol / 3.0, 1.0) * 100.0 * 0.3) + (quality_score * 0.2)
        confidence = max(0.0, min(100.0, confidence))

        reasoning = (
            f"High volume breakout confirmed. Relative volume is {rvol:.2f} "
            f"aligning with a confirmed {confirmed_pattern.pattern_type.name} pattern."
        )

        return StrategySignal(
            signal_id=str(uuid.uuid4()),
            symbol=market_state.symbol,
            timeframe=market_state.timeframe,
            direction=direction,
            strategy_type=StrategyType.BREAKOUT,
            decision=StrategyDecision.BUY if is_bullish else StrategyDecision.SELL,
            confidence=round(confidence, 2),
            confluence_score=round(overall_confluence, 2),
            reasoning=reasoning,
            supporting_factors=[
                "Confirmed Breakout Pivot",
                "High Volume Expansion",
                "Confirmed Chart Pattern",
            ],
            conflicting_factors=[],
            detected_at=datetime.now(timezone.utc),
        )
