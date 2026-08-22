"""Unit tests for Strategy models."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from price_action.core.enums import PatternDirection
from strategy.core.enums import StrategyDecision, StrategyType
from strategy.core.models import (
    StrategySignal,
    StrategyState,
    StrategySnapshot,
)


def test_strategy_signal_validation():
    """Verify that StrategySignal validates fields, constraints, and freezes properties."""
    now = datetime.now(timezone.utc)
    
    # Valid model
    signal = StrategySignal(
        signal_id="sig-123",
        symbol="BTCUSDT",
        timeframe="1h",
        direction=PatternDirection.BULLISH,
        strategy_type=StrategyType.TREND_FOLLOWING,
        decision=StrategyDecision.BUY,
        confidence=85.5,
        confluence_score=90.0,
        reasoning="Bullish trend structure confirmed.",
        supporting_factors=["BOS", "Trend"],
        conflicting_factors=[],
        detected_at=now,
    )
    
    assert signal.signal_id == "sig-123"
    assert signal.symbol == "BTCUSDT"
    assert signal.timeframe == "1h"
    assert signal.direction == PatternDirection.BULLISH
    assert signal.strategy_type == StrategyType.TREND_FOLLOWING
    assert signal.decision == StrategyDecision.BUY
    assert signal.confidence == 0.855
    assert signal.confluence_score == 90.0
    assert signal.reasoning == "Bullish trend structure confirmed."
    assert signal.supporting_factors == ["BOS", "Trend"]
    assert signal.conflicting_factors == []
    assert signal.detected_at == now

    # Immutability check
    with pytest.raises(ValidationError):
        # Frozen model properties should not be modifiable
        signal.confidence = 95.0

    # ge/le constraints validation
    with pytest.raises(ValidationError):
        # negative confidence is invalid
        StrategySignal(
            signal_id="sig-123",
            symbol="BTCUSDT",
            timeframe="1h",
            direction=PatternDirection.BULLISH,
            strategy_type=StrategyType.TREND_FOLLOWING,
            confidence=-0.5,  # negative confidence raises ValidationError
            confluence_score=90.0,
            reasoning="Test",
            detected_at=now,
        )

    with pytest.raises(ValidationError):
        # confidence too low
        StrategySignal(
            signal_id="sig-123",
            symbol="BTCUSDT",
            timeframe="1h",
            direction=PatternDirection.BULLISH,
            strategy_type=StrategyType.TREND_FOLLOWING,
            confidence=-5.0,  # invalid
            confluence_score=90.0,
            reasoning="Too low confidence",
            detected_at=now,
        )


def test_strategy_state_validation():
    """Verify StrategyState construction, defaults, and frozen behaviors."""
    now = datetime.now(timezone.utc)
    signal = StrategySignal(
        signal_id="sig-123",
        symbol="BTCUSDT",
        timeframe="1h",
        direction=PatternDirection.BULLISH,
        strategy_type=StrategyType.TREND_FOLLOWING,
        decision=StrategyDecision.BUY,
        confidence=85.5,
        confluence_score=90.0,
        reasoning="Bullish trend structure confirmed.",
        detected_at=now,
    )

    state = StrategyState(
        symbol="BTCUSDT",
        timeframe="1h",
        active_strategy=StrategyType.TREND_FOLLOWING,
        latest_signal=signal,
        historical_strategies=[signal],
        updated_at=now,
    )

    assert state.symbol == "BTCUSDT"
    assert state.timeframe == "1h"
    assert state.active_strategy == StrategyType.TREND_FOLLOWING
    assert state.latest_signal == signal
    assert len(state.historical_strategies) == 1
    assert state.updated_at == now

    # Verify defaults
    default_state = StrategyState(
        symbol="BTCUSDT",
        timeframe="15m",
    )
    assert default_state.active_strategy is None
    assert default_state.latest_signal is None
    assert default_state.historical_strategies == []
    assert isinstance(default_state.updated_at, datetime)

    # Verify immutability
    with pytest.raises(ValidationError):
        default_state.active_strategy = StrategyType.BREAKOUT


def test_strategy_snapshot_validation():
    """Verify StrategySnapshot model."""
    now = datetime.now(timezone.utc)
    state = StrategyState(
        symbol="BTCUSDT",
        timeframe="1h",
        active_strategy=StrategyType.TREND_FOLLOWING,
    )

    snapshot = StrategySnapshot(
        snapshot_id="snap-456",
        symbol="BTCUSDT",
        timestamp=now,
        states={"1h": state},
    )

    assert snapshot.snapshot_id == "snap-456"
    assert snapshot.symbol == "BTCUSDT"
    assert snapshot.timestamp == now
    assert snapshot.states["1h"] == state

    # Verify immutability
    with pytest.raises(ValidationError):
        snapshot.symbol = "ETHUSDT"
