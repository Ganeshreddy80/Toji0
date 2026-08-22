"""Breakout Quality Scoring for the Pattern Quality Engine."""

from __future__ import annotations

from price_action.core.models import PatternCandidate, PatternMatch
from price_action.core.enums import PatternStatus


def evaluate_breakout(pattern: PatternCandidate | PatternMatch) -> float:
    """Evaluate breakout quality score [0.0, 100.0]."""
    if isinstance(pattern, PatternCandidate):
        # Candidates have not broken out yet: neutral/baseline score
        return 50.0

    if not hasattr(pattern, "status"):
        return 50.0

    if pattern.status == PatternStatus.DEVELOPING:
        return 50.0

    # Confirmed, Completed, or Invalidated matches
    if pattern.status == PatternStatus.INVALIDATED:
        # Failed breakout
        return 20.0

    # Active or completed breakout: base 85.0
    score = 85.0

    # If trendlines exist, we can compute breakout distance relative to pattern height
    if len(pattern.trendlines) >= 2:
        highs = [p.price for p in pattern.points]
        lows = [p.price for p in pattern.points]
        if highs and lows:
            height = max(highs) - min(lows)
            if height > 0.0:
                # We check the confirmed/latest point price relative to the pattern levels
                last_price = pattern.points[-1].price
                breakout_dist = abs(last_price - max(highs))  # basic heuristic
                pct = breakout_dist / height
                # Up to +15.0 points for reasonable breakout distance (e.g. 10% of pattern height)
                score += min(15.0, pct * 150.0)

    return max(0.0, min(100.0, score))
