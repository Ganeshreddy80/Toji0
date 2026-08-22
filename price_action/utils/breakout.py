"""Breakout, target hit, and invalidation verification utilities."""

from __future__ import annotations

from price_action.core.enums import PatternDirection


def evaluate_breakout(price: float, upper_barrier: float, lower_barrier: float) -> tuple[bool, bool]:
    """Check if price has broken out above the upper barrier or below the lower barrier.

    Returns:
        tuple: (is_bullish_breakout, is_bearish_breakout)
    """
    return price > upper_barrier, price < lower_barrier


def check_target_reached(price: float, target_price: float, direction: PatternDirection) -> bool:
    """Check if price has reached or exceeded the pattern's completion target."""
    if direction == PatternDirection.BULLISH:
        return price >= target_price
    elif direction == PatternDirection.BEARISH:
        return price <= target_price
    return False


def check_invalidation_breached(price: float, invalidation_price: float, direction: PatternDirection) -> bool:
    """Check if price has breached the invalidation level."""
    if direction == PatternDirection.BULLISH:
        return price <= invalidation_price
    elif direction == PatternDirection.BEARISH:
        return price >= invalidation_price
    return False
