"""Unit tests for Trading Context models."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from market_intelligence.core.models import MarketState
from strategy.core.models import StrategyState
from trading_context.core.models import (
    TradingContext,
    ContextMetadata,
    TradingContextSnapshot,
)


@pytest.fixture
def base_states() -> tuple[MarketState, StrategyState]:
    """Helper to return base validated MarketState and StrategyState."""
    dt = datetime.now(timezone.utc)
    market_state = MarketState(
        symbol="BTCUSDT",
        timeframe="1h",
        updated_at=dt,
    )
    strategy_state = StrategyState(
        symbol="BTCUSDT",
        timeframe="1h",
        updated_at=dt,
    )
    return market_state, strategy_state


def test_metadata_validation():
    """Verify ContextMetadata construction and constraints."""
    meta = ContextMetadata(
        engine_versions={"platform": "1.0.0"},
        replay_hash="hash-123",
        pipeline_version="1.0.0",
        source_events=["system.market_state_updated"],
    )
    assert meta.engine_versions["platform"] == "1.0.0"
    assert meta.replay_hash == "hash-123"
    assert meta.pipeline_version == "1.0.0"
    assert meta.source_events == ["system.market_state_updated"]
    assert isinstance(meta.creation_timestamp, datetime)

    # Immutability check
    with pytest.raises(ValidationError):
        meta.pipeline_version = "2.0.0"


def test_trading_context_validation(base_states):
    """Verify TradingContext holds all states and freezes properties."""
    market_state, strategy_state = base_states
    
    context = TradingContext(
        symbol="BTCUSDT",
        timeframe="1h",
        market_state=market_state,
        strategy_state=strategy_state,
        generated_at=datetime.now(timezone.utc),
        replay_id="replay-abc",
        version="1.0.0",
    )

    assert context.symbol == "BTCUSDT"
    assert context.timeframe == "1h"
    assert context.market_state == market_state
    assert context.strategy_state == strategy_state
    assert context.pattern_state is None
    assert context.confluence_state is None
    assert context.strategy_signal is None
    assert context.replay_id == "replay-abc"
    assert context.version == "1.0.0"
    assert isinstance(context.metadata, ContextMetadata)

    # Immutability check
    with pytest.raises(ValidationError):
        context.symbol = "ETHUSDT"


def test_trading_context_snapshot(base_states):
    """Verify TradingContextSnapshot validation and mappings."""
    market_state, strategy_state = base_states
    dt = datetime.now(timezone.utc)
    
    context = TradingContext(
        symbol="BTCUSDT",
        timeframe="1h",
        market_state=market_state,
        strategy_state=strategy_state,
        generated_at=dt,
    )

    snapshot = TradingContextSnapshot(
        snapshot_id="snap-xyz",
        symbol="BTCUSDT",
        timestamp=dt,
        states={"1h": context},
    )

    assert snapshot.snapshot_id == "snap-xyz"
    assert snapshot.symbol == "BTCUSDT"
    assert snapshot.timestamp == dt
    assert snapshot.states["1h"] == context

    # Immutability check
    with pytest.raises(ValidationError):
        snapshot.snapshot_id = "new-id"
