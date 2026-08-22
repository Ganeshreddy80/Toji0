"""Comprehensive unit and integration tests for Exit Engine.
"""

from __future__ import annotations

import os
import pytest
import time
from datetime import datetime, timezone

from toji_platform.core.dependency_injection import Container
from toji_platform.core.event_bus import InMemoryEventBus
from toji_platform.core.event_bus.events import MarketDataReceived
from research_platform.paper_trading.events import PaperOrderMatched
from research_platform.portfolio_accounting.events import PositionValuationUpdated, TradeClosed
from research_platform.portfolio_accounting.accounting_service import AccountingService
from research_platform.portfolio_accounting.plugin import PortfolioAccountingPlugin
from research_platform.exit_engine.orchestrator import ExitEngineOrchestrator
from research_platform.exit_engine.plugin import ExitEnginePlugin
from research_platform.exit_engine.events import (
    PositionExitRequested, PositionClosed, StopLossTriggered,
    TakeProfitTriggered, TrailingStopUpdated
)
from research_platform.live_trading.trade_manager import TradeManager
from research_platform.oms.orchestrator import OrderManagementSystemOrchestrator
from research_platform.oms.oms_core import OmsCore
from research_platform.execution_engine.orchestrator import ExecutionEngineOrchestrator
from research_platform.feature_platform.feature_store import FeatureStore


class MockFeaturePlatformOrchestrator:
    """Minimal FP mock that returns empty DataFrames for any query_realtime call."""
    def __init__(self):
        self.store = FeatureStore()

    def query_realtime(self, feature_names, symbols):
        import pandas as pd
        return pd.DataFrame()


class MockPriceActionOrchestrator:
    """Minimal PA mock for FP-4 boundary tests."""

    def __init__(self, atr_value: float = 0.0):
        self._atr_value = atr_value
        self.get_atr_calls: list = []

    def get_atr(self, symbol: str) -> float:
        self.get_atr_calls.append(symbol)
        return self._atr_value


@pytest.fixture
def event_bus():
    return InMemoryEventBus()


@pytest.fixture
def container(event_bus):
    c = Container()
    c.register("IEventBus", instance=event_bus)
    
    # Mock Feature Store
    feat_orch = MockFeaturePlatformOrchestrator()
    c.register("FeaturePlatformOrchestrator", instance=feat_orch)
    
    # Portfolio Accounting via Plugin
    accounting_plugin = PortfolioAccountingPlugin(c)
    accounting_plugin.initialize()
    
    # OMS and EMS
    oms = OrderManagementSystemOrchestrator(event_bus)
    ems = ExecutionEngineOrchestrator(event_bus)
    c.register("OrderManagementSystemOrchestrator", instance=oms)
    c.register("ExecutionEngineOrchestrator", instance=ems)
    
    # Trade Manager
    trade_mgr = TradeManager(oms, ems)
    c.register("TradeManager", instance=trade_mgr)
    
    return c


def test_exit_engine_stop_loss_pct(container, event_bus, monkeypatch):
    monkeypatch.setenv("EXIT_STOP_LOSS_PCT", "0.02") # 2% Stop Loss
    monkeypatch.setenv("TRADING_MODE", "live") # route via EMS to keep it simple

    plugin = ExitEnginePlugin(container)
    plugin.initialize()
    exit_orch = container.resolve("ExitEngine")

    # Open a long position in Accounting
    accounting = container.resolve("PortfolioAccounting")
    
    event_bus.publish(PaperOrderMatched(payload={
        "symbol": "BTC/USDT",
        "side": "BUY",
        "quantity": 1.0,
        "price": 10000.0,
        "strategy": "MOCK",
        "ai_confidence": 0.8,
        "rationale": "test"
    }))

    # Assert position opened
    pos = accounting.valuation_engine.get_position("BTC/USDT")
    assert pos is not None
    assert pos.average_entry == 10000.0

    # Track events triggered
    events_triggered = []
    def track_exit_requested(ev):
        events_triggered.append(ev)
    event_bus.subscribe("system.position_exit_requested", track_exit_requested)

    # Publish valuation update within SL bounds (9900.0 -> -1%)
    # Note: ExitEngine listens to PositionValuationUpdated published by Accounting
    event_bus.publish(PositionValuationUpdated(payload={
        "symbol": "BTC/USDT",
        "price": 9900.0
    }))
    assert len(events_triggered) == 0

    # Publish valuation update breaching SL (9750.0 -> -2.5%)
    event_bus.publish(PositionValuationUpdated(payload={
        "symbol": "BTC/USDT",
        "price": 9750.0
    }))
    
    assert len(events_triggered) == 1
    assert events_triggered[0].payload["reason"] == "STOP_LOSS"


