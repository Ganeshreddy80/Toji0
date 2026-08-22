"""Unit tests for pattern age score calculation."""

from __future__ import annotations

from datetime import datetime, timezone
from price_action.core.models import PatternCandidate, PatternPoint
from price_action.core.enums import PatternDirection, PatternType
from price_action.quality.age_score import evaluate_age


def test_age_score_duration():
    """Verify age score based on point indexes difference."""
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
    )
    score = evaluate_age(cand)
    # duration is 20, which is in optimal [10, 50] range
    assert score == 100.0
