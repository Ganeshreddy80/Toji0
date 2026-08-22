"""Regime scoring logic for the Confluence Engine."""

from __future__ import annotations

from market_intelligence.core.models import MarketState
from price_action.core.enums import PatternDirection
from confluence.core.models import SupportingFactor, ConflictingFactor


def evaluate_regime(
    market_state: MarketState,
    pattern_direction: PatternDirection | None = None,
) -> tuple[float, list[SupportingFactor], list[ConflictingFactor]]:
    """Evaluate market regime alignment [0.0, 100.0]."""
    supporting = []
    conflicting = []

    phase = getattr(market_state, "market_phase_state", "Unknown")
    
    score = 75.0
    if phase and "trend" in str(phase).lower():
        supporting.append(
            SupportingFactor(
                name="Trending Regime Alignment",
                category="REGIME",
                value=85.0,
                description=f"Market phase aligns with a trending regime: {phase}.",
            )
        )
        score = 85.0
    elif phase and "range" in str(phase).lower():
        # If it's range and we have a breakout pattern, it could be a breakout from range (which is positive)
        # but if it's trend-following it might conflict. Let's keep it neutral
        score = 70.0

    return score, supporting, conflicting
