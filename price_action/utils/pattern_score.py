"""Pattern quality scoring utilities for geometry, symmetry, and volume context."""

from __future__ import annotations


def calculate_geometry_score(regression_fit: float, error_factor: float = 0.0) -> float:
    """Compute geometry score based on regression fit and error bounds."""
    score = regression_fit - abs(error_factor)
    return max(0.0, min(1.0, score))


def calculate_symmetry_score(left_width: int, right_width: int) -> float:
    """Compute symmetry balance score [0, 1] comparing two sides of a pattern."""
    total = left_width + right_width
    if total <= 0:
        return 1.0
    ratio = abs(left_width - right_width) / max(1, total)
    return max(0.0, min(1.0, 1.0 - ratio))


def calculate_volume_confirmation(breakout_volume: float, average_volume: float) -> float:
    """Compute volume confirmation score [0, 1] based on relative breakout volume."""
    if average_volume <= 0.0:
        return 1.0
    rvol = breakout_volume / average_volume
    # Scale: rvol >= 2.0 gets 1.0, rvol < 1.0 gets 0.0
    if rvol >= 2.0:
        return 1.0
    elif rvol <= 1.0:
        return 0.0
    return rvol - 1.0


def calculate_atr_normalization(pattern_height: float, atr: float) -> float:
    """Scale pattern size by ATR to determine normal size conformity."""
    if atr <= 0.0:
        return 1.0
    size_in_atrs = pattern_height / atr
    # Typically, pattern height should be between 1.5 ATR and 10 ATR
    if 1.5 <= size_in_atrs <= 10.0:
        return 1.0
    elif size_in_atrs < 1.5:
        return size_in_atrs / 1.5
    else:
        return max(0.0, 1.0 - (size_in_atrs - 10.0) / 10.0)


def calculate_overall_score(
    geometry_score: float,
    symmetry_score: float,
    regression_fit: float,
    volume_confirmation: float,
    atr_normalization: float,
) -> float:
    """Synthesize overall pattern quality score as a weighted average."""
    weights = [0.25, 0.20, 0.25, 0.15, 0.15]
    scores = [
        geometry_score,
        symmetry_score,
        regression_fit,
        volume_confirmation,
        atr_normalization,
    ]
    return max(0.0, min(1.0, sum(s * w for s, w in zip(scores, weights))))
