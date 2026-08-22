"""Geometry utilities for pattern line projections and convergence validation."""

from __future__ import annotations


def line_value(slope: float, intercept: float, x: float) -> float:
    """Calculate the y-value of a line at index x."""
    return slope * x + intercept


def distance_at_index(
    slope_high: float,
    intercept_high: float,
    slope_low: float,
    intercept_low: float,
    x: float,
) -> float:
    """Calculate the vertical distance between two lines at index x."""
    return line_value(slope_high, intercept_high, x) - line_value(slope_low, intercept_low, x)


def check_convergence(
    slope_high: float,
    intercept_high: float,
    slope_low: float,
    intercept_low: float,
    first_idx: int,
    last_idx: int,
) -> bool:
    """Validate that two lines converge from first_idx to last_idx, without crossing."""
    dist_first = distance_at_index(slope_high, intercept_high, slope_low, intercept_low, first_idx)
    dist_last = distance_at_index(slope_high, intercept_high, slope_low, intercept_low, last_idx)
    return dist_last < dist_first and dist_last > 0.0
