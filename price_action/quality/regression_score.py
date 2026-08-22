"""Regression Fit Quality Scoring for the Pattern Quality Engine."""

from __future__ import annotations

from price_action.core.models import PatternCandidate, PatternMatch


def evaluate_regression(pattern: PatternCandidate | PatternMatch) -> float:
    """Evaluate regression fit score of a pattern [0.0, 100.0]."""
    if pattern.metadata and pattern.metadata.regression_fit is not None:
        r2 = pattern.metadata.regression_fit
    else:
        r2 = 0.85

    score = r2 * 100.0

    # Slight penalty for very few points since regression R2 is less stable with fewer points
    if len(pattern.points) < 4:
        score -= 10.0

    return max(0.0, min(100.0, score))
