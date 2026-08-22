"""Unit tests for pattern completion score calculation."""

from __future__ import annotations

from datetime import datetime, timezone
from price_action.core.models import PatternMatch, PatternPoint
from price_action.core.enums import PatternDirection, PatternType, PatternStatus
from price_action.quality.completion_score import evaluate_completion


def test_completion_score_completed():
    """Verify completed patterns receive 100.0."""
    p1 = PatternPoint(price=10.0, timestamp=datetime.now(timezone.utc), index=10, point_label="A")
    match = PatternMatch(
        match_id="match-1",
        symbol="BTCUSDT",
        timeframe="1h",
        pattern_type=PatternType.DOUBLE_TOP,
        direction=PatternDirection.BEARISH,
        status=PatternStatus.COMPLETED,
        points=[p1],
        fit_score=0.9,
        confirmed_at=datetime.now(timezone.utc),
    )
    score = evaluate_completion(match)
    assert score == 100.0


def test_completion_score_invalidated():
    """Verify invalidated patterns receive 0.0."""
    p1 = PatternPoint(price=10.0, timestamp=datetime.now(timezone.utc), index=10, point_label="A")
    match = PatternMatch(
        match_id="match-1",
        symbol="BTCUSDT",
        timeframe="1h",
        pattern_type=PatternType.DOUBLE_TOP,
        direction=PatternDirection.BEARISH,
        status=PatternStatus.INVALIDATED,
        points=[p1],
        fit_score=0.9,
        confirmed_at=datetime.now(timezone.utc),
    )
    score = evaluate_completion(match)
    assert score == 0.0
