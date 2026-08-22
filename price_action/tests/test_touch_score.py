"""Unit tests for touch score calculation."""

from __future__ import annotations

from datetime import datetime, timezone
from price_action.core.models import PatternCandidate, PatternPoint, PatternMetadata
from price_action.core.enums import PatternDirection, PatternType
from price_action.quality.touch_score import evaluate_touches


def test_touch_score_metadata_fallback():
    """Verify touch score maps metadata touch count correctly."""
    meta = PatternMetadata(
        source_engine="test",
        version="1.0.0",
        touch_count=4,
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
    score = evaluate_touches(cand)
    assert score == 85.0
