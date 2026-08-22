"""Correlation scoring logic for the Confluence Engine."""

from __future__ import annotations

from market_intelligence.core.models import MarketState
from price_action.core.enums import PatternDirection
from confluence.core.models import SupportingFactor, ConflictingFactor


def evaluate_correlation(
    market_state: MarketState,
    pattern_direction: PatternDirection | None = None,
) -> tuple[float, list[SupportingFactor], list[ConflictingFactor]]:
    """Evaluate asset correlation risk [0.0, 100.0]."""
    supporting = []
    conflicting = []

    context = market_state.market_context
    if context is None or not context.correlation:
        return 100.0, [], []

    # Calculate average correlation
    correlations = context.correlation
    avg_corr = sum(abs(v) for v in correlations.values()) / len(correlations)

    score = 100.0
    if avg_corr > 0.8:
        # High correlation represents higher systemic risk / redundancy
        conflicting.append(
            ConflictingFactor(
                name="High Asset Correlation",
                category="CORRELATION",
                penalty=1.5,
                description=f"High average correlation of {avg_corr:.2f} increases exposure risk.",
            )
        )
        score = 60.0
    elif avg_corr < 0.3:
        supporting.append(
            SupportingFactor(
                name="Uncorrelated Asset",
                category="CORRELATION",
                value=95.0,
                description=f"Low average correlation of {avg_corr:.2f} confirms diversification value.",
            )
        )
        score = 95.0
    else:
        score = 80.0

    return score, supporting, conflicting
