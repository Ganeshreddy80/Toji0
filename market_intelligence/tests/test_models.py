"""Unit tests for Market Intelligence Layer Pydantic models."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from market_intelligence.core.enums import (
    MarketPhase,
    SessionName,
    StructureBias,
    SwingType,
    TrendDirection,
    VolumeExpansionState,
    ZoneType,
)
from market_intelligence.core.models import (
    ConfidenceState,
    ContextState,
    LiquidityState,
    MarketSnapshot,
    MarketState,
    SessionState,
    StoryState,
    SwingPoint,
    TrendState,
    VolumeState,
    Zone,
)


def test_swing_point_model():
    """Verify SwingPoint creation, validation, and immutability."""
    now = datetime.now(timezone.utc)
    sp = SwingPoint(
        symbol="BTCUSDT",
        timeframe="1h",
        point_type=SwingType.HIGH,
        price=60000.0,
        timestamp=now,
        index=10,
    )
    assert sp.symbol == "BTCUSDT"
    assert sp.point_type == SwingType.HIGH
    assert sp.price == 60000.0
    assert sp.timestamp == now
    assert sp.index == 10

    # Immutability
    with pytest.raises((ValidationError, AttributeError)):
        sp.price = 61000.0  # type: ignore

    # Validation: price must be > 0
    with pytest.raises(ValidationError):
        SwingPoint(
            symbol="BTCUSDT",
            timeframe="1h",
            point_type=SwingType.HIGH,
            price=-10.0,
            timestamp=now,
            index=10,
        )

    # Validation: index must be >= 0
    with pytest.raises(ValidationError):
        SwingPoint(
            symbol="BTCUSDT",
            timeframe="1h",
            point_type=SwingType.HIGH,
            price=60000.0,
            timestamp=now,
            index=-1,
        )


def test_trend_state_model():
    """Verify TrendState creation, validation, and immutability."""
    now = datetime.now(timezone.utc)
    trend = TrendState(
        symbol="BTCUSDT",
        timeframe="1h",
        direction=TrendDirection.UP,
        strength=0.85,
        start_time=now,
        end_time=now,
    )
    assert trend.direction == TrendDirection.UP
    assert trend.strength == 0.85

    with pytest.raises((ValidationError, AttributeError)):
        trend.strength = 0.9  # type: ignore

    # Validation: strength must be between 0 and 1
    with pytest.raises(ValidationError):
        TrendState(
            symbol="BTCUSDT",
            timeframe="1h",
            direction=TrendDirection.UP,
            strength=1.5,
            start_time=now,
            end_time=now,
        )


def test_liquidity_state_model():
    """Verify LiquidityState creation and defaults."""
    liq = LiquidityState(
        symbol="BTCUSDT",
        timeframe="1h",
        buy_side_pools=[59000.0, 59500.0],
        sell_side_pools=[61000.0],
        swept_levels=[60500.0],
    )
    assert liq.buy_side_pools == [59000.0, 59500.0]
    assert liq.sell_side_pools == [61000.0]
    assert liq.swept_levels == [60500.0]


def test_zone_model():
    """Verify Zone model validation."""
    zone = Zone(
        symbol="BTCUSDT",
        timeframe="1h",
        zone_type=ZoneType.DEMAND,
        upper_bound=59200.0,
        lower_bound=59000.0,
        volume_at_creation=125.5,
        mitigations_count=2,
        is_invalidated=False,
    )
    assert zone.zone_type == ZoneType.DEMAND
    assert zone.upper_bound == 59200.0

    with pytest.raises(ValidationError):
        Zone(
            symbol="BTCUSDT",
            timeframe="1h",
            zone_type=ZoneType.DEMAND,
            upper_bound=-10.0,
            lower_bound=59000.0,
            volume_at_creation=125.5,
        )


def test_session_state_model():
    """Verify SessionState validation."""
    session = SessionState(
        symbol="BTCUSDT",
        session_name=SessionName.NEW_YORK,
        session_high=61500.0,
        session_low=60200.0,
        is_broken=True,
    )
    assert session.session_name == SessionName.NEW_YORK
    assert session.session_high == 61500.0


def test_volume_state_model():
    """Verify VolumeState validation."""
    vol = VolumeState(
        symbol="BTCUSDT",
        timeframe="1h",
        volume_ma=150.0,
        normalized_volume=2.5,
        expansion_state=VolumeExpansionState.EXPANSION,
    )
    assert vol.expansion_state == VolumeExpansionState.EXPANSION
    assert vol.normalized_volume == 2.5


def test_context_state_model():
    """Verify ContextState validation."""
    now = datetime.now(timezone.utc)
    ctx = ContextState(
        symbol="BTCUSDT",
        market_phase=MarketPhase.ACCUMULATION,
        dominant_bias=StructureBias.RANGING,
        key_support=58000.0,
        key_resistance=62000.0,
        timestamp=now,
    )
    assert ctx.market_phase == MarketPhase.ACCUMULATION
    assert ctx.dominant_bias == StructureBias.RANGING


def test_confidence_state_model():
    """Verify ConfidenceState validation."""
    now = datetime.now(timezone.utc)
    conf = ConfidenceState(
        symbol="BTCUSDT",
        score=0.95,
        factors={"trend_alignment": 1.0, "volume_confirmation": 0.9},
        timestamp=now,
    )
    assert conf.score == 0.95
    assert conf.factors["trend_alignment"] == 1.0


def test_story_state_model():
    """Verify StoryState validation."""
    now = datetime.now(timezone.utc)
    story = StoryState(
        symbol="BTCUSDT",
        narrative="Market is consolidating in accumulation phase.",
        supporting_events=["SwingHighSwept", "VolumeExpansion"],
        generated_at=now,
    )
    assert story.narrative == "Market is consolidating in accumulation phase."
    assert len(story.supporting_events) == 2


def test_market_state_model():
    """Verify MarketState aggregation model."""
    now = datetime.now(timezone.utc)
    trend = TrendState(
        symbol="BTCUSDT",
        timeframe="1h",
        direction=TrendDirection.UP,
        strength=0.85,
        start_time=now,
        end_time=now,
    )
    ms = MarketState(
        symbol="BTCUSDT",
        timeframe="1h",
        swings=[],
        trend=trend,
        liquidity=None,
        zones=[],
        session=None,
        volume=None,
        context=None,
        confidence=None,
        story=None,
        updated_at=now,
    )
    assert ms.symbol == "BTCUSDT"
    assert ms.timeframe == "1h"
    assert ms.trend is not None
    assert ms.trend.direction == TrendDirection.UP


def test_market_snapshot_model():
    """Verify MarketSnapshot creation and nested access."""
    now = datetime.now(timezone.utc)
    trend = TrendState(
        symbol="BTCUSDT",
        timeframe="1h",
        direction=TrendDirection.UP,
        strength=0.85,
        start_time=now,
        end_time=now,
    )
    ms = MarketState(
        symbol="BTCUSDT",
        timeframe="1h",
        swings=[],
        trend=trend,
        liquidity=None,
        zones=[],
        session=None,
        volume=None,
        context=None,
        confidence=None,
        story=None,
        updated_at=now,
    )
    snapshot = MarketSnapshot(
        snapshot_id="snap-12345",
        symbol="BTCUSDT",
        timestamp=now,
        states={"1h": ms},
    )
    assert snapshot.snapshot_id == "snap-12345"
    assert snapshot.symbol == "BTCUSDT"
    assert "1h" in snapshot.states
    assert snapshot.states["1h"].trend is not None
    assert snapshot.states["1h"].trend.direction == TrendDirection.UP