def test_exit_engine_take_profit_pct(container, event_bus, monkeypatch):
    monkeypatch.setenv("EXIT_TAKE_PROFIT_PCT", "0.05") # 5% TP
    monkeypatch.setenv("TRADING_MODE", "live")

    plugin = ExitEnginePlugin(container)
    plugin.initialize()
    
    event_bus.publish(PaperOrderMatched(payload={
        "symbol": "BTC/USDT",
        "side": "BUY",
        "quantity": 1.0,
        "price": 10000.0,
        "strategy": "MOCK",
        "ai_confidence": 0.8,
        "rationale": "test"
    }))

    events_triggered = []
    event_bus.subscribe("system.position_exit_requested", lambda ev: events_triggered.append(ev))

    # Price moves to 10400.0 (+4%) -> no TP
    event_bus.publish(PositionValuationUpdated(payload={
        "symbol": "BTC/USDT",
        "price": 10400.0
    }))
    assert len(events_triggered) == 0

    # Price moves to 10600.0 (+6%) -> TP triggers
    event_bus.publish(PositionValuationUpdated(payload={
        "symbol": "BTC/USDT",
        "price": 10600.0
    }))
    assert len(events_triggered) == 1
    assert events_triggered[0].payload["reason"] == "TAKE_PROFIT"


def test_exit_engine_trailing_stop(container, event_bus, monkeypatch):
    monkeypatch.setenv("EXIT_TRAILING_PCT", "0.02") # 2% Trailing Stop
    monkeypatch.setenv("TRADING_MODE", "live")

    plugin = ExitEnginePlugin(container)
    plugin.initialize()
    exit_orch = container.resolve("ExitEngine")

    event_bus.publish(PaperOrderMatched(payload={
        "symbol": "BTC/USDT",
        "side": "BUY",
        "quantity": 1.0,
        "price": 10000.0,
        "strategy": "MOCK",
        "ai_confidence": 0.8,
        "rationale": "test"
    }))

    # Set highest price manually in ValuationEngine to simulate watermark tracking
    accounting = container.resolve("PortfolioAccounting")
    pos = accounting.valuation_engine.get_position("BTC/USDT")
    pos.highest_price_seen = 11000.0

    events_triggered = []
    event_bus.subscribe("system.position_exit_requested", lambda ev: events_triggered.append(ev))

    # Price drops to 10850.0 (above trailing stop level 10780.0) -> no exit
    event_bus.publish(PositionValuationUpdated(payload={
        "symbol": "BTC/USDT",
        "price": 10850.0
    }))
    assert len(events_triggered) == 0

    # Price drops to 10700.0 (below trailing stop level 10780.0) -> triggers exit
    event_bus.publish(PositionValuationUpdated(payload={
        "symbol": "BTC/USDT",
        "price": 10700.0
    }))
    assert len(events_triggered) == 1
    assert events_triggered[0].payload["reason"] == "TRAILING_STOP"


