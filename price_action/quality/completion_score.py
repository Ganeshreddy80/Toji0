"""Completion Progress Quality Scoring for the Pattern Quality Engine."""

from __future__ import annotations

from price_action.core.models import PatternCandidate, PatternMatch
from price_action.core.enums import PatternStatus, PatternDirection


def evaluate_completion(pattern: PatternCandidate | PatternMatch) -> float:
    """Evaluate completion and target achievement progress [0.0, 100.0]."""
    if isinstance(pattern, PatternCandidate):
        return 50.0

    if pattern.status == PatternStatus.COMPLETED:
        return 100.0
    elif pattern.status == PatternStatus.INVALIDATED:
        return 0.0

    # For confirmed/active patterns, estimate progress towards target
    highs = [p.price for p in pattern.points]
    lows = [p.price for p in pattern.points]
    if not highs or not lows:
        return 50.0

    max_p = max(highs)
    min_p = min(lows)
    height = max_p - min_p
    if height <= 0.0:
        return 50.0

    # Last point represents current price state
    current_price = pattern.points[-1].price

    if pattern.direction == PatternDirection.BULLISH:
        entry_price = max_p
        target_price = entry_price + height
        if current_price >= target_price:
            return 100.0
        elif current_price <= min_p:
            return 0.0
        ratio = (current_price - entry_price) / max(1e-6, target_price - entry_price)
        return max(0.0, min(100.0, ratio * 100.0))
    elif pattern.direction == PatternDirection.BEARISH:
        entry_price = min_p
        target_price = entry_price - height
        if current_price <= target_price:
            return 100.0
        elif current_price >= max_p:
            return 0.0
        ratio = (entry_price - current_price) / max(1e-6, entry_price - target_price)
        return max(0.0, min(100.0, ratio * 100.0))

    return 50.0
