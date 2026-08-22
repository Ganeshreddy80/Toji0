"""Unit tests for breakout score calculation."""

from __future__ import annotations

from datetime import datetime, timezone
from price_action.core.models import PatternCandidate, PatternMatch, PatternPoint, PatternMetadata
from price_action.core.enums import PatternDirection, PatternType, PatternStatus
from price_action.quality.breakout_score import evaluate_breakout


def test_breakout_candidate_score():
    """Verify candidate breakout score is neutral."""
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
    )
    score = evaluate_breakout(cand)
    assert score == 50.0


def test_breakout_match_score():
    """Verify confirmed breakout match score."""
    p1 = PatternPoint(price=10.0, timestamp=datetime.now(timezone.utc), index=1, point_label="A")
    match = PatternMatch(
        match_id="match-1",
        symbol="BTCUSDT",
        timeframe="1h",
        pattern_type=PatternType.DOUBLE_TOP,
        direction=PatternDirection.BEARISH,
        status=PatternStatus.CONFIRMED,
        points=[p1],
        fit_score=0.9,
        confirmed_at=datetime.now(timezone.utc),
    )
    score = evaluate_breakout(match)
    assert score == 85.0
