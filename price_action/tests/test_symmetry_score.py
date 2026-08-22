"""Unit tests for symmetry score calculation."""

from __future__ import annotations

from datetime import datetime, timezone
from price_action.core.models import PatternCandidate, PatternPoint, PatternMetadata
from price_action.core.enums import PatternDirection, PatternType
from price_action.quality.symmetry_score import evaluate_symmetry


def test_symmetry_score_metadata_fallback():
    """Verify symmetry score uses metadata if available."""
    meta = PatternMetadata(
        source_engine="test",
        version="1.0.0",
        symmetry_score=0.88,
    )
    p1 = PatternPoint(price=10.0, timestamp=datetime.now(timezone.utc), index=1, point_label="A")
    cand = PatternCandidate(
        candidate_id="cand-1",
        symbol="BTCUSDT",
        timeframe="1h",
        pattern_type=PatternType.DOUBLE_TOP,
        direction=PatternDirection.BEARISH,
        points=[p1],
        score=0.9,
        detected_at=datetime.now(timezone.utc),
        metadata=meta,
    )
    score = evaluate_symmetry(cand)
    assert score == 88.0


def test_symmetry_points_calculation():
    """Verify symmetry score calculation based on point indices spacing."""
    p1 = PatternPoint(price=10.0, timestamp=datetime.now(timezone.utc), index=10, point_label="Left")
    p2 = PatternPoint(price=20.0, timestamp=datetime.now(timezone.utc), index=20, point_label="Middle")
    p3 = PatternPoint(price=10.0, timestamp=datetime.now(timezone.utc), index=30, point_label="Right")

    cand = PatternCandidate(
        candidate_id="cand-1",
        symbol="BTCUSDT",
        timeframe="1h",
        pattern_type=PatternType.DOUBLE_TOP,
        direction=PatternDirection.BEARISH,
        points=[p1, p2, p3],
        score=0.9,
        detected_at=datetime.now(timezone.utc),
    )
    score = evaluate_symmetry(cand)
    # Spacing is symmetric (10 to 20 vs 20 to 30)
    assert score > 80.0
