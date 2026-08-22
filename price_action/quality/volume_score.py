"""Volume Quality Scoring for the Pattern Quality Engine."""

from __future__ import annotations

from price_action.core.models import PatternCandidate, PatternMatch


def evaluate_volume(pattern: PatternCandidate | PatternMatch) -> float:
    """Evaluate volume profile score of a pattern [0.0, 100.0]."""
    if pattern.metadata and pattern.metadata.volume_confirmation is not None:
        vol_score = pattern.metadata.volume_confirmation
    else:
        vol_score = 0.80

    score = vol_score * 100.0

    return max(0.0, min(100.0, score))
