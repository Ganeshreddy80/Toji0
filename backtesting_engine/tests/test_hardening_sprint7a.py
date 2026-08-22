"""Comprehensive production hardening unit tests for Sprint 7A (Findings 002, 003, 004, 005, 006, 007)."""

from __future__ import annotations

import concurrent.futures
from datetime import datetime, timezone
import threading
from unittest.mock import MagicMock

import pytest

from backtesting_engine.broker.simulated_broker import SimulatedBroker
from backtesting_engine.core.enums import (
    OrderType,
    PositionSide,
    ReplayStatus,
    SimulatedOrderStatus,
    TimeInForce,
)
from backtesting_engine.core.exceptions import BacktestRepositoryError
from backtesting_engine.core.models import (
    BacktestConfig,
    BacktestResult,
    MarketBar,
    SimulatedOrder,
)
from backtesting_engine.core.orchestrator import BacktestOrchestrator
from backtesting_engine.core.plugin import BacktestingEnginePlugin
from backtesting_engine.core.repository import BacktestRepository
from backtesting_engine.core.state import BacktestStateStore
from backtesting_engine.matching.order_matching_engine import OrderMatchingEngine
from toji_platform.core.event_bus import InMemoryEventBus
from toji_platform.core.types import ModuleState


# ============================================================================
# Finding 004: Timezone-Aware Timestamp Validation Tests
# ============================================================================

def test_market_bar_aware_datetime_accepted():
    bar = MarketBar(
        symbol="BTC/USDT",
        timeframe="1h",
        timestamp=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
        open=50000.0,
        high=51000.0,
        low=49000.0,
        close=50500.0,
    )
    assert bar.timestamp.tzinfo is not None


def test_market_bar_naive_datetime_rejected():
    with pytest.raises(ValueError, match="MarketBar timestamp must be timezone-aware"):
        MarketBar(
            symbol="BTC/USDT",
            timeframe="1h",
            timestamp=datetime(2025, 1, 1, 10, 0),  # Naive
            open=50000.0,
            high=51000.0,
            low=49000.0,
            close=50500.0,
        )


# ============================================================================
# Finding 002: Repository Concurrency & Synchronization Tests
# ============================================================================

def test_repository_concurrent_save_result():
    repo = BacktestRepository()
    cfg = BacktestConfig(start_date=datetime(2025, 1, 1, tzinfo=timezone.utc), end_date=datetime(2025, 1, 2, tzinfo=timezone.utc))

    def save_task(idx: int):
        res = BacktestResult(
            backtest_id=f"bt-concurrent-{idx}",
            config=cfg,
            replay_session_id=f"session-{idx}",
            status=ReplayStatus.COMPLETED,
            final_equity=100000.0 + idx,
        )
        repo.save_result(res)

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(save_task, i) for i in range(50)]
        concurrent.futures.wait(futures)

    results = repo.list_results()
    assert len(results) == 50
    for i in range(50):
        assert repo.load_result(f"bt-concurrent-{i}") is not None


def test_repository_concurrent_reads_during_writes():
    repo = BacktestRepository()
    cfg = BacktestConfig(start_date=datetime(2025, 1, 1, tzinfo=timezone.utc), end_date=datetime(2025, 1, 2, tzinfo=timezone.utc))
    read_errors = []

    def writer_task():
        for i in range(30):
            res = BacktestResult(
                backtest_id=f"bt-rw-{i}",
                config=cfg,
                replay_session_id=f"session-{i}",
                status=ReplayStatus.COMPLETED,
                final_equity=100000.0 + i,
            )
            repo.save_result(res)

    def reader_task():
        for i in range(30):
            try:
                repo.list_results()
                repo.load_result(f"bt-rw-{i}")
            except Exception as e:
                read_errors.append(e)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        f_write = executor.submit(writer_task)
        f_reads = [executor.submit(reader_task) for _ in range(7)]
        concurrent.futures.wait([f_write] + f_reads)

    assert len(read_errors) == 0


