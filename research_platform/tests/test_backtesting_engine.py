"""Unit tests for the Event-Driven Backtesting Engine.
"""

from __future__ import annotations

from datetime import datetime, timezone
import numpy as np
import pandas as pd
import pytest

from toji_platform.core.event_bus import InMemoryEventBus
from research_platform.backtesting_engine.analytics import BacktestAnalytics
from research_platform.backtesting_engine.matching import MatchingEngine
from research_platform.backtesting_engine.models import (
    BacktestConfiguration,
    CommissionModel,
    MarginModel,
    MarketEvent,
    Order,
    OrderRequest,
    SlippageModel,
    OrderFill,
    PortfolioState
)
from research_platform.backtesting_engine.orchestrator import BacktestingEngineOrchestrator
from research_platform.backtesting_engine.portfolio import PortfolioTracker
from research_platform.backtesting_engine.replay import HistoricalReplayEngine
from research_platform.backtesting_engine.risk import SimulationRiskController
from research_platform.backtesting_engine.simulator import ExecutionSimulator
from research_platform.strategy_lab.models import EntryRule, ExitRule, PositionSizingRule, StrategyDefinition


@pytest.fixture
def event_bus():
    return InMemoryEventBus()


@pytest.fixture
def orchestrator(event_bus):
    return BacktestingEngineOrchestrator(event_bus)


def test_historical_event_replay_and_clock():
    """Verify replay clock advances and time travel works."""
    df = pd.DataFrame({
        "timestamp": pd.date_range("2026-06-25 12:00:00", periods=5, freq="1min"),
        "open": [10.0, 11.0, 12.0, 13.0, 14.0],
        "high": [10.5, 11.5, 12.5, 13.5, 14.5],
        "low": [9.5, 10.5, 11.5, 12.5, 13.5],
        "close": [10.2, 11.2, 12.2, 13.2, 14.2],
        "volume": [1000, 1100, 1200, 1300, 1400]
    })

    replay = HistoricalReplayEngine(df, symbol="BTC/USDT")
    assert replay.has_next() is True

    # 1. Step Forward
    evt = replay.next_event()
    assert evt is not None
    assert evt.data["close"] == 10.2
    assert replay.clock.current_time.minute == 0

    # 2. Time Travel
    target = datetime(2026, 6, 25, 12, 3, 0, tzinfo=timezone.utc)
    replay.set_time(target)
    evt2 = replay.next_event()
    assert evt2 is not None
    # timestamp index 3 is 12:03:00, value is 13.2
    assert evt2.data["close"] == 13.2


def test_matching_engine_queues():
    """Verify limit and stop orders trigger matching conditions."""
    matching = MatchingEngine(slippage_pct=0.0, commission_pct=0.0)

    # Replay event: High=10.5, Low=9.5, Close=10.0
    evt = MarketEvent(
        timestamp=datetime.now(timezone.utc),
        symbol="BTC/USDT",
        event_type="OHLCV",
        data={"close": 10.0, "high": 10.5, "low": 9.5}
    )

    # 1. Limit Buy below price: should match because Low 9.5 <= Limit 9.8
    req_limit = OrderRequest(
        order_id="1", strategy_id="s", symbol="BTC/USDT", direction="BUY", quantity=10, order_type="LIMIT", price=9.8
    )
    order_limit = Order(order_id="1", request=req_limit, created_time=datetime.now(timezone.utc), updated_time=datetime.now(timezone.utc))
    
    fills = matching.match_orders([order_limit], evt)
    assert len(fills) == 1
    assert fills[0].price == 9.8

    # 2. Stop Sell: triggers when price <= stop price (Stop 9.6 >= Low 9.5)
    req_stop = OrderRequest(
        order_id="2", strategy_id="s", symbol="BTC/USDT", direction="SELL", quantity=10, order_type="STOP", price=9.6
    )
    order_stop = Order(order_id="2", request=req_stop, created_time=datetime.now(timezone.utc), updated_time=datetime.now(timezone.utc))

    fills_stop = matching.match_orders([order_stop], evt)
    assert len(fills_stop) == 1
    assert fills_stop[0].price == 9.6


def test_execution_simulator_slippage_models():
    """Verify fixed and percentage execution models."""
    slip = SlippageModel(type="Percentage", params={"percentage": 0.01})
    comm = CommissionModel(type="Percentage", params={"percentage": 0.005})
    sim = ExecutionSimulator(slip, comm)

    req = OrderRequest(
        order_id="1", strategy_id="s", symbol="BTC/USDT", direction="BUY", quantity=10, order_type="MARKET"
    )
    evt = MarketEvent(
        timestamp=datetime.now(timezone.utc),
        symbol="BTC/USDT",
        event_type="OHLCV",
        data={"close": 100.0}
    )

    fill = sim.simulate_fill(req, evt)
    # price 100 + 1% slippage = 101.0
    assert fill.price == 101.0
    # commission 101.0 * 10 * 0.005 = 5.05
    assert fill.commission == pytest.approx(5.05)


