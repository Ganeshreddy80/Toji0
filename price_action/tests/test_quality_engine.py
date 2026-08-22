"""Unit tests for the PatternQualityEngine coordinator."""

from __future__ import annotations

from datetime import datetime, timezone
from price_action.core.models import PatternCandidate, PatternPoint, PatternMetadata
from price_action.core.enums import PatternDirection, PatternType
from price_action.quality.quality_engine import PatternQualityEngine


def test_quality_engine_evaluates_candidate():
    """Verify that PatternQualityEngine evaluates a candidate and computes scores."""
    engine = PatternQualityEngine()
    meta = PatternMetadata(
        source_engine="test",
        version="1.0.0",
        geometry_score=0.9,
        symmetry_score=0.8,
        touch_count=4,
        regression_fit=0.85,
        volume_confirmation=0.9,
        atr_normalization=0.8,
    )
    p1 = PatternPoint(price=10.0, timestamp=datetime.now(timezone.utc), index=10, point_label="A")
    p2 = PatternPoint(price=12.0, timestamp=datetime.now(timezone.utc), index=30, point_label="B")
    
    cand = PatternCandidate(
        candidate_id="cand-1",
        symbol="BTCUSDT",
        timeframe="1h",
        pattern_type=PatternType.DOUBLE_TOP,
        direction=PatternDirection.BEARISH,
        points=[p1, p2],
        score=0.9,
        detected_at=datetime.now(timezone.utc),
        metadata=meta,
    )

    quality = engine.evaluate_candidate(cand)
    assert quality.overall_score > 0.0
    assert quality.geometry_score == 90.0
    assert quality.symmetry_score == 80.0
    assert quality.regression_score == 75.0
    assert quality.touch_score == 85.0  # 4 touches mapping
    assert len(quality.explanation) > 0
