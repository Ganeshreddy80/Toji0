"""Validation utilities for checking swing point counts and properties."""

from __future__ import annotations

from typing import Sequence
from market_intelligence.core.enums import SwingType
from market_intelligence.core.models import SwingPoint


def validate_swing_counts(
    swings: Sequence[SwingPoint],
    min_highs: int = 2,
    min_lows: int = 2,
) -> bool:
    """Validate that the swings list contains at least min_highs and min_lows."""
    highs = [s for s in swings if s.point_type == SwingType.HIGH]
    lows = [s for s in swings if s.point_type == SwingType.LOW]
    return len(highs) >= min_highs and len(lows) >= min_lows
