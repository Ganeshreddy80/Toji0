"""Helpers for selecting, sorting, and partitioning swing point subsets."""

from __future__ import annotations

from typing import Sequence
from market_intelligence.core.enums import SwingType
from market_intelligence.core.models import SwingPoint


def select_recent_swings(swings: Sequence[SwingPoint], count: int = 6) -> list[SwingPoint]:
    """Retrieve and sort the last `count` swing points by index."""
    return sorted(swings[-count:], key=lambda s: s.index)


def partition_highs_lows(swings: Sequence[SwingPoint]) -> tuple[list[SwingPoint], list[SwingPoint]]:
    """Partition swings into separate lists of highs and lows, sorted chronologically."""
    highs = sorted([s for s in swings if s.point_type == SwingType.HIGH], key=lambda s: s.index)
    lows = sorted([s for s in swings if s.point_type == SwingType.LOW], key=lambda s: s.index)
    return highs, lows


def get_extremes(swings: Sequence[SwingPoint]) -> tuple[float, float]:
    """Calculate the minimum and maximum price levels across a sequence of swings."""
    if not swings:
        return 0.0, 0.0
    prices = [s.price for s in swings]
    return min(prices), max(prices)
