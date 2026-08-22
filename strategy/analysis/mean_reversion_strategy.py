"""Mean Reversion Strategy logic."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from market_intelligence.core.models import MarketState
from price_action.core.enums import PatternDirection
from price_action.core.models import PatternState
from confluence.core.models import ConfluenceState
from strategy.core.enums import StrategyDecision, StrategyType
from strategy.core.models import StrategySignal


class MeanReversionStrategy:
    """Strategy that triggers buy/sell signals on price rejection at S/R or demand/supply zones."""

    def __init__(self, confluence_min: float = 70.0) -> None:
        self.confluence_min = confluence_min

    @property
    def strategy_type(self) -> StrategyType:
        return StrategyType.MEAN_REVERSION

    @property
    def name(self) -> str:
        return "Mean Reversion Strategy"

    def evaluate(
        self,
        market_state: MarketState,
        pattern_state: PatternState | None,
        confluence_state: ConfluenceState | None,
    ) -> StrategySignal | None:
        """Evaluate market state for a mean reversion setup."""
        if confluence_state is None:
            return None

        overall_confluence = confluence_state.score.overall_score
        if overall_confluence < self.confluence_min:
            return None

        # 1. Volatile/ranging check
        is_volatile_or_range = False
        context = market_state.market_context
        if context is not None:
            from market_intelligence.core.enums import MarketRegime
            if context.regime in (MarketRegime.VOLATILE, MarketRegime.RANGING):
                is_volatile_or_range = True

        phase_lower = market_state.market_phase_state.lower()
        if "volatile" in phase_lower or "range" in phase_lower or "consolidation" in phase_lower:
            is_volatile_or_range = True

        if not is_volatile_or_range:
            return None

        # 2. Check if price is near key Support/Resistance or Supply/Demand zones
        latest_swing = market_state.swings[-1] if market_state.swings else None
        if not latest_swing:
            return None

        current_price = latest_swing.price
        near_support = False
        near_resistance = False

        # Check demand/supply zones
        for zone in market_state.zones:
            if zone.is_invalidated:
                continue
            
            # Retrieve lower_bound/upper_bound
            lower = getattr(zone, "lower_bound", 0.0)
            upper = getattr(zone, "upper_bound", 0.0)
            if lower <= 0.0 or upper <= 0.0:
                continue
            
            # Zone height
            height = upper - lower
            threshold = height * 0.20
            
            if "DEMAND" in str(zone.zone_type).upper():
                # Near demand lower boundary (support)
                if abs(current_price - lower) <= threshold or (lower <= current_price <= upper):
                    near_support = True
            elif "SUPPLY" in str(zone.zone_type).upper():
                # Near supply upper boundary (resistance)
                if abs(current_price - upper) <= threshold or (lower <= current_price <= upper):
                    near_resistance = True

        # Check horizontal support/resistance
        for sr in market_state.sr_levels:
            dist = abs(current_price - sr.price)
            # Within 1% of the price level
            if dist <= current_price * 0.01:
                if sr.level_type == "SUPPORT":
                    near_support = True
                elif sr.level_type == "RESISTANCE":
                    near_resistance = True

        if not (near_support or near_resistance):
            return None

        # Determine direction
        is_bullish = near_support
        is_bearish = near_resistance and not near_support # Tie-break to support if somehow both

        direction = PatternDirection.BULLISH if is_bullish else PatternDirection.BEARISH
        decision = StrategyDecision.BUY if is_bullish else StrategyDecision.SELL

        # Calculate confidence
        confidence = overall_confluence
        reasoning = (
            f"Mean reversion setup triggered near key {'Support/Demand' if is_bullish else 'Resistance/Supply'} "
            f"in a volatile/consolidating regime."
        )

        return StrategySignal(
            signal_id=str(uuid.uuid4()),
            symbol=market_state.symbol,
            timeframe=market_state.timeframe,
            direction=direction,
            strategy_type=StrategyType.MEAN_REVERSION,
            decision=decision,
            confidence=round(confidence, 2),
            confluence_score=round(overall_confluence, 2),
            reasoning=reasoning,
            supporting_factors=[
                "Volatile Regime Dynamic Check",
                "Key Support/Resistance Level Rejection",
            ],
            conflicting_factors=[],
            detected_at=datetime.now(timezone.utc),
        )
