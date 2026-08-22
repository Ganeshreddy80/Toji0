"""Tolerance and slope validation utilities for pattern boundaries."""

from __future__ import annotations


def check_parallel(slope_high_norm: float, slope_low_norm: float, tolerance: float = 0.15) -> bool:
    """Validate if two trendline slopes are parallel within tolerance."""
    return abs(slope_high_norm - slope_low_norm) <= tolerance


def is_horizontal(slope_norm: float, threshold: float = 0.02) -> bool:
    """Verify if a normalized slope is horizontal within a given threshold."""
    return abs(slope_norm) <= threshold


def is_rising(slope_norm: float, threshold: float = 0.02) -> bool:
    """Verify if a normalized slope is rising above a given threshold."""
    return slope_norm > threshold


def is_falling(slope_norm: float, threshold: float = -0.02) -> bool:
    """Verify if a normalized slope is falling below a given threshold."""
    return slope_norm < threshold
