"""Touch Quality Scoring for the Pattern Quality Engine."""

from __future__ import annotations

from price_action.core.models import PatternCandidate, PatternMatch


def evaluate_touches(pattern: PatternCandidate | PatternMatch) -> float:
    """Evaluate touch frequency score of a pattern [0.0, 100.0]."""
    if pattern.metadata and pattern.metadata.touch_count is not None:
        touches = pattern.metadata.touch_count
    else:
        touches = len(pattern.points)

    if touches <= 2:
        score = 50.0
    elif touches == 3:
        score = 70.0
    elif touches == 4:
        score = 85.0
    elif touches == 5:
        score = 95.0
    else:
        score = 100.0

    return max(0.0, min(100.0, score))