def test_exit_engine_break_even(container, event_bus, monkeypatch):
    monkeypatch.setenv("EXIT_BREAK_EVEN_TRIGGER", "0.03") # 3% profit trigger
    monkeypatch.setenv("TRADING_MODE", "live")

    plugin = ExitEnginePlugin(container)
    plugin.initialize()

    event_bus.publish(PaperOrderMatched(payload={
        "symbol": "BTC/USDT",
        "side": "BUY",
        "quantity": 1.0,
        "price": 10000.0,
        "strategy": "MOCK",
        "ai_confidence": 0.8,
        "rationale": "test"
    }))

    accounting = container.resolve("PortfolioAccounting")
    pos = accounting.valuation_engine.get_position("BTC/USDT")

    events_triggered = []
    event_bus.subscribe("system.position_exit_requested", lambda ev: events_triggered.append(ev))

    # Move price to 10200.0 (2% profit, break even not active yet)
    pos.pnl_percent = 2.0
    event_bus.publish(PositionValuationUpdated(payload={
        "symbol": "BTC/USDT",
        "price": 10200.0
    }))
    # Retrace to entry 10000.0 -> no exit
    event_bus.publish(PositionValuationUpdated(payload={
        "symbol": "BTC/USDT",
        "price": 10000.0
    }))
    assert len(events_triggered) == 0

    # Move price to 10400.0 (4% profit -> break even activated)
    pos.pnl_percent = 4.0
    event_bus.publish(PositionValuationUpdated(payload={
        "symbol": "BTC/USDT",
        "price": 10400.0
    }))
    
    # Retrace to 10000.0 -> triggers exit
    event_bus.publish(PositionValuationUpdated(payload={
        "symbol": "BTC/USDT",
        "price": 10000.0
    }))
    assert len(events_triggered) == 1
    assert events_triggered[0].payload["reason"] == "BREAK_EVEN"


def test_exit_engine_time_stop(container, event_bus, monkeypatch):
    monkeypatch.setenv("EXIT_TIME_SECONDS", "0.1") # 0.1s Time Stop
    monkeypatch.setenv("TRADING_MODE", "live")

    plugin = ExitEnginePlugin(container)
    plugin.initialize()

    event_bus.publish(PaperOrderMatched(payload={
        "symbol": "BTC/USDT",
        "side": "BUY",
        "quantity": 1.0,
        "price": 10000.0,
        "strategy": "MOCK",
        "ai_confidence": 0.8,
        "rationale": "test"
    }))

    events_triggered = []
    event_bus.subscribe("system.position_exit_requested", lambda ev: events_triggered.append(ev))

    # Immediate check -> no time stop
    event_bus.publish(PositionValuationUpdated(payload={
        "symbol": "BTC/USDT",
        "price": 10000.0
    }))
    assert len(events_triggered) == 0

    # Wait 0.2s and tick again
    time.sleep(0.2)
    event_bus.publish(PositionValuationUpdated(payload={
        "symbol": "BTC/USDT",
        "price": 10000.0
    }))
    assert len(events_triggered) == 1
    assert events_triggered[0].payload["reason"] == "TIME_STOP"


def test_exit_engine_atr_stop(container, event_bus, monkeypatch):
    """FP-4 / ADR-001: ATR stop uses PA-ATR (pa_orch.get_atr), not Feature Platform ATR.

    PA mock returns 100.0. Multiplier=2.0.
    Expected stop level = 10000.0 - (2.0 * 100.0) = 9800.0.
    Price 9850.0 -> above stop -> no exit.
    Price 9790.0 -> below stop -> ATR_STOP exit.
    """
    monkeypatch.setenv("EXIT_ATR_MULTIPLIER", "2.0")
    monkeypatch.setenv("TRADING_MODE", "live")

    # Register mock PA with known ATR=100.0
    mock_pa = MockPriceActionOrchestrator(atr_value=100.0)
    container.register("PriceActionOrchestrator", instance=mock_pa)

    plugin = ExitEnginePlugin(container)
    plugin.initialize()

    event_bus.publish(PaperOrderMatched(payload={
        "symbol": "BTC/USDT",
        "side": "BUY",
        "quantity": 1.0,
        "price": 10000.0,
        "strategy": "MOCK",
        "ai_confidence": 0.8,
        "rationale": "test"
    }))

    events_triggered = []
    event_bus.subscribe("system.position_exit_requested", lambda ev: events_triggered.append(ev))

    # ATR Stop = 10000.0 - (2.0 * 100.0) = 9800.0
    event_bus.publish(PositionValuationUpdated(payload={
        "symbol": "BTC/USDT",
        "price": 9850.0  # above stop -> no exit
    }))
    assert len(events_triggered) == 0

    event_bus.publish(PositionValuationUpdated(payload={
        "symbol": "BTC/USDT",
        "price": 9790.0  # below stop -> ATR_STOP
    }))
    assert len(events_triggered) == 1
    assert events_triggered[0].payload["reason"] == "ATR_STOP"

    # Boundary proof: PA.get_atr() was called (ExitEngine used PA, not FP store)
    assert len(mock_pa.get_atr_calls) >= 1, "PA.get_atr() must have been called by ExitEngine"
    assert all(sym == "BTC/USDT" for sym in mock_pa.get_atr_calls)


