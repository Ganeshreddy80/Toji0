"""Price projection utilities for targets, invalidations, and breakouts."""

from __future__ import annotations

from price_action.core.enums import PatternDirection


def check_breakout(price: float, upper_val: float, lower_val: float) -> tuple[bool, bool]:
    """Check if a price has broken out above upper_val or below lower_val.

    Returns:
        tuple: (is_bullish_breakout, is_bearish_breakout)
    """
    return price > upper_val, price < lower_val


def project_target_and_invalidation(
    max_p: float,
    min_p: float,
    direction: PatternDirection,
) -> tuple[float, float]:
    """Calculate the target and invalidation prices for a pattern breakout.

    Returns:
        tuple: (target_price, invalidation_price)
    """
    height = max_p - min_p
    if direction == PatternDirection.BULLISH:
        return max_p + height, min_p
    elif direction == PatternDirection.BEARISH:
        return min_p - height, max_p
    return max_p, min_p
