"""Unit tests for geometry score calculation."""

from __future__ import annotations

from datetime import datetime, timezone
from price_action.core.models import PatternCandidate, PatternPoint, PatternMetadata, Trendline
from price_action.core.enums import PatternDirection, PatternType
from price_action.quality.geometry_score import evaluate_geometry


def test_geometry_score_metadata_fallback():
    """Verify geometry score uses metadata if available."""
    meta = PatternMetadata(
        source_engine="test",
        version="1.0.0",
        geometry_score=0.95,
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
    score = evaluate_geometry(cand)
    assert score == 95.0


def test_geometry_score_trendlines():
    """Verify geometry score handles trendline slanting/convergence."""
    p1 = PatternPoint(price=10.0, timestamp=datetime.now(timezone.utc), index=1, point_label="A")
    p2 = PatternPoint(price=20.0, timestamp=datetime.now(timezone.utc), index=5, point_label="B")
    
    # Slopes are parallel (slope diff is 0.0)
    t1 = Trendline(start_point=p1, end_point=p2, slope=0.1, intercept=10.0)
    t2 = Trendline(start_point=p1, end_point=p2, slope=0.1, intercept=15.0)

    cand = PatternCandidate(
        candidate_id="cand-1",
        symbol="BTCUSDT",
        timeframe="1h",
        pattern_type=PatternType.RECTANGLE,
        direction=PatternDirection.BULLISH,
        points=[p1, p2],
        trendlines=[t1, t2],
        score=0.9,
        detected_at=datetime.now(timezone.utc),
    )
    score = evaluate_geometry(cand)
    # base is 80, plus 15 for parallel channels
    assert score == 95.0
