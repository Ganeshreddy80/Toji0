"""Structure scoring logic for the Confluence Engine."""

from __future__ import annotations

from market_intelligence.core.models import MarketState
from price_action.core.enums import PatternDirection
from confluence.core.models import SupportingFactor, ConflictingFactor


def evaluate_structure(
    market_state: MarketState,
    pattern_direction: PatternDirection | None = None,
) -> tuple[float, list[SupportingFactor], list[ConflictingFactor]]:
    """Evaluate market structure alignment (BOS/CHoCH) [0.0, 100.0]."""
    supporting = []
    conflicting = []

    has_bos = len(market_state.bos_history) > 0
    has_choch = len(market_state.choch_history) > 0

    if not (has_bos or has_choch):
        return 70.0, [], []

    # Simple heuristic check: if structure exists, check alignment
    score = 80.0
    if has_choch:
        supporting.append(
            SupportingFactor(
                name="Market Structure Shift",
                category="STRUCTURE",
                value=90.0,
                description="CHoCH confirms structure shift.",
            )
        )
        score = 90.0
    elif has_bos:
        supporting.append(
            SupportingFactor(
                name="Structural Continuation",
                category="STRUCTURE",
                value=85.0,
                description="BOS confirms structural continuation.",
            )
        )
        score = 85.0

    return score, supporting, conflicting