def test_exit_engine_summary(container, event_bus, monkeypatch):
    plugin = ExitEnginePlugin(container)
    plugin.initialize()
    exit_orch = container.resolve("ExitEngine")

    summary = exit_orch.get_summary()
    assert "open_positions" in summary
    assert "winning_positions" in summary
    assert "exit_counts" in summary


def test_exit_engine_e2e_pipeline(event_bus, monkeypatch):
    monkeypatch.setenv("EXIT_STOP_LOSS_PCT", "0.02")
    monkeypatch.setenv("TRADING_MODE", "paper") # paper trading!

    c = Container()
    c.register("IEventBus", instance=event_bus)

    # Mock Feature Store
    feat_orch = MockFeaturePlatformOrchestrator()
    c.register("FeaturePlatformOrchestrator", instance=feat_orch)

    # Initialize PaperTrading, Oms, PortfolioAccounting, and ExitEngine
    from research_platform.paper_trading.plugin import PaperTradingPlugin
    from research_platform.oms.plugin import OmsPlugin
    from research_platform.portfolio_analytics.plugin import PortfolioAnalyticsPlugin
    from research_platform.trade_journal.plugin import TradeJournalPlugin
    from research_platform.paper_market.plugin import PaperMarketPlugin
    from research_platform.institutional_memory.plugin import InstitutionalMemoryPlugin
    from research_platform.knowledge_graph.plugin import KnowledgeGraphPlugin
    from research_platform.execution_engine.plugin import ExecutionEnginePlugin
    from research_platform.live_trading.plugin import LiveTradingEnginePlugin

    # Register other plugins
    InstitutionalMemoryPlugin(c).initialize()
    KnowledgeGraphPlugin(c).initialize()
    OmsPlugin(c).initialize()
    ExecutionEnginePlugin(c).initialize()
    PaperMarketPlugin(c).initialize()
    PaperTradingPlugin(c).initialize()
    LiveTradingEnginePlugin(c).initialize()
    PortfolioAccountingPlugin(c).initialize()
    TradeJournalPlugin(c).initialize()
    PortfolioAnalyticsPlugin(c).initialize()
    ExitEnginePlugin(c).initialize()

    # Now let's open a position via the OMS!
    # OMS -> Paper Trading -> Portfolio Accounting -> Exit Engine
    from research_platform.oms.oms_core import OmsCore
    oms = c.resolve(OmsCore)
    
    # Place an order
    oms.submit_order(
        strategy_id="strat_1",
        symbol="BTC/USDT",
        quantity=1.0,
        price=10000.0,
        order_type="MARKET",
        side="BUY",
        rationale="test"
    )
    
    # Assert position is open in accounting
    accounting = c.resolve("PortfolioAccounting")
    pos = accounting.valuation_engine.get_position("BTC/USDT")
    assert pos is not None
    assert pos.quantity == 1.0

    # Let's track events
    events = []
    event_bus.subscribe("system.position_exit_requested", lambda ev: events.append(ev))
    event_bus.subscribe("system.trade_closed", lambda ev: events.append(ev))

    # Publish bad market tick -> breaches SL -> Exit Engine triggers exit order -> OMS -> fills -> Accounting
    event_bus.publish(PositionValuationUpdated(payload={
        "symbol": "BTC/USDT",
        "price": 9700.0 # -3% breach
    }))

    # Verify exit requested event fired
    assert any(ev.event_type == "system.position_exit_requested" for ev in events)
    # Verify trade closed in accounting
    assert any(ev.event_type == "system.trade_closed" for ev in events)
    # Verify position is closed in accounting
    pos_after = accounting.valuation_engine.get_position("BTC/USDT")
    assert pos_after is None or pos_after.quantity == 0.0

    # Check Exit Engine summary runtime API integration
    exit_orch = c.resolve("ExitEngine")
    summary = exit_orch.get_summary()
    assert summary["exit_counts"]["STOP_LOSS"] == 1
    assert len(summary["triggered_stops"]) == 1