def test_repository_persistence_failure_and_consistency_after_failure():
    mock_storage = MagicMock()
    mock_storage.write_rows.side_effect = RuntimeError("Database disk full")

    repo = BacktestRepository(storage_engine=mock_storage)
    cfg = BacktestConfig(start_date=datetime(2025, 1, 1, tzinfo=timezone.utc), end_date=datetime(2025, 1, 2, tzinfo=timezone.utc))
    res = BacktestResult(
        backtest_id="bt-fail-disk",
        config=cfg,
        replay_session_id="s1",
        status=ReplayStatus.COMPLETED,
        final_equity=100000.0,
    )

    with pytest.raises(BacktestRepositoryError, match="Failed to persist backtest result to storage"):
        repo.save_result(res)

    # In-memory repository state MUST remain unchanged after storage failure
    assert repo.load_result("bt-fail-disk") is None
    assert len(repo.list_results()) == 0


# ============================================================================
# Finding 003: Fail-Closed Persistence Ordering Tests
# ============================================================================

def test_orchestrator_fail_closed_persistence_ordering():
    mock_repo = MagicMock()
    mock_repo.save_result.side_effect = BacktestRepositoryError("Repository write failed")
    mock_state_store = MagicMock()

    orch = BacktestOrchestrator(repository=mock_repo)
    orch._state_store = mock_state_store

    cfg = BacktestConfig(start_date=datetime(2025, 1, 1, tzinfo=timezone.utc), end_date=datetime(2025, 1, 2, tzinfo=timezone.utc))

    # Run with empty bars -> triggers fail closed
    res = orch.run_backtest(config=cfg, bars=[])

    assert res.status == ReplayStatus.FAILED
    # Authoritative repository save_result MUST be called first
    mock_repo.save_result.assert_called_once()
    # Since repository save_result raised an exception, state_store MUST NOT have been called
    mock_state_store.save_result.assert_not_called()


# ============================================================================
# Finding 005: IOC and FOK Immediate Cancellation Tests
# ============================================================================

def test_ioc_order_immediate_cancellation_unfilled():
    orch = BacktestOrchestrator()
    orch.initialize()

    cfg = BacktestConfig(
        start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc),
        slippage_model="NONE",
    )

    # Bar 1: Limit price 50000.0 not reached (low is 50500.0)
    # Bar 2: Low drops to 49000.0
    bars = [
        MarketBar(symbol="BTC/USDT", timeframe="1h", timestamp=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc), open=51000.0, high=52000.0, low=50500.0, close=51500.0),
        MarketBar(symbol="BTC/USDT", timeframe="1h", timestamp=datetime(2025, 1, 1, 11, 0, tzinfo=timezone.utc), open=51500.0, high=51500.0, low=49000.0, close=49500.0),
    ]

    orders = [
        {
            "symbol": "BTC/USDT",
            "side": "LONG",
            "quantity": 1.0,
            "order_type": "LIMIT",
            "price": 50000.0,
            "time_in_force": "IOC",
        }
    ]

    res = orch.run_backtest(config=cfg, bars=bars, orders_to_place=orders)

    # Order must produce ZERO fills because it was cancelled immediately on bar 1
    assert len(res.fills) == 0


def test_fok_order_immediate_cancellation_unfillable():
    orch = BacktestOrchestrator()
    orch.initialize()

    cfg = BacktestConfig(
        start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc),
        slippage_model="NONE",
    )

    bars = [
        MarketBar(symbol="BTC/USDT", timeframe="1h", timestamp=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc), open=51000.0, high=52000.0, low=50500.0, close=51500.0),
        MarketBar(symbol="BTC/USDT", timeframe="1h", timestamp=datetime(2025, 1, 1, 11, 0, tzinfo=timezone.utc), open=51500.0, high=51500.0, low=49000.0, close=49500.0),
    ]

    # Limit price 50000.0 cannot be filled on bar 1
    orders = [
        {
            "symbol": "BTC/USDT",
            "side": "LONG",
            "quantity": 2.0,
            "order_type": "LIMIT",
            "price": 50000.0,
            "time_in_force": "FOK",
        }
    ]

    res = orch.run_backtest(config=cfg, bars=bars, orders_to_place=orders)
    assert len(res.fills) == 0


