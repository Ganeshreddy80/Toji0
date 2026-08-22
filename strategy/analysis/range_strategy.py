"""Range Strategy logic."""

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


class RangeStrategy:
    """Strategy that triggers range trades (buy low / sell high) in sideways regimes."""

    def __init__(self, confluence_min: float = 65.0) -> None:
        self.confluence_min = confluence_min

    @property
    def strategy_type(self) -> StrategyType:
        return StrategyType.RANGE

    @property
    def name(self) -> str:
        return "Range Strategy"

    def evaluate(
        self,
        market_state: MarketState,
        pattern_state: PatternState | None,
        confluence_state: ConfluenceState | None,
    ) -> StrategySignal | None:
        """Evaluate market state for a range setup."""
        if confluence_state is None:
            return None

        overall_confluence = confluence_state.score.overall_score
        if overall_confluence < self.confluence_min:
            return None

        # 1. Sideways regime check
        is_sideways = False
        if market_state.trend is not None and market_state.trend.direction == TrendDirection.SIDEWAYS:
            is_sideways = True
        elif market_state.market_phase_state and "range" in market_state.market_phase_state.lower():
            is_sideways = True

        if not is_sideways:
            return None

        # 2. Check for Rectangle or Channel pattern
        range_pattern = None
        if pattern_state:
            patterns = pattern_state.active_patterns + pattern_state.candidate_patterns
            for p in patterns:
                if p.pattern_type in (
                    PatternType.RECTANGLE,
                    PatternType.ASC_CHANNEL,
                    PatternType.DESC_CHANNEL,
                    PatternType.CHANNEL,
                ):
                    range_pattern = p
                    break

        if not range_pattern:
            return None

        # 3. Low Volatility check
        rvol = 1.0
        if market_state.volume is not None:
            rvol = getattr(market_state.volume, "relative_volume", None) or getattr(market_state.volume, "normalized_volume", 1.0)

        # Volatility index check or RVOL < 1.0
        if rvol > 1.2:
            return None

        # 4. Proximity check to determine BUY, SELL, or WAIT
        # If swings are available, check where the latest price is relative to support/resistance
        latest_swing = market_state.swings[-1] if market_state.swings else None
        if not latest_swing:
            return None

        # Find support/resistance in the SR levels or active zones
        current_price = latest_swing.price
        support = None
        resistance = None
        for sr in market_state.sr_levels:
            if sr.level_type == "SUPPORT":
                if support is None or abs(current_price - sr.price) < abs(current_price - support):
                    support = sr.price
            elif sr.level_type == "RESISTANCE":
                if resistance is None or abs(current_price - sr.price) < abs(current_price - resistance):
                    resistance = sr.price

        if support is None or resistance is None:
            # Check pattern points as fallback
            prices = [pt.price for pt in range_pattern.points]
            if prices:
                support = min(prices)
                resistance = max(prices)

        if support is None or resistance is None:
            return None

        range_height = resistance - support
        if range_height <= 0.0:
            return None

        # Proximity threshold: within 15% of boundaries
        threshold = range_height * 0.15
        is_near_support = abs(current_price - support) <= threshold
        is_near_resistance = abs(current_price - resistance) <= threshold

        decision = StrategyDecision.WAIT
        direction = PatternDirection.BULLISH
        reasoning = "Sideways regime: price consolidating in range. Maintain wait posture."

        if is_near_support:
            decision = StrategyDecision.BUY
            direction = PatternDirection.BULLISH
            reasoning = f"Price near range support level of {support:.2f}. Potential mean reversion up."
        elif is_near_resistance:
            decision = StrategyDecision.SELL
            direction = PatternDirection.BEARISH
            reasoning = f"Price near range resistance level of {resistance:.2f}. Potential mean reversion down."

        # If it's wait, we can still return a signal representing the ranging wait state
        # (which has lower confidence)
        confidence = overall_confluence
        if decision == StrategyDecision.WAIT:
            confidence *= 0.5

        return StrategySignal(
            signal_id=str(uuid.uuid4()),
            symbol=market_state.symbol,
            timeframe=market_state.timeframe,
            direction=direction,
            strategy_type=StrategyType.RANGE,
            decision=decision,
            confidence=round(confidence, 2),
            confluence_score=round(overall_confluence, 2),
            reasoning=reasoning,
            supporting_factors=[
                "Ranging Regime Stability",
                "Consolidation Boundaries Defined",
            ],
            conflicting_factors=[],
            detected_at=datetime.now(timezone.utc),
        )
