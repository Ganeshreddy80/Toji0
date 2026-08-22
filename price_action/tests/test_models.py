"""Unit tests for Price Action Engine models."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from price_action.core.enums import PatternDirection, PatternStatus, PatternType
from price_action.core.models import (
    PatternPoint,
    Trendline,
    PatternCandidate,
    PatternMatch,
    PatternState,
    PatternSnapshot,
    PatternMetadata,
    PatternStatistics,
)


def test_pattern_point_immutability():
    """Verify that PatternPoint is frozen and validated properly."""
    dt = datetime.now(timezone.utc)
    point = PatternPoint(price=100.5, timestamp=dt, index=12, point_label="A")

    assert point.price == 100.5
    assert point.index == 12
    assert point.point_label == "A"

    # Immutability check
    with pytest.raises(ValidationError):
        # Trying to mutate attributes in a frozen Pydantic model raises ValidationError or AttributeError
        # Depending on Pydantic configuration, frozen models block setting attributes
        point.price = 101.0  # type: ignore[misc]

    # Negative price validation
    with pytest.raises(ValidationError):
        PatternPoint(price=-1.0, timestamp=dt, index=12, point_label="A")


def test_trendline_slope_calculation():
    """Verify Trendline immutability and attributes."""
    dt = datetime.now(timezone.utc)
    p1 = PatternPoint(price=10.0, timestamp=dt, index=0, point_label="Start")
    p2 = PatternPoint(price=20.0, timestamp=dt, index=10, point_label="End")

    trend = Trendline(start_point=p1, end_point=p2, slope=1.0, intercept=10.0)
    assert trend.slope == 1.0
    assert trend.intercept == 10.0

    with pytest.raises(ValidationError):
        trend.slope = 2.0  # type: ignore[misc]


def test_pattern_candidate_serialization():
    """Verify that PatternCandidate serializes and deserializes correctly."""
    dt = datetime.now(timezone.utc)
    p1 = PatternPoint(price=50.0, timestamp=dt, index=5, point_label="P1")
    candidate = PatternCandidate(
        candidate_id="uuid-cand-123",
        symbol="BTCUSDT",
        timeframe="1h",
        pattern_type=PatternType.DOUBLE_TOP,
        direction=PatternDirection.BEARISH,
        points=[p1],
        score=0.95,
        detected_at=dt,
    )

    dumped = candidate.model_dump(mode="json")
    assert dumped["candidate_id"] == "uuid-cand-123"
    assert dumped["pattern_type"] == "DOUBLE_TOP"
    assert dumped["direction"] == "BEARISH"
    assert len(dumped["points"]) == 1

    loaded = PatternCandidate(**dumped)
    assert loaded.candidate_id == "uuid-cand-123"
    assert loaded.points[0].price == 50.0


def test_pattern_match_lifecycle_serialization():
    """Verify PatternMatch properties and lifecycle states."""
    dt = datetime.now(timezone.utc)
    match = PatternMatch(
        match_id="uuid-match-456",
        symbol="ETHUSDT",
        timeframe="15m",
        pattern_type=PatternType.HEAD_AND_SHOULDERS,
        direction=PatternDirection.BEARISH,
        status=PatternStatus.CONFIRMED,
        fit_score=0.88,
        confirmed_at=dt,
        completed_at=dt,
    )

    assert match.status == PatternStatus.CONFIRMED
    assert match.completed_at == dt

    dumped = match.model_dump(mode="json")
    loaded = PatternMatch(**dumped)
    assert loaded.match_id == "uuid-match-456"
    assert loaded.status == PatternStatus.CONFIRMED


def test_pattern_state_and_snapshot():
    """Verify Pydantic structures of PatternState and PatternSnapshot."""
    dt = datetime.now(timezone.utc)
    state = PatternState(
        symbol="BTCUSDT",
        timeframe="1h",
        active_patterns=[],
        candidate_patterns=[],
        historical_patterns=[],
        updated_at=dt,
    )

    snapshot = PatternSnapshot(
        snapshot_id="uuid-snap-999",
        symbol="BTCUSDT",
        timestamp=dt,
        states={"1h": state},
    )

    assert snapshot.states["1h"].symbol == "BTCUSDT"
    dumped = snapshot.model_dump(mode="json")
    loaded = PatternSnapshot(**dumped)
    assert loaded.snapshot_id == "uuid-snap-999"
    assert loaded.states["1h"].updated_at == dt


def test_statistics_validation():
    """Verify PatternStatistics limits and bounds."""
    dt = datetime.now(timezone.utc)
    stats = PatternStatistics(
        symbol="BTCUSDT",
        total_detected=10,
        by_type={"DOUBLE_TOP": 5, "DOUBLE_BOTTOM": 5},
        by_status={"COMPLETED": 8, "INVALIDATED": 2},
        win_rate=0.8,
        updated_at=dt,
    )

    assert stats.win_rate == 0.8

    # Win rate bound validation check
    with pytest.raises(ValidationError):
        PatternStatistics(
            symbol="BTCUSDT",
            total_detected=10,
            win_rate=1.5,
            updated_at=dt,
        )
