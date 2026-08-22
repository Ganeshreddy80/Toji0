"""Comprehensive end-to-end pipeline and integration tests for Backtesting Engine (Sprint 7A)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock
import pytest

from backtesting_engine.core.enums import OrderType, PositionSide, ReplayStatus
from backtesting_engine.core.events import BacktestingEngineInitialized, BacktestingEngineShutdown
from backtesting_engine.core.exceptions import BacktestRepositoryError
from backtesting_engine.core.interfaces import IBacktestOrchestrator, IBacktestRepository
from backtesting_engine.core.models import BacktestConfig, BacktestResult, MarketBar
from backtesting_engine.core.orchestrator import BacktestOrchestrator
from backtesting_engine.core.plugin import BacktestingEnginePlugin
from backtesting_engine.core.repository import BacktestRepository
from backtesting_engine.core.state import BacktestStateStore
from research_platform.analysis.metrics_engine import MetricsEngine
from toji_platform.core.dependency_injection.container import Container
from toji_platform.core.event_bus import InMemoryEventBus
from toji_platform.core.types import ModuleState


def create_test_bars() -> list[MarketBar]:
    return [
        MarketBar(symbol="BTC/USDT", timeframe="1h", timestamp=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc), open=50000.0, high=51000.0, low=49500.0, close=50800.0, volume=10.0),
        MarketBar(symbol="BTC/USDT", timeframe="1h", timestamp=datetime(2025, 1, 1, 11, 0, tzinfo=timezone.utc), open=50800.0, high=52500.0, low=50500.0, close=52000.0, volume=15.0),
        MarketBar(symbol="BTC/USDT", timeframe="1h", timestamp=datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc), open=52000.0, high=53000.0, low=51500.0, close=52800.0, volume=12.0),
    ]


def test_backtest_orchestrator_end_to_end():
    event_bus = InMemoryEventBus()
    orch = BacktestOrchestrator()
    orch.initialize(event_bus=event_bus)

    cfg = BacktestConfig(
        name="Sprint 7A End-to-End Test",
        start_date=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
        end_date=datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc),
        initial_capital=100000.0,
        commission_rate=0.001,
        slippage_model="NONE",
    )

    bars = create_test_bars()
    initial_orders = [
        {"symbol": "BTC/USDT", "side": "LONG", "quantity": 1.0, "order_type": "MARKET"}
    ]

    res = orch.run_backtest(config=cfg, bars=bars, orders_to_place=initial_orders)

    assert res.status == ReplayStatus.COMPLETED
    assert res.final_equity > 100000.0  # Profit from price increase
    assert len(res.returns_series) == 2
    assert len(res.equity_curve) == 3
    assert len(res.fills) == 1
    assert len(res.trades) == 1
    assert res.trades[0].status.value == "OPEN"


def test_backtest_repository_atomic_persistence_and_eviction():
    failing_storage = MagicMock()
    failing_storage.write_rows.side_effect = RuntimeError("Storage write failed")
    failing_storage.execute.return_value = []

    repo = BacktestRepository(storage_engine=failing_storage)
    cfg = BacktestConfig(start_date=datetime(2025, 1, 1, tzinfo=timezone.utc), end_date=datetime(2025, 1, 2, tzinfo=timezone.utc))
    res = BacktestResult(backtest_id="bt-fail-1", config=cfg, replay_session_id="s1", status=ReplayStatus.COMPLETED, final_equity=100000.0)

    # Storage error prevents memory commit (Option A Atomic Persistence)
    with pytest.raises(BacktestRepositoryError, match="Failed to persist backtest result to storage"):
        repo.save_result(res)

    assert repo.load_result("bt-fail-1") is None
    assert len(repo.list_results()) == 0


def test_backtest_repository_cache_eviction_bounded_memory():
    repo = BacktestRepository()
    cfg = BacktestConfig(start_date=datetime(2025, 1, 1, tzinfo=timezone.utc), end_date=datetime(2025, 1, 2, tzinfo=timezone.utc))

    for i in range(1001):
        bt_id = f"bt-evict-{i}"
        res = BacktestResult(backtest_id=bt_id, config=cfg, replay_session_id=f"s-{i}", status=ReplayStatus.COMPLETED, final_equity=100000.0)
        repo.save_result(res)

    assert len(repo.list_results()) == 1000
    assert repo.load_result("bt-evict-0") is None
    assert repo.load_result("bt-evict-1000") is not None


def test_backtest_state_store_and_repository_ownership():
    state_store = BacktestStateStore()
    repo = BacktestRepository()
    cfg = BacktestConfig(start_date=datetime(2025, 1, 1, tzinfo=timezone.utc), end_date=datetime(2025, 1, 2, tzinfo=timezone.utc))
    res = BacktestResult(backtest_id="bt-own-1", config=cfg, replay_session_id="s1", status=ReplayStatus.COMPLETED)

    state_store.save_result(res)
    repo.save_result(res)

    assert state_store.get_result("bt-own-1") is not None
    assert repo.load_result("bt-own-1") is not None

    state_store.clear()
    assert state_store.get_result("bt-own-1") is None
    assert repo.load_result("bt-own-1") is not None  # Repository is persistent


def test_backtest_fail_closed_error_handling():
    orch = BacktestOrchestrator()
    orch.initialize()

    cfg = BacktestConfig(start_date=datetime(2025, 1, 1, tzinfo=timezone.utc), end_date=datetime(2025, 1, 2, tzinfo=timezone.utc))

    # Missing bars -> fails closed safely
    res = orch.run_backtest(config=cfg, bars=[])
    assert res.status == ReplayStatus.FAILED
    assert "No backtest configuration or historical market bars provided." in res.error_message


def test_backtest_plugin_lifecycle_and_di_wiring():
    event_bus = InMemoryEventBus()
    container = Container()

    plugin = BacktestingEnginePlugin(event_bus=event_bus, container=container)
    assert str(plugin.plugin_id) == "backtesting_engine"

    plugin.initialize()
    assert plugin.state == ModuleState.RUNNING

    assert container.has(IBacktestRepository)
    assert container.has(IBacktestOrchestrator)

    plugin.shutdown()
    assert plugin.state == ModuleState.STOPPED


def test_decoupled_research_platform_integration():
    """Verify BacktestResult return series is cleanly processed by ResearchPlatform MetricsEngine."""
    orch = BacktestOrchestrator()
    orch.initialize()

    cfg = BacktestConfig(start_date=datetime(2025, 1, 1, tzinfo=timezone.utc), end_date=datetime(2025, 1, 2, tzinfo=timezone.utc))
    bars = create_test_bars()
    orders = [{"symbol": "BTC/USDT", "side": "LONG", "quantity": 1.0, "order_type": "MARKET"}]

    bt_res = orch.run_backtest(config=cfg, bars=bars, orders_to_place=orders)

    # Feed Backtesting Engine returns output into Research Platform MetricsEngine
    metrics_engine = MetricsEngine()
    metrics = metrics_engine.calculate_metrics(returns=bt_res.returns_series, equity_curve=bt_res.equity_curve)

    assert metrics.total_trades > 0
    assert isinstance(metrics.sharpe_ratio, float)
    assert isinstance(metrics.max_drawdown, float)