def test_exit_engine_recovery_from_rejected_order(event_bus, monkeypatch):
    """Verify that Exit Engine recovers and resets exit_requested flag when exit order is rejected/cancelled."""
    monkeypatch.setenv("TRADING_MODE", "paper")
    from toji_platform.core.dependency_injection import Container
    from research_platform.portfolio_accounting.plugin import PortfolioAccountingPlugin
    from research_platform.exit_engine.plugin import ExitEnginePlugin
    from research_platform.oms.plugin import OmsPlugin
    from research_platform.paper_trading.plugin import PaperTradingPlugin
    from research_platform.paper_market.plugin import PaperMarketPlugin
    from research_platform.trade_journal.plugin import TradeJournalPlugin
    from research_platform.portfolio_analytics.plugin import PortfolioAnalyticsPlugin
    from research_platform.live_trading.trade_manager import TradeManager
    from research_platform.execution_engine.orchestrator import ExecutionEngineOrchestrator
    from research_platform.oms.events import OMSOrderStateChanged
    from toji_platform.core.event_bus.events import BaseEvent

    c = Container()
    c.register("IEventBus", instance=event_bus)
    
    # Register Mock Feature Store
    feat_orch = MockFeaturePlatformOrchestrator()
    c.register("FeaturePlatformOrchestrator", instance=feat_orch)
    
    # Initialize plugins
    PortfolioAccountingPlugin(c).initialize()
    OmsPlugin(c).initialize()
    PaperTradingPlugin(c).initialize()
    PaperMarketPlugin(c).initialize()
    TradeJournalPlugin(c).initialize()
    PortfolioAnalyticsPlugin(c).initialize()
    ExitEnginePlugin(c).initialize()

    # Create TradeManager
    oms = c.resolve(OmsCore)
    ems = ExecutionEngineOrchestrator(event_bus)
    c.register("ExecutionEngineOrchestrator", instance=ems)
    
    # We resolve the paper execution router from container to inject in TradeManager
    paper_router = c.resolve("PaperExecutionRouter")
    trade_mgr = TradeManager(oms, ems, paper_router=paper_router)
    c.register("TradeManager", instance=trade_mgr)

    # Start active paper session
    paper_orch = c.resolve("research_platform.paper_trading.orchestrator.PaperTradingOrchestrator")
    paper_orch.start_paper_session("acc-prod", 100000.0)

    # Place an order to open position
    oms.submit_order(
        strategy_id="strat_1",
        symbol="BTC/USDT",
        quantity=1.0,
        price=10000.0,
        order_type="MARKET",
        side="BUY",
        rationale="test"
    )

    # Publish valuation update to initialize exit state tracking
    event_bus.publish(PositionValuationUpdated(payload={
        "symbol": "BTC/USDT",
        "price": 10000.0
    }))

    exit_orch = c.resolve("ExitEngine")
    state = exit_orch._exit_states.get("BTC/USDT")
    assert state is not None
    assert not state.exit_requested

    # We mock TradeManager.execute_signal_trade to simulate pending order submission
    captured_order_id = []

    def mock_execute(order_id, symbol, direction, quantity, price):
        captured_order_id.append(order_id)
        return True

    trade_mgr.execute_signal_trade = mock_execute

    # Set Stop Loss to trigger exit
    exit_orch.config.stop_loss_pct = 0.02 # 2%
    
    # Valuation update -> triggers SL exit
    event_bus.publish(PositionValuationUpdated(payload={
        "symbol": "BTC/USDT",
        "price": 9700.0
    }))

    # Verify exit was requested and order is pending
    assert state.exit_requested
    assert len(captured_order_id) == 1
    exit_order_id = captured_order_id[0]
    assert exit_order_id in exit_orch._pending_exits

    # Now simulate a state change event showing order cancelled/rejected
    # The event class is OMSOrderStateChanged
    event_bus.publish(OMSOrderStateChanged(payload={
        "order_id": exit_order_id,
        "status": "CANCELLED"
    }))

    # Verify exit engine has reset the exit flags to recover
    assert not state.exit_requested
    assert state.exit_reason is None
    assert exit_order_id not in exit_orch._pending_exits


