"""Volume scoring logic for the Confluence Engine."""

from __future__ import annotations

from market_intelligence.core.models import MarketState
from price_action.core.enums import PatternDirection
from confluence.core.models import SupportingFactor, ConflictingFactor


def evaluate_volume(
    market_state: MarketState,
    pattern_direction: PatternDirection | None = None,
) -> tuple[float, list[SupportingFactor], list[ConflictingFactor]]:
    """Evaluate volume profile confirmation [0.0, 100.0]."""
    supporting = []
    conflicting = []

    vol_state = market_state.volume
    if vol_state is None:
        return 75.0, [], []

    # Get relative volume or state, fallback to baseline
    score = 75.0
    rvol = getattr(vol_state, "relative_volume", 1.0) or getattr(vol_state, "average_volume", 1.0) # Check fields
    if hasattr(vol_state, "relative_volume") and vol_state.relative_volume is not None:
        rvol = vol_state.relative_volume

    if rvol >= 1.5:
        supporting.append(
            SupportingFactor(
                name="High Relative Volume",
                category="VOLUME",
                value=90.0,
                description=f"High relative volume of {rvol:.2f} confirms market interest.",
            )
        )
        score = 90.0
    elif rvol < 0.5:
        conflicting.append(
            ConflictingFactor(
                name="Low Volume Participation",
                category="VOLUME",
                penalty=2.0,
                description=f"Low relative volume of {rvol:.2f} suggests lack of interest.",
            )
        )
        score = 50.0

    return score, supporting, conflicting
