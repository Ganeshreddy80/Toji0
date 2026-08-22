"""Unit and integration tests for replay safety and concurrent access in the Risk Engine."""

from __future__ import annotations

import concurrent.futures
from datetime import datetime, timezone
import pytest
from unittest.mock import MagicMock

from trading_context.core.models import TradingContext
from market_intelligence.core.models import MarketState, SessionState
from market_intelligence.core.enums import SessionName
from strategy.core.models import StrategyState
from risk_engine.core.enums import RiskDecision
from risk_engine.core.models import RiskState, RiskSnapshot, RiskAssessment
from risk_engine.core.state import RiskStateStore
from risk_engine.core.repository import RiskRepository
from risk_engine.analysis.risk_engine import RiskEngine
from risk_engine.core.orchestrator import RiskOrchestrator


@pytest.fixture
def dummy_context() -> TradingContext:
    dt = datetime.now(timezone.utc)
    session_state = SessionState(
        symbol="BTCUSDT",
        session_name=SessionName.NEW_YORK,
        session_high=50000.0,
        session_low=49000.0,
    )
    market_state = MarketState(
        symbol="BTCUSDT",
        timeframe="1h",
        updated_at=dt,
        session=session_state,
    )
    strategy_state = StrategyState(symbol="BTCUSDT", timeframe="1h", updated_at=dt)
    return TradingContext(
        symbol="BTCUSDT",
        timeframe="1h",
        market_state=market_state,
        strategy_state=strategy_state,
        generated_at=dt,
    )


def test_replay_determinism(dummy_context):
    """Verify that processing the same TradingContext twice results in identical RiskAssessment details."""
    dt = datetime(2026, 6, 24, 12, 0, 0, tzinfo=timezone.utc)
    ctx = dummy_context.model_copy(update={"generated_at": dt})

    # Run 1
    state_store_1 = RiskStateStore()
    repo_1 = RiskRepository()
    engine_1 = RiskEngine()
    orchestrator_1 = RiskOrchestrator()
    orchestrator_1.initialize(state_store=state_store_1, repository=repo_1, risk_engine=engine_1)

    state_1 = orchestrator_1.process_context(
        ctx,
        current_daily_loss_pct=0.01,
        current_drawdown_pct=0.02,
        market_closed=False,
    )

    # Run 2 (identical inputs)
    state_store_2 = RiskStateStore()
    repo_2 = RiskRepository()
    engine_2 = RiskEngine()
    orchestrator_2 = RiskOrchestrator()
    orchestrator_2.initialize(state_store=state_store_2, repository=repo_2, risk_engine=engine_2)

    state_2 = orchestrator_2.process_context(
        ctx,
        current_daily_loss_pct=0.01,
        current_drawdown_pct=0.02,
        market_closed=False,
    )

    assert state_1 is not None
    assert state_2 is not None

    # Check that score, decision, factors, and violations match exactly
    assert state_1.symbol == state_2.symbol
    assert state_1.timeframe == state_2.timeframe
    assert state_1.assessment.overall_score == state_2.assessment.overall_score
    assert state_1.assessment.decision == state_2.assessment.decision
    assert [f.id for f in state_1.assessment.factors] == [f.id for f in state_2.assessment.factors]
    assert state_1.assessment.violations == state_2.assessment.violations


def test_concurrent_state_store_access():
    """Verify that multiple threads can safely read/write to the RiskStateStore concurrently."""
    store = RiskStateStore(history_limit=2000)
    symbol = "BTCUSDT"
    dt = datetime.now(timezone.utc)

    # Initialize the base snapshot to update against
    base_snapshot = RiskSnapshot(
        snapshot_id="base",
        symbol=symbol,
        timestamp=dt,
        states={},
    )
    store.update_snapshot(base_snapshot)

    def worker(worker_id: int):
        # Create a dummy risk state
        assessment = RiskAssessment(overall_score=100.0, decision=RiskDecision.ALLOW)
        state = RiskState(
            symbol=symbol,
            timeframe=f"tf_{worker_id}",
            assessment=assessment,
            updated_at=dt,
        )
        # Safely update timeframe state
        store.update_timeframe_state(symbol, f"tf_{worker_id}", state)
        # Retrieve snapshot
        snap = store.get_snapshot(symbol)
        assert snap is not None
        assert f"tf_{worker_id}" in snap.states

    num_threads = 50
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(worker, i) for i in range(num_threads)]
        for future in concurrent.futures.as_completed(futures):
            # Retrieve results to check for exceptions raised in threads
            future.result()

    # Verify state store reflects updates from all workers
    final_snap = store.get_snapshot(symbol)
    assert final_snap is not None
    assert len(final_snap.states) == num_threads

    # Verify history captures every step (1 base + 50 threads = 51 snapshots)
    history = store.get_history(symbol, limit=2000)
    assert len(history) == num_threads + 1
