"""Trend scoring logic for the Confluence Engine."""

from __future__ import annotations

from market_intelligence.core.models import MarketState
from price_action.core.enums import PatternDirection
from confluence.core.models import SupportingFactor, ConflictingFactor


def evaluate_trend(
    market_state: MarketState,
    pattern_direction: PatternDirection | None = None,
) -> tuple[float, list[SupportingFactor], list[ConflictingFactor]]:
    """Evaluate trend alignment quality score [0.0, 100.0]."""
    supporting = []
    conflicting = []
    
    if market_state.trend is None:
        return 50.0, [], []

    trend_dir = getattr(market_state.trend, "direction", None)
    if not trend_dir:
        return 50.0, [], []

    trend_str = str(trend_dir).upper()
    is_bullish_trend = "BULL" in trend_str or "UP" in trend_str
    is_bearish_trend = "BEAR" in trend_str or "DOWN" in trend_str

    if pattern_direction == PatternDirection.BULLISH:
        if is_bullish_trend:
            supporting.append(
                SupportingFactor(
                    name="Trend Alignment",
                    category="TREND",
                    value=100.0,
                    description="Bullish pattern aligns with bullish trend.",
                )
            )
            return 100.0, supporting, conflicting
        elif is_bearish_trend:
            conflicting.append(
                ConflictingFactor(
                    name="Counter-Trend Pattern",
                    category="TREND",
                    penalty=3.0,
                    description="Bullish pattern conflicts with bearish trend.",
                )
            )
            return 30.0, supporting, conflicting
    elif pattern_direction == PatternDirection.BEARISH:
        if is_bearish_trend:
            supporting.append(
                SupportingFactor(
                    name="Trend Alignment",
                    category="TREND",
                    value=100.0,
                    description="Bearish pattern aligns with bearish trend.",
                )
            )
            return 100.0, supporting, conflicting
        elif is_bullish_trend:
            conflicting.append(
                ConflictingFactor(
                    name="Counter-Trend Pattern",
                    category="TREND",
                    penalty=3.0,
                    description="Bearish pattern conflicts with bullish trend.",
                )
            )
            return 30.0, supporting, conflicting

    # Default baseline if no pattern or neutral/sideways trend
    return 75.0, [], []
