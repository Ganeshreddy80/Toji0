"""Liquidity Validator for the Risk Engine."""

from __future__ import annotations

from typing import Any

from trading_context.core.models import TradingContext
from risk_engine.core.enums import RiskSeverity
from risk_engine.core.models import RiskFactor


class LiquidityValidator:
    """Checks bid-ask spread boundaries, minimum volume, and depth constraints."""

    def validate(
        self, context: TradingContext, **kwargs: Any
    ) -> tuple[RiskFactor | None, float, str | None]:
        market_state = context.market_state

        # 1. Resolve limits and current states from kwargs
        bid_ask_spread = float(kwargs.get("bid_ask_spread", 0.0))
        max_allowable_spread = float(kwargs.get("max_allowable_spread", 0.005))
        min_required_volume = float(kwargs.get("min_required_volume", 1.0))
        current_volume = float(kwargs.get("current_volume", 10.0))

        # 2. Check bid-ask spread limits
        if bid_ask_spread > max_allowable_spread:
            return (
                RiskFactor(
                    id="RE_LIQ_001",
                    name="Excessive Bid-Ask Spread",
                    severity=RiskSeverity.HIGH,
                    score=25.0,
                    description=f"Current spread of {bid_ask_spread:.4f} "
                    f"exceeds limit of {max_allowable_spread:.4f}.",
                ),
                25.0,
                f"Liquidity spread validation failed: {bid_ask_spread:.4f} > {max_allowable_spread:.4f}.",
            )

        # 3. Check minimum absolute volume
        if current_volume < min_required_volume:
            return (
                RiskFactor(
                    id="RE_LIQ_002",
                    name="Insufficient Volumetric Liquidity",
                    severity=RiskSeverity.MEDIUM,
                    score=15.0,
                    description=f"Current volume of {current_volume:.2f} is below minimum requirement of {min_required_volume:.2f}.",
                ),
                15.0,
                f"Insufficient volume: {current_volume:.2f} < {min_required_volume:.2f}.",
            )

        # 4. Check normalized volume from market state
        if market_state and market_state.volume:
            if market_state.volume.normalized_volume < 0.2:
                return (
                    RiskFactor(
                        id="RE_LIQ_003",
                        name="Low Normalized Volume Context",
                        severity=RiskSeverity.MEDIUM,
                        score=15.0,
                        description=f"Normalized volume of {market_state.volume.normalized_volume:.2f} is extremely low.",
                    ),
                    15.0,
                    f"Low normalized volume: {market_state.volume.normalized_volume:.2f} < 0.2.",
                )

        return None, 0.0, None