# ─────────────────────────────────────────────────────────────────────────────
# FP-4 BOUNDARY TESTS — ADR-001 Ownership Compliance
# Sprint 004 FP-4: ATR Canonical Source Migration
# ─────────────────────────────────────────────────────────────────────────────


def _make_fp4_container(event_bus, pa_atr_value: float = 100.0):
    """Build a container with both MockPA and MockFP registered for FP-4 tests."""
    c = Container()
    c.register("IEventBus", instance=event_bus)

    mock_fp = MockFeaturePlatformOrchestrator()
    c.register("FeaturePlatformOrchestrator", instance=mock_fp)

    mock_pa = MockPriceActionOrchestrator(atr_value=pa_atr_value)
    c.register("PriceActionOrchestrator", instance=mock_pa)

    PortfolioAccountingPlugin(c).initialize()
    oms = OrderManagementSystemOrchestrator(event_bus)
    ems = ExecutionEngineOrchestrator(event_bus)
    c.register("OrderManagementSystemOrchestrator", instance=oms)
    c.register("ExecutionEngineOrchestrator", instance=ems)
    c.register("TradeManager", instance=TradeManager(oms, ems))

    return c, mock_fp, mock_pa


def test_fp4_exit_engine_obtains_atr_from_pa(event_bus, monkeypatch):
    """AC-1: ExitEngine obtains atr_val from pa_orch.get_atr(symbol)."""
    monkeypatch.setenv("EXIT_ATR_MULTIPLIER", "2.0")
    monkeypatch.setenv("TRADING_MODE", "live")

    c, mock_fp, mock_pa = _make_fp4_container(event_bus, pa_atr_value=100.0)
    ExitEnginePlugin(c).initialize()

    event_bus.publish(PaperOrderMatched(payload={
        "symbol": "BTC/USDT", "side": "BUY", "quantity": 1.0, "price": 10000.0,
        "strategy": "MOCK", "ai_confidence": 0.8, "rationale": "test"
    }))

    events_triggered = []
    event_bus.subscribe("system.position_exit_requested", lambda ev: events_triggered.append(ev))

    # Stop = 10000.0 - (2.0 * 100.0) = 9800.0; price 9790.0 breaches it
    event_bus.publish(PositionValuationUpdated(payload={"symbol": "BTC/USDT", "price": 9790.0}))

    assert len(events_triggered) == 1
    assert events_triggered[0].payload["reason"] == "ATR_STOP"
    assert len(mock_pa.get_atr_calls) >= 1, "AC-1 FAIL: ExitEngine did not call pa_orch.get_atr()"


def test_fp4_exit_engine_does_not_query_fp_for_atr(event_bus, monkeypatch):
    """AC-2: ExitEngine does NOT request 'atr' from Feature Platform query_realtime."""
    monkeypatch.setenv("EXIT_ATR_MULTIPLIER", "2.0")
    monkeypatch.setenv("TRADING_MODE", "live")

    queried_feature_lists = []

    class SpyFP(MockFeaturePlatformOrchestrator):
        def query_realtime(self, feature_names, symbols):
            queried_feature_lists.append(list(feature_names))
            import pandas as pd
            return pd.DataFrame()

    c = Container()
    c.register("IEventBus", instance=event_bus)
    c.register("FeaturePlatformOrchestrator", instance=SpyFP())
    c.register("PriceActionOrchestrator", instance=MockPriceActionOrchestrator(atr_value=100.0))
    PortfolioAccountingPlugin(c).initialize()
    oms = OrderManagementSystemOrchestrator(event_bus)
    ems = ExecutionEngineOrchestrator(event_bus)
    c.register("OrderManagementSystemOrchestrator", instance=oms)
    c.register("ExecutionEngineOrchestrator", instance=ems)
    c.register("TradeManager", instance=TradeManager(oms, ems))

    ExitEnginePlugin(c).initialize()
    event_bus.publish(PaperOrderMatched(payload={
        "symbol": "BTC/USDT", "side": "BUY", "quantity": 1.0, "price": 10000.0,
        "strategy": "MOCK", "ai_confidence": 0.8, "rationale": "test"
    }))
    event_bus.publish(PositionValuationUpdated(payload={"symbol": "BTC/USDT", "price": 9999.0}))

    all_queried = [f for lst in queried_feature_lists for f in lst]
    assert "atr" not in all_queried, (
        f"AC-2 FAIL: ExitEngine queried FP for 'atr' — violates ADR-001. Queried: {queried_feature_lists}"
    )


