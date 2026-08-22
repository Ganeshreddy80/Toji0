"""Fibonacci ratio and harmonic leg validation utilities."""

from __future__ import annotations


def calculate_ratio(leg_numerator: float, leg_denominator: float) -> float:
    """Calculate the absolute ratio between two price leg heights."""
    if leg_denominator == 0.0:
        return 0.0
    return abs(leg_numerator / leg_denominator)


def validate_ratio(ratio: float, target: float, tolerance: float = 0.05) -> bool:
    """Check if a calculated ratio matches a target Fibonacci level within tolerance."""
    return abs(ratio - target) <= tolerance