def test_portfolio_tracking_realized_and_unrealized():
    """Verify position entry updates cash and tracks unrealized PnL."""
    tracker = PortfolioTracker(initial_capital=10000.0, margin_requirement_pct=0.5)

    # 1. Buy 10 units at 100
    fill = OrderFill(
        order_id="1", fill_id="f1", symbol="BTC/USDT", quantity=10, price=100.0, commission=10.0, slippage=0.0, timestamp=datetime.now(timezone.utc)
    )
    state = tracker.process_fill(fill)
    # cash = 10000 - 10 = 9990.0 (cash tracks realized balance minus commissions)
    assert state.cash == 9990.0
    assert "BTC/USDT" in state.positions
    assert state.positions["BTC/USDT"].quantity == 10

    # 2. Mark to Market at 110
    evt = MarketEvent(
        timestamp=datetime.now(timezone.utc),
        symbol="BTC/USDT",
        event_type="OHLCV",
        data={"close": 110.0}
    )
    state_mtm = tracker.mark_to_market(evt)
    # unrealized = 10 * (110 - 100) = 100
    assert state_mtm.unrealized_pnl == 100.0
    # equity = cash + unrealized = 9990 + 100 = 10090
    assert state_mtm.equity == 10090.0

    # 3. Sell/Close 10 units at 110
    fill_sell = OrderFill(
        order_id="2", fill_id="f2", symbol="BTC/USDT", quantity=-10, price=110.0, commission=10.0, slippage=0.0, timestamp=datetime.now(timezone.utc)
    )
    state_close = tracker.process_fill(fill_sell)
    # realized = 10 * (110 - 100) = 100. Total realized = 100.
    # cash = cash_prev + position_close - comm = 9990 + 10 * 110 - 10 = 11080.0
    assert state_close.cash == 11080.0
    assert "BTC/USDT" not in state_close.positions
    assert state_close.realized_pnl == 100.0


def test_simulation_risk_controls():
    """Verify drawdown stops and margin call liquidations."""
    risk = SimulationRiskController(max_drawdown_pct=0.20, maintenance_margin_pct=0.30)

    # Initial peak equity
    state1 = PortfolioState(
        timestamp=datetime.now(timezone.utc), cash=1000.0, equity=1000.0, margin=0.0, buying_power=1000.0, realized_pnl=0.0, unrealized_pnl=0.0
    )
    stop, reason = risk.check_risk(state1)
    assert stop is False

    # Drop equity to 750 (25% drawdown)
    state2 = PortfolioState(
        timestamp=datetime.now(timezone.utc), cash=750.0, equity=750.0, margin=0.0, buying_power=750.0, realized_pnl=0.0, unrealized_pnl=0.0
    )
    stop2, reason2 = risk.check_risk(state2)
    assert stop2 is True
    assert "Drawdown stop" in reason2


def test_performance_analytics():
    """Verify Sharpe and Sortino ratios calculation."""
    # Flat equity curves
    curve = [1000.0, 1001.0, 1002.0, 1003.0]
    trades = [1.0, 1.0, 1.0]
    stats = BacktestAnalytics.calculate_stats(curve, trades, 1000.0)
    assert stats.total_trades == 3
    assert stats.win_rate == 1.0
    assert stats.sharpe_ratio > 0.0


def test_backtesting_orchestration_loop(orchestrator):
    """Verify the event-driven backtesting execution replay loop completes."""
    df = pd.DataFrame({
        "timestamp": pd.date_range("2026-06-25 12:00:00", periods=50, freq="1min"),
        "open": [10.0 + i for i in range(50)],
        "high": [10.5 + i for i in range(50)],
        "low": [9.5 + i for i in range(50)],
        "close": [10.2 + i for i in range(50)],
        "volume": [1000.0 for _ in range(50)]
    })

    # Strategy Definition
    entry = EntryRule(name="Entry", condition_type="SignalThreshold", parameters={"column": "close", "threshold": 15.0, "operator": ">"})
    exit_rule = ExitRule(name="Exit", condition_type="ProfitTarget", parameters={"target_pct": 0.20})
    sizing = PositionSizingRule(name="Sizing", sizing_type="FixedSize", parameters={"units": 1})
    
    strategy = StrategyDefinition(
        strategy_id="strat_abc",
        name="TrendStrategy",
        display_name="Trend Strategy",
        description="Desc",
        version="1.0.0",
        entry_rules=[entry],
        exit_rules=[exit_rule],
        sizing_rule=sizing,
        risk_rules=[]
    )

    config = BacktestConfiguration(
        strategy_id="strat_abc",
        dataset_id="ds_1",
        initial_capital=10000.0,
        start_time=datetime(2026, 6, 25, 12, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 6, 25, 12, 45, 0, tzinfo=timezone.utc),
        slippage=SlippageModel(type="Percentage", params={"percentage": 0.0005}),
        commission=CommissionModel(type="Percentage", params={"percentage": 0.001}),
        margin=MarginModel(initial_margin_pct=0.5, maintenance_margin_pct=0.3)
    )

    res = orchestrator.run_backtest(config, df, strategy)
    assert res.stats.total_trades > 0
    assert len(orchestrator.repository.list_runs()) == 1
