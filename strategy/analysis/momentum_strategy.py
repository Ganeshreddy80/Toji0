"""Momentum Strategy logic."""

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


class MomentumStrategy:
    """Strategy that triggers buy/sell signals on price velocity and volume acceleration."""

    def __init__(self, confluence_min: float = 70.0, rvol_min: float = 1.5, strength_min: float = 0.7) -> None:
        self.confluence_min = confluence_min
        self.rvol_min = rvol_min
        self.strength_min = strength_min

    @property
    def strategy_type(self) -> StrategyType:
        return StrategyType.MOMENTUM

    @property
    def name(self) -> str:
        return "Momentum Strategy"

    def evaluate(
        self,
        market_state: MarketState,
        pattern_state: PatternState | None,
        confluence_state: ConfluenceState | None,
    ) -> StrategySignal | None:
        """Evaluate market state for a momentum setup."""
        if confluence_state is None or market_state.trend is None:
            return None

        overall_confluence = confluence_state.score.overall_score
        if overall_confluence < self.confluence_min:
            return None

        # 1. High Relative Volume
        rvol = 1.0
        if market_state.volume is not None:
            rvol = getattr(market_state.volume, "relative_volume", None) or getattr(market_state.volume, "normalized_volume", 1.0)

        if rvol < self.rvol_min:
            return None

        # 2. Strong Trend Strength
        trend_strength = market_state.trend.strength
        if trend_strength < self.strength_min:
            return None

        trend_dir = market_state.trend.direction
        if trend_dir == TrendDirection.SIDEWAYS:
            return None

        is_bullish = trend_dir == TrendDirection.UP
        direction = PatternDirection.BULLISH if is_bullish else PatternDirection.BEARISH
        decision = StrategyDecision.BUY if is_bullish else StrategyDecision.SELL

        # Calculate confidence
        confidence = (overall_confluence * 0.4) + (trend_strength * 100.0 * 0.4) + (min(rvol / 3.0, 1.0) * 100.0 * 0.2)
        confidence = max(0.0, min(100.0, confidence))

        reasoning = (
            f"Strong momentum acceleration: trend strength of {trend_strength:.2f} "
            f"coupled with high relative volume of {rvol:.2f}."
        )

        return StrategySignal(
            signal_id=str(uuid.uuid4()),
            symbol=market_state.symbol,
            timeframe=market_state.timeframe,
            direction=direction,
            strategy_type=StrategyType.MOMENTUM,
            decision=decision,
            confidence=round(confidence, 2),
            confluence_score=round(overall_confluence, 2),
            reasoning=reasoning,
            supporting_factors=[
                "High Relative Volume",
                "Strong Trend Strength",
                "Price Acceleration",
            ],
            conflicting_factors=[],
            detected_at=datetime.now(timezone.utc),
        )
