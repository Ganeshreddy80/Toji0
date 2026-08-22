"""Unit tests for volatility score calculation."""

from __future__ import annotations

from datetime import datetime, timezone
from price_action.core.models import PatternCandidate, PatternPoint, PatternMetadata
from price_action.core.enums import PatternDirection, PatternType
from price_action.quality.volatility_score import evaluate_volatility


def test_volatility_score_metadata():
    """Verify volatility score maps atr normalization from metadata."""
    meta = PatternMetadata(
        source_engine="test",
        version="1.0.0",
        atr_normalization=0.82,
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
    score = evaluate_volatility(cand)
    assert score == 82.0