def test_fp4_exit_engine_still_queries_fp_for_norm_atr_and_risk_score(event_bus, monkeypatch):
    """AC-3: ExitEngine still requests normalized_atr and risk_score from Feature Platform."""
    monkeypatch.setenv("TRADING_MODE", "live")

    queried_feature_lists = []

    class SpyFP(MockFeaturePlatformOrchestrator):
        def query_realtime(self, feature_names, symbols):
            queried_feature_lists.append(list(feature_names))
            import pandas as pd
            return pd.DataFrame()

    c = Container()
    c.register("IEventBus", instance=event_bus)
    c.register("FeaturePlatformOrchestrator", instance=SpyFP())
    c.register("PriceActionOrchestrator", instance=MockPriceActionOrchestrator(atr_value=50.0))
    PortfolioAccountingPlugin(c).initialize()
    oms = OrderManagementSystemOrchestrator(event_bus)
    ems = ExecutionEngineOrchestrator(event_bus)
    c.register("OrderManagementSystemOrchestrator", instance=oms)
    c.register("ExecutionEngineOrchestrator", instance=ems)
    c.register("TradeManager", instance=TradeManager(oms, ems))

    ExitEnginePlugin(c).initialize()
    event_bus.publish(PaperOrderMatched(payload={
        "symbol": "BTC/USDT", "side": "BUY", "quantity": 1.0, "price": 10000.0,
        "strategy": "MOCK", "ai_confidence": 0.8, "rationale": "test"
    }))
    event_bus.publish(PositionValuationUpdated(payload={"symbol": "BTC/USDT", "price": 9999.0}))

    all_queried = [f for lst in queried_feature_lists for f in lst]
    assert "normalized_atr" in all_queried, "AC-3 FAIL: ExitEngine must query FP for normalized_atr"
    assert "risk_score" in all_queried, "AC-3 FAIL: ExitEngine must query FP for risk_score"


def test_fp4_pa_unavailable_skips_atr_stop_gracefully(event_bus, monkeypatch):
    """Safety: If PriceActionOrchestrator not in container, ATR stop is skipped (no exception)."""
    monkeypatch.setenv("EXIT_ATR_MULTIPLIER", "2.0")
    monkeypatch.setenv("TRADING_MODE", "live")

    # Container WITHOUT PA registered
    c = Container()
    c.register("IEventBus", instance=event_bus)
    c.register("FeaturePlatformOrchestrator", instance=MockFeaturePlatformOrchestrator())
    # PriceActionOrchestrator deliberately NOT registered
    PortfolioAccountingPlugin(c).initialize()
    oms = OrderManagementSystemOrchestrator(event_bus)
    ems = ExecutionEngineOrchestrator(event_bus)
    c.register("OrderManagementSystemOrchestrator", instance=oms)
    c.register("ExecutionEngineOrchestrator", instance=ems)
    c.register("TradeManager", instance=TradeManager(oms, ems))

    ExitEnginePlugin(c).initialize()
    exit_orch = c.resolve("ExitEngine")

    event_bus.publish(PaperOrderMatched(payload={
        "symbol": "BTC/USDT", "side": "BUY", "quantity": 1.0, "price": 10000.0,
        "strategy": "MOCK", "ai_confidence": 0.8, "rationale": "test"
    }))
    event_bus.publish(PositionValuationUpdated(payload={"symbol": "BTC/USDT", "price": 9999.0}))

    state = exit_orch._exit_states.get("BTC/USDT")
    assert state is not None
    assert state.initial_atr_stop is None, "ATR stop must not be set when PA is unavailable"


