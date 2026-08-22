"""Statistical utilities for patterns, normalized slopes, and flagpole metrics."""

from __future__ import annotations


def calculate_fit_score(r2_high: float, r2_low: float) -> float:
    """Calculate the average R-squared fit score constrained to [0, 1]."""
    return max(0.0, min(1.0, (r2_high + r2_low) / 2.0))


def normalize_slope(slope: float, atr: float) -> float:
    """Normalize a slope by Average True Range (ATR) to make it scale-independent."""
    if atr <= 0.0:
        return slope
    return slope / atr


def calculate_pole_height_atr(start_price: float, end_price: float, atr: float) -> float:
    """Calculate the height of a flagpole in ATRs."""
    if atr <= 0.0:
        return 0.0
    return (end_price - start_price) / atr
