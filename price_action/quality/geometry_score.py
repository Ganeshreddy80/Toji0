"""Geometry Quality Scoring for the Pattern Quality Engine."""

from __future__ import annotations

from price_action.core.models import PatternCandidate, PatternMatch


def evaluate_geometry(pattern: PatternCandidate | PatternMatch) -> float:
    """Evaluate geometric correctness of a pattern [0.0, 100.0]."""
    if pattern.metadata and pattern.metadata.geometry_score is not None:
        base_score = pattern.metadata.geometry_score * 100.0
    else:
        base_score = 80.0

    # Add geometric adjustments based on trendlines if present
    if len(pattern.trendlines) >= 2:
        t1, t2 = pattern.trendlines[0], pattern.trendlines[1]
        slope_diff = abs(t1.slope - t2.slope)
        
        # Parallel lines check (for channels/rectangles)
        if "channel" in pattern.pattern_type.value.lower() or "rectangle" in pattern.pattern_type.value.lower():
            if slope_diff <= 0.05:
                base_score += 15.0
            elif slope_diff <= 0.15:
                base_score += 5.0
            else:
                base_score -= 10.0
        # Converging lines check (for triangles/wedges/pennants)
        elif "triangle" in pattern.pattern_type.value.lower() or "wedge" in pattern.pattern_type.value.lower() or "pennant" in pattern.pattern_type.value.lower():
            # Triangles should converge
            if (t1.slope < 0 and t2.slope > 0) or (abs(t1.slope) > abs(t2.slope) if t1.slope < 0 else abs(t2.slope) > abs(t1.slope)):
                base_score += 10.0
            else:
                base_score -= 5.0

    return max(0.0, min(100.0, base_score))
