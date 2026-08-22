"""Age and Maturity Quality Scoring for the Pattern Quality Engine."""

from __future__ import annotations

from price_action.core.models import PatternCandidate, PatternMatch


def evaluate_age(pattern: PatternCandidate | PatternMatch) -> float:
    """Evaluate pattern age/maturity score [0.0, 100.0]."""
    if len(pattern.points) < 2:
        return 50.0

    p_sorted = sorted(pattern.points, key=lambda p: p.index)
    duration = p_sorted[-1].index - p_sorted[0].index

    if duration < 10:
        # Too young: scale from 50.0 up to 90.0
        score = 50.0 + (duration / 10.0) * 40.0
    elif 10 <= duration <= 50:
        # Optimal maturity
        score = 100.0
    else:
        # Too old: decay at 0.5 per bar beyond 50, floor at 50.0
        score = max(50.0, 100.0 - (duration - 50) * 0.5)

    return max(0.0, min(100.0, score))
