"""Tests for the Position Sizing Engine replay determinism and thread-safety."""

from __future__ import annotations

import concurrent.futures
from datetime import datetime, timezone
import pytest

from trading_context.core.models import TradingContext
from market_intelligence.core.models import MarketState, VolumeState
from market_intelligence.core.enums import VolumeExpansionState
from risk_engine.core.models import RiskAssessment
from risk_engine.core.enums import RiskDecision
from strategy.core.models import StrategyState
from position_sizing.core.enums import SizingStatus
from position_sizing.core.models import (
    PositionSizingResult,
    PositionSizingState,
    PositionSizingSnapshot,
)
from position_sizing.analysis.position_engine import PositionSizingEngine
from position_sizing.core.state import PositionSizingStateStore


@pytest.fixture
def dummy_context() -> TradingContext:
    dt = datetime.now(timezone.utc)
    volume_state = VolumeState(
        symbol="BTCUSDT",
        timeframe="1h",
        volume_ma=100.0,
        normalized_volume=1.0,
        expansion_state=VolumeExpansionState.NORMAL,
        atr=2.5,
    )
    market_state = MarketState(
        symbol="BTCUSDT",
        timeframe="1h",
        volume=volume_state,
        updated_at=dt,
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
    """Verify that running identical parameters yields exact-match sizing results."""
    engine = PositionSizingEngine()
    risk = RiskAssessment(overall_score=95.0, decision=RiskDecision.ALLOW)

    # Execute sizing calculation 3 times sequentially
    results = []
    for _ in range(3):
        res = engine.calculate_size(
            dummy_context,
            risk,
            account_balance=100000.0,
            risk_percent=0.01,
            stop_distance=5.0,
            take_profit_distance=10.0,
            entry_price=100.0,
        )
        results.append(res)

    # Verify all outcomes match exactly
    assert results[0].success == results[1].success == results[2].success
    assert results[0].status == results[1].status == results[2].status
    assert results[0].position_size.quantity == results[1].position_size.quantity == results[2].position_size.quantity
    assert results[0].position_size.margin_required == results[1].position_size.margin_required == results[2].position_size.margin_required


def test_concurrent_state_store_access():
    """Verify that StateStore manages updates correctly under concurrent workloads."""
    store = PositionSizingStateStore(history_limit=100)
    now = datetime.now(timezone.utc)

    # Initial snapshot
    snap = PositionSizingSnapshot(
        snapshot_id="test-snap",
        symbol="BTCUSDT",
        timestamp=now,
        states={},
    )
    store.update_snapshot(snap)

    def write_task(i: int):
        res = PositionSizingResult(
            success=True,
            status=SizingStatus.APPROVED,
        )
        state_update = PositionSizingState(
            symbol="BTCUSDT",
            timeframe=f"tf-{i}",
            result=res,
            updated_at=now,
        )
        store.update_timeframe_state("BTCUSDT", f"tf-{i}", state_update)

    # Run concurrent threads
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(write_task, i) for i in range(20)]
        concurrent.futures.wait(futures)

    # Check store has correct number of timeframe states
    final_snap = store.get_snapshot("BTCUSDT")
    assert final_snap is not None
    assert len(final_snap.states) == 20
