"""Liquidity scoring logic for the Confluence Engine."""

from __future__ import annotations

from market_intelligence.core.models import MarketState
from price_action.core.enums import PatternDirection
from confluence.core.models import SupportingFactor, ConflictingFactor


def evaluate_liquidity(
    market_state: MarketState,
    pattern_direction: PatternDirection | None = None,
) -> tuple[float, list[SupportingFactor], list[ConflictingFactor]]:
    """Evaluate liquidity sweeps proximity and confirmation [0.0, 100.0]."""
    supporting = []
    conflicting = []

    liq = market_state.liquidity
    if liq is None:
        return 70.0, [], []

    swept_high = getattr(liq, "swept_high", False) or getattr(liq, "high_swept", False)
    swept_low = getattr(liq, "swept_low", False) or getattr(liq, "low_swept", False)

    score = 70.0
    if pattern_direction == PatternDirection.BULLISH and swept_low:
        supporting.append(
            SupportingFactor(
                name="Liquidity Sweep Support",
                category="LIQUIDITY",
                value=90.0,
                description="Bullish pattern aligns with swept sell-side liquidity.",
            )
        )
        score = 95.0
    elif pattern_direction == PatternDirection.BEARISH and swept_high:
        supporting.append(
            SupportingFactor(
                name="Liquidity Sweep Resistance",
                category="LIQUIDITY",
                value=90.0,
                description="Bearish pattern aligns with swept buy-side liquidity.",
            )
        )
        score = 95.0
    elif swept_high or swept_low:
        score = 80.0

    return score, supporting, conflicting