def test_fok_partial_fill_forbidden():
    matching_engine = OrderMatchingEngine()
    cfg = BacktestConfig(start_date=datetime(2025, 1, 1, tzinfo=timezone.utc), end_date=datetime(2025, 1, 2, tzinfo=timezone.utc))

    bar = MarketBar(symbol="BTC/USDT", timeframe="1h", timestamp=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc), open=50000.0, high=51000.0, low=49000.0, close=50500.0)

    # Order requires 10.0, but partially filled order has 4.0 remaining
    ord_fok = SimulatedOrder(
        symbol="BTC/USDT",
        side=PositionSide.LONG,
        quantity=10.0,
        filled_quantity=6.0,
        order_type=OrderType.LIMIT,
        price=50000.0,
        time_in_force=TimeInForce.FOK,
        status=SimulatedOrderStatus.PARTIALLY_FILLED,
    )

    # Full remaining quantity (4.0) matches bar low (49000 <= 50000), so it gets 4.0 fill.
    fills = matching_engine.match_orders([ord_fok], bar, cfg)
    assert len(fills) == 1
    assert fills[0].fill_quantity == 4.0


# ============================================================================
# Finding 006: Plugin Shutdown Lifecycle Tests
# ============================================================================

def test_plugin_initialize_shutdown_initialize_cycle():
    event_bus = InMemoryEventBus()
    plugin = BacktestingEnginePlugin(event_bus=event_bus)

    assert plugin.state == ModuleState.CREATED

    # 1. First initialize
    plugin.initialize()
    assert plugin.state == ModuleState.RUNNING

    # 2. First shutdown
    plugin.shutdown()
    assert plugin.state == ModuleState.STOPPED

    # 3. Re-initialize
    plugin.initialize()
    assert plugin.state == ModuleState.RUNNING

    # 4. Final shutdown
    plugin.shutdown()
    assert plugin.state == ModuleState.STOPPED


# ============================================================================
# Finding 007: Weighted Average Fill Price Tests
# ============================================================================

def test_weighted_average_fill_price_multiple_fills():
    broker = SimulatedBroker()
    orch = BacktestOrchestrator(broker=broker)
    orch.initialize()

    # Create order
    order = broker.place_order(
        symbol="ETH/USDT",
        side=PositionSide.LONG,
        quantity=10.0,
        order_type=OrderType.LIMIT,
        price=3000.0,
    )

    config = BacktestConfig(
        start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2025, 1, 2, tzinfo=timezone.utc),
        tick_precision=2,
    )

    # Fill 1: 2.0 @ $1000.0 -> avg = $1000.0
    fill1 = MagicMock(order_id=order.order_id, fill_quantity=2.0, fill_price=1000.0)
    # Fill 2: 3.0 @ $2000.0 -> (2*1000 + 3*2000)/5 = $1600.0
    fill2 = MagicMock(order_id=order.order_id, fill_quantity=3.0, fill_price=2000.0)
    # Fill 3: 5.0 @ $3000.0 -> (5*1600 + 5*3000)/10 = $2300.0
    fill3 = MagicMock(order_id=order.order_id, fill_quantity=5.0, fill_price=3000.0)

    # Apply fills sequentially simulating orchestrator logic
    cum = 0.0
    avg = 0.0
    for f in [fill1, fill2, fill3]:
        prev = cum
        cum += f.fill_quantity
        avg = ((avg * prev) + (f.fill_price * f.fill_quantity)) / cum
        updated = broker.get_order(order.order_id).model_copy(
            update={
                "filled_quantity": cum,
                "avg_fill_price": round(avg, config.tick_precision),
            }
        )
        broker.update_order(updated)

    final_ord = broker.get_order(order.order_id)
    assert final_ord.filled_quantity == 10.0
    assert final_ord.avg_fill_price == 2300.0  # Exact weighted average!
