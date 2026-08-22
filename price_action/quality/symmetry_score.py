"""Symmetry Quality Scoring for the Pattern Quality Engine."""

from __future__ import annotations

from price_action.core.models import PatternCandidate, PatternMatch
from price_action.core.enums import PatternType


def evaluate_symmetry(pattern: PatternCandidate | PatternMatch) -> float:
    """Evaluate symmetry balance of a pattern [0.0, 100.0]."""
    if pattern.metadata and pattern.metadata.symmetry_score is not None:
        base_score = pattern.metadata.symmetry_score * 100.0
    else:
        base_score = 80.0

    # Calculate symmetry from point intervals if points are available
    if len(pattern.points) >= 3:
        p_list = sorted(pattern.points, key=lambda p: p.index)
        mid_idx = len(p_list) // 2
        left_width = abs(p_list[mid_idx].index - p_list[0].index)
        right_width = abs(p_list[-1].index - p_list[mid_idx].index)
        
        total_width = left_width + right_width
        if total_width > 0:
            ratio = abs(left_width - right_width) / total_width
            adjustment = (1.0 - ratio) * 20.0  # Up to +20 points for perfect balance
            base_score = (base_score * 0.8) + adjustment

    # Head and Shoulders specific shoulder symmetry
    if pattern.pattern_type in (PatternType.HEAD_AND_SHOULDERS, PatternType.INVERSE_HEAD_AND_SHOULDERS):
        # We look for LeftShoulder and RightShoulder labels
        ls = next((p for p in pattern.points if "leftshoulder" in p.point_label.lower()), None)
        rs = next((p for p in pattern.points if "rightshoulder" in p.point_label.lower()), None)
        if ls and rs:
            shoulder_diff = abs(ls.price - rs.price)
            avg_shoulder = (ls.price + rs.price) / 2.0
            if avg_shoulder > 0.0:
                dev = shoulder_diff / avg_shoulder
                if dev <= 0.02:
                    base_score += 10.0
                elif dev > 0.08:
                    base_score -= 15.0

    return max(0.0, min(100.0, base_score))