def test_fp4_pa_returns_zero_skips_atr_stop(event_bus, monkeypatch):
    """Safety: If PA.get_atr() returns 0.0 (warm-up), atr_val=None and ATR stop is not set."""
    monkeypatch.setenv("EXIT_ATR_MULTIPLIER", "2.0")
    monkeypatch.setenv("TRADING_MODE", "live")

    c, _, _ = _make_fp4_container(event_bus, pa_atr_value=0.0)
    ExitEnginePlugin(c).initialize()
    exit_orch = c.resolve("ExitEngine")

    event_bus.publish(PaperOrderMatched(payload={
        "symbol": "BTC/USDT", "side": "BUY", "quantity": 1.0, "price": 10000.0,
        "strategy": "MOCK", "ai_confidence": 0.8, "rationale": "test"
    }))
    event_bus.publish(PositionValuationUpdated(payload={"symbol": "BTC/USDT", "price": 9999.0}))

    state = exit_orch._exit_states.get("BTC/USDT")
    assert state is not None
    assert state.initial_atr_stop is None, "ATR stop must not be set when PA returns 0.0 (warm-up)"


def test_fp4_feature_platform_atr_pipeline_intact():
    """AC-7/AC-8/AC-9/AC-10: AtrTransformer, FeatureRecord(atr), normalized_atr,
    risk_score, and annualized_vol remain registered. Internal DAG is intact."""
    from research_platform.feature_platform.dependency_graph import DependencyGraph
    from research_platform.feature_platform.feature_pipeline import FeaturePipeline
    from research_platform.feature_platform.orchestrator import DEFAULT_FEATURE_DEFINITIONS, FeaturePlatformOrchestrator
    from research_platform.feature_platform.transformers import AtrTransformer
    from toji_platform.core.event_bus import InMemoryEventBus

    dep_graph = DependencyGraph()
    pipeline = FeaturePipeline(dep_graph)

    # AtrTransformer must still be in pipeline transformers
    assert "atr" in pipeline._transformers, "AC-7 FAIL: AtrTransformer must be present in FeaturePipeline"
    assert isinstance(pipeline._transformers["atr"], AtrTransformer), "AC-7 FAIL: pipeline['atr'] must be AtrTransformer"

    # 'atr' must be registered in default feature definitions and orchestrator registry
    default_names = [r.name for r in DEFAULT_FEATURE_DEFINITIONS]
    assert "atr" in default_names, "AC-8 FAIL: FeatureRecord(name='atr') must remain in DEFAULT_FEATURE_DEFINITIONS"
    assert "normalized_atr" in default_names, "AC-9 FAIL: normalized_atr must remain registered"
    assert "risk_score" in default_names, "AC-9 FAIL: risk_score must remain registered"
    assert "annualized_vol" in default_names, "AC-10 FAIL: FP-3D annualized_vol must remain registered"

    # Test orchestrator registration
    eb = InMemoryEventBus()
    fp_orch = FeaturePlatformOrchestrator(eb)
    fp_orch.register_default_features()
    all_registered = [r.name for r in fp_orch.registry.list_all()]
    assert "atr" in all_registered, "AC-8 FAIL: 'atr' must be in registered features of orchestrator"
    assert "normalized_atr" in all_registered
    assert "risk_score" in all_registered
    assert "annualized_vol" in all_registered


def test_fp4_static_boundary_no_fp_atr_query_in_production():
    """AC-12: Static grep audit — no query_realtime('atr') in exit_engine or trade_journal production source."""
    import subprocess
    # Search for the old pattern: query_realtime with "atr" in exit_engine and trade_journal
    result = subprocess.run(
        ["grep", "-rn", "--include=*.py",
         "query_realtime",
         "research_platform/exit_engine",
         "research_platform/trade_journal"],
        capture_output=True, text=True,
        cwd="/Users/a.ganeshkumarreddy12/Downloads/toji-main 3"
    )
    matching_lines = [
        line for line in result.stdout.splitlines()
        if '"atr"' in line and "normalized_atr" not in line and "risk_score" not in line
        and "test_" not in line
    ]
    assert len(matching_lines) == 0, (
        f"AC-12 FAIL: Found query_realtime with 'atr' in production files — ADR-001 violation:\n"
        + "\n".join(matching_lines)
    )
