"""Unit tests for regression score calculation."""

from __future__ import annotations

from datetime import datetime, timezone
from price_action.core.models import PatternCandidate, PatternPoint, PatternMetadata
from price_action.core.enums import PatternDirection, PatternType
from price_action.quality.regression_score import evaluate_regression


def test_regression_score_metadata():
    """Verify regression score uses metadata if available."""
    meta = PatternMetadata(
        source_engine="test",
        version="1.0.0",
        regression_fit=0.92,
    )
    # 4 points to avoid regression penalty
    pts = [
        PatternPoint(price=10.0, timestamp=datetime.now(timezone.utc), index=i, point_label="A")
        for i in range(4)
    ]
    cand = PatternCandidate(
        candidate_id="cand-1",
        symbol="BTCUSDT",
        timeframe="1h",
        pattern_type=PatternType.DOUBLE_TOP,
        direction=PatternDirection.BEARISH,
        points=pts,
        score=0.9,
        detected_at=datetime.now(timezone.utc),
        metadata=meta,
    )
    score = evaluate_regression(cand)
    assert score == 92.0
