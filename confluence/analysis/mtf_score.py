"""Multi-timeframe scoring logic for the Confluence Engine."""

from __future__ import annotations

from market_intelligence.core.models import MarketState
from price_action.core.enums import PatternDirection
from confluence.core.models import SupportingFactor, ConflictingFactor


def evaluate_mtf(
    market_state: MarketState,
    pattern_direction: PatternDirection | None = None,
) -> tuple[float, list[SupportingFactor], list[ConflictingFactor]]:
    """Evaluate multi-timeframe alignment score [0.0, 100.0]."""
    supporting = []
    conflicting = []

    # Proximity or trend alignment across higher timeframes
    # For now, evaluate based on context trend alignment
    score = 75.0
    context = market_state.market_context
    if context is not None:
        htf_trend = getattr(context, "higher_timeframe_trend", None)
        if htf_trend is None and context.alignment is not None:
            htf_trend = getattr(context.alignment, "dominant_trend", None)
        if htf_trend:
            htf_trend_str = str(htf_trend).upper()
            is_bullish_htf = "BULL" in htf_trend_str or "UP" in htf_trend_str
            is_bearish_htf = "BEAR" in htf_trend_str or "DOWN" in htf_trend_str

            if pattern_direction == PatternDirection.BULLISH and is_bullish_htf:
                supporting.append(
                    SupportingFactor(
                        name="HTF Trend Confluence",
                        category="MTF",
                        value=90.0,
                        description="Bullish setup aligns with higher timeframe trend direction.",
                    )
                )
                score = 95.0
            elif pattern_direction == PatternDirection.BEARISH and is_bearish_htf:
                supporting.append(
                    SupportingFactor(
                        name="HTF Trend Confluence",
                        category="MTF",
                        value=90.0,
                        description="Bearish setup aligns with higher timeframe trend direction.",
                    )
                )
                score = 95.0
            elif (pattern_direction == PatternDirection.BULLISH and is_bearish_htf) or \
                 (pattern_direction == PatternDirection.BEARISH and is_bullish_htf):
                conflicting.append(
                    ConflictingFactor(
                        name="HTF Trend Conflict",
                        category="MTF",
                        penalty=2.0,
                        description="Setup direction is counter to higher timeframe trend.",
                    )
                )
                score = 40.0

    return score, supporting, conflicting
