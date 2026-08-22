"""Unit and integration tests for replay safety and concurrent access."""

from __future__ import annotations

import concurrent.futures
from datetime import datetime, timezone
import pytest
from unittest.mock import MagicMock

from market_intelligence.core.models import MarketState
from strategy.core.models import StrategyState
from trading_context.core.models import (
    TradingContext,
    TradingContextSnapshot,
)
from trading_context.core.state import TradingContextStateStore
from trading_context.core.repository import TradingContextRepository
from trading_context.core.orchestrator import TradingContextOrchestrator


@pytest.fixture
def base_dt() -> datetime:
    return datetime.now(timezone.utc)


def test_replay_determinism(base_dt):
    """Verify that processing the same input states twice results in identical context properties (excluding IDs)."""
    # 1. Prepare identical inputs
    market_state = MarketState(symbol="BTCUSDT", timeframe="1h", updated_at=base_dt)
    strategy_state = StrategyState(symbol="BTCUSDT", timeframe="1h", updated_at=base_dt)

    m_snap = MagicMock()
    m_snap.states = {"1h": market_state}
    
    s_snap = MagicMock()
    s_snap.states = {"1h": strategy_state}

    # Run 1
    state_store_1 = TradingContextStateStore()
    repo_1 = TradingContextRepository()
    mock_market_store_1 = MagicMock()
    mock_market_store_1.get_snapshot.return_value = m_snap
    mock_strategy_store_1 = MagicMock()
    mock_strategy_store_1.get_snapshot.return_value = s_snap

    orchestrator_1 = TradingContextOrchestrator()
    orchestrator_1.initialize(
        state_store=state_store_1,
        repository=repo_1,
        market_state_store=mock_market_store_1,
        strategy_state_store=mock_strategy_store_1,
    )
    ctx1 = orchestrator_1.process_context("BTCUSDT", "1h")

    # Run 2 (identical configuration)
    state_store_2 = TradingContextStateStore()
    repo_2 = TradingContextRepository()
    mock_market_store_2 = MagicMock()
    mock_market_store_2.get_snapshot.return_value = m_snap
    mock_strategy_store_2 = MagicMock()
    mock_strategy_store_2.get_snapshot.return_value = s_snap

    orchestrator_2 = TradingContextOrchestrator()
    orchestrator_2.initialize(
        state_store=state_store_2,
        repository=repo_2,
        market_state_store=mock_market_store_2,
        strategy_state_store=mock_strategy_store_2,
    )
    ctx2 = orchestrator_2.process_context("BTCUSDT", "1h")

    assert ctx1 is not None
    assert ctx2 is not None

    # Verify identical fields
    assert ctx1.symbol == ctx2.symbol
    assert ctx1.timeframe == ctx2.timeframe
    assert ctx1.market_state == ctx2.market_state
    assert ctx1.strategy_state == ctx2.strategy_state
    assert ctx1.pattern_state == ctx2.pattern_state
    assert ctx1.confluence_state == ctx2.confluence_state
    assert ctx1.strategy_signal == ctx2.strategy_signal
    assert ctx1.version == ctx2.version
    assert ctx1.metadata.pipeline_version == ctx2.metadata.pipeline_version


def test_concurrent_state_store_access():
    """Verify that multiple threads can safely read/write to the TradingContextStateStore concurrently."""
    store = TradingContextStateStore(history_limit=2000)
    symbol = "BTCUSDT"
    dt = datetime.now(timezone.utc)
    
    # Initialize the base snapshot to update against
    base_snapshot = TradingContextSnapshot(
        snapshot_id="base",
        symbol=symbol,
        timestamp=dt,
        states={},
    )
    store.update_snapshot(base_snapshot)

    def worker(worker_id: int):
        # Create a dummy context
        ctx = TradingContext(
            symbol=symbol,
            timeframe=f"tf_{worker_id}",
            market_state=MarketState(symbol=symbol, timeframe=f"tf_{worker_id}", updated_at=dt),
            strategy_state=StrategyState(symbol=symbol, timeframe=f"tf_{worker_id}", updated_at=dt),
            generated_at=dt,
        )
        # Safely update timeframe state
        store.update_timeframe_state(symbol, f"tf_{worker_id}", ctx)
        # Retrieve snapshot
        snap = store.get_snapshot(symbol)
        assert snap is not None
        assert f"tf_{worker_id}" in snap.states

    num_threads = 50
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(worker, i) for i in range(num_threads)]
        for future in concurrent.futures.as_completed(futures):
            future.result()  # Will raise exception if any assertion or error occurred

    # Verify state store reflects updates from all workers
    final_snap = store.get_snapshot(symbol)
    assert final_snap is not None
    assert len(final_snap.states) == num_threads
    
    # Verify history captures every step
    history = store.get_history(symbol, limit=2000)
    # The history contains: 1 base snapshot + num_threads updates = num_threads + 1 snapshots
    assert len(history) == num_threads + 1
