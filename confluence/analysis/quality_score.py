"""Quality scoring logic for the Confluence Engine."""

from __future__ import annotations

from market_intelligence.core.models import MarketState
from price_action.core.enums import PatternDirection
from price_action.core.models import PatternState
from confluence.core.models import SupportingFactor, ConflictingFactor


def evaluate_quality(
    market_state: MarketState,
    pattern_state: PatternState | None = None,
    pattern_direction: PatternDirection | None = None,
) -> tuple[float, list[SupportingFactor], list[ConflictingFactor]]:
    """Evaluate pattern quality score [0.0, 100.0]."""
    supporting = []
    conflicting = []

    if pattern_state is None:
        return 50.0, [], []

    # Collect all pattern matches and candidates matching the direction (or any, if direction is None)
    patterns_to_evaluate = []
    for pattern in pattern_state.active_patterns:
        if pattern_direction is None or pattern.direction == pattern_direction:
            patterns_to_evaluate.append(pattern)

    for pattern in pattern_state.candidate_patterns:
        if pattern_direction is None or pattern.direction == pattern_direction:
            patterns_to_evaluate.append(pattern)

    if not patterns_to_evaluate:
        return 50.0, [], []

    # Get the best quality score among the matching patterns
    max_quality_score = 0.0
    best_pattern = None

    for pattern in patterns_to_evaluate:
        if pattern.quality is not None:
            if pattern.quality.overall_score > max_quality_score:
                max_quality_score = pattern.quality.overall_score
                best_pattern = pattern

    if best_pattern is None:
        # No quality details available, return default moderate score
        return 70.0, [], []

    score = max_quality_score
    pattern_name = str(best_pattern.pattern_type)

    if score >= 80.0:
        supporting.append(
            SupportingFactor(
                name=f"High Pattern Quality: {pattern_name}",
                category="QUALITY",
                value=score,
                description=f"Pattern quality of {score:.1f} shows strong structural formation.",
            )
        )
    elif score < 50.0:
        conflicting.append(
            ConflictingFactor(
                name=f"Low Pattern Quality: {pattern_name}",
                category="QUALITY",
                penalty=2.0,
                description=f"Low pattern quality of {score:.1f} indicates weak geometry.",
            )
        )

    return score, supporting, conflicting
