"""Volatility Validator for the Risk Engine."""

from __future__ import annotations

from typing import Any

from trading_context.core.models import TradingContext
from risk_engine.core.enums import RiskSeverity
from risk_engine.core.models import RiskFactor
from market_intelligence.core.enums import MarketRegime, VolumeExpansionState


class VolatilityValidator:
    """Checks volatility levels, ATR spikes, and abnormal volume expansion states."""

    def validate(
        self, context: TradingContext, **kwargs: Any
    ) -> tuple[RiskFactor | None, float, str | None]:
        market_state = context.market_state
        if not market_state:
            return None, 0.0, None

        # 1. Resolve configuration thresholds from kwargs
        volatility_threshold_multiplier = float(kwargs.get("volatility_threshold_multiplier", 3.0))
        atr_ma = float(kwargs.get("atr_ma", 0.0))  # Default 0.0 means not checked via MA comparison

        # 2. Check ATR spike
        if market_state.volume and atr_ma > 0.0:
            current_atr = market_state.volume.atr
            if current_atr > atr_ma * volatility_threshold_multiplier:
                return (
                    RiskFactor(
                        id="RE_VOL_001",
                        name="ATR Volatility Spike",
                        severity=RiskSeverity.HIGH,
                        score=30.0,
                        description=f"Current ATR of {current_atr:.4f} exceeds limit multiplier "
                        f"threshold of {atr_ma * volatility_threshold_multiplier:.4f}.",
                    ),
                    30.0,
                    f"ATR spike detected: {current_atr:.4f} > {atr_ma * volatility_threshold_multiplier:.4f}.",
                )

        # 3. Check Volume expansion state
        if market_state.volume and market_state.volume.expansion_state == VolumeExpansionState.CLIMATIC:
            return (
                RiskFactor(
                    id="RE_VOL_002",
                    name="Climatic Volume Expansion",
                    severity=RiskSeverity.HIGH,
                    score=25.0,
                    description="Climatic volume expansion detected, indicating potential exhaustion or high risk.",
                ),
                25.0,
                "Climatic volume expansion active.",
            )

        # 4. Check Volatile Market Regime
        if market_state.market_context and market_state.market_context.regime == MarketRegime.VOLATILE:
            return (
                RiskFactor(
                    id="RE_VOL_003",
                    name="Volatile Market Regime",
                    severity=RiskSeverity.MEDIUM,
                    score=15.0,
                    description="Market regime is classified as highly volatile.",
                ),
                15.0,
                "Volatile market regime active.",
            )

        return None, 0.0, None
