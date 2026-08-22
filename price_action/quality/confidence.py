"""Confidence Quality Scoring for the Pattern Quality Engine."""

from __future__ import annotations

from market_intelligence.core.models import MarketState
from price_action.core.models import PatternCandidate, PatternMatch
from price_action.core.enums import PatternDirection


def evaluate_confidence(pattern: PatternCandidate | PatternMatch, market_state: MarketState | None = None) -> float:
    """Evaluate confidence sub-score of a pattern [0.0, 100.0] based on trend alignment."""
    if market_state is None or market_state.trend is None:
        return 80.0

    trend_dir = getattr(market_state.trend, "direction", None)
    if not trend_dir:
        return 80.0

    # Trend alignment logic
    # trend_dir can be "BULLISH", "BEARISH", "SIDEWAYS", "UNKNOWN", etc.
    trend_dir_str = str(trend_dir).upper()

    is_bullish_trend = "BULL" in trend_dir_str or "UP" in trend_dir_str
    is_bearish_trend = "BEAR" in trend_dir_str or "DOWN" in trend_dir_str

    if pattern.direction == PatternDirection.BULLISH:
        if is_bullish_trend:
            return 95.0
        elif is_bearish_trend:
            return 60.0  # counter-trend
    elif pattern.direction == PatternDirection.BEARISH:
        if is_bearish_trend:
            return 95.0
        elif is_bullish_trend:
            return 60.0  # counter-trend

    return 80.0
