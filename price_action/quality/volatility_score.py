"""Volatility Quality Scoring for the Pattern Quality Engine."""

from __future__ import annotations

from price_action.core.models import PatternCandidate, PatternMatch


def evaluate_volatility(pattern: PatternCandidate | PatternMatch) -> float:
    """Evaluate ATR-normalized volatility conformity [0.0, 100.0]."""
    if pattern.metadata and pattern.metadata.atr_normalization is not None:
        atr_norm = pattern.metadata.atr_normalization
    else:
        atr_norm = 0.75

    score = atr_norm * 100.0

    return max(0.0, min(100.0, score))
