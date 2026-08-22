"""Comprehensive unit and integration tests for Position Sizing and Capital Allocation.
"""

from __future__ import annotations

import os
import pytest
import pandas as pd
from datetime import datetime, timezone

from toji_platform.core.dependency_injection import Container
from toji_platform.core.event_bus import InMemoryEventBus
from toji_platform.core.event_bus.events import MarketDataReceived
from research_platform.paper_trading.events import PaperOrderMatched

from research_platform.portfolio_accounting.plugin import PortfolioAccountingPlugin
from research_platform.oms.plugin import OmsPlugin
from research_platform.paper_trading.plugin import PaperTradingPlugin
from research_platform.live_trading.plugin import LiveTradingEnginePlugin
from research_platform.live_trading.models import ActiveSignal
from research_platform.live_trading.orchestrator import LiveTradingOrchestrator
from research_platform.portfolio_governor.plugin import PortfolioGovernorPlugin
from research_platform.feature_platform.feature_store import FeatureStore

# Sizing imports
from research_platform.position_sizing.plugin import PositionSizingPlugin
from research_platform.position_sizing.orchestrator import PositionSizingOrchestrator


class MockFeaturePlatformOrchestrator:
    """Minimal mock with a FeatureStore and query_realtime support."""
    def __init__(self) -> None:
        self.store = FeatureStore()

    def query_realtime(self, names, symbols):
        """Delegate to the underlying FeatureStore.query_latest."""
        return self.store.query_latest(names, symbols)


@pytest.fixture
def event_bus() -> InMemoryEventBus:
    return InMemoryEventBus()


@pytest.fixture
def container(event_bus: InMemoryEventBus) -> Container:
    c = Container()
    c.register("IEventBus", instance=event_bus)

    # Feature Store mock
    feat_orch = MockFeaturePlatformOrchestrator()
    c.register("FeaturePlatformOrchestrator", instance=feat_orch)

    # Initialize accounting, OMS, paper trading plugins
    PortfolioAccountingPlugin(c).initialize()
    OmsPlugin(c).initialize()
    PaperTradingPlugin(c).initialize()
    PortfolioGovernorPlugin(c).initialize()
    PositionSizingPlugin(c).initialize()

    return c


def test_position_sizing_fixed_risk(container: Container, event_bus: InMemoryEventBus) -> None:
    sizer = container.resolve(PositionSizingOrchestrator)
    sizer._config.method = "fixed_risk"
    sizer._config.risk_percent = 0.02
    sizer._config.max_symbol_exposure_pct = 1.0 # disable symbol cap for test
    sizer._config.max_portfolio_exposure_pct = 1.0 # disable portfolio cap for test

    # Seed latest price for BTC/USDT via event
    event_bus.publish(MarketDataReceived(payload={"symbol": "BTC/USDT", "price": 10000.0}))

    # Calculate size for BTC/USDT signal (Equity = 100,000, cash = 100,000)
    # Risk amount = 100,000 * 0.02 = 2000. Stop distance = 10,000 * 0.02 = 200.
    # Qty = 2000 / 200 = 10.0
    res = sizer.calculate_size("BTC/USDT", "BUY")
    assert res.raw_qty == pytest.approx(10.0)
    assert res.final_qty == pytest.approx(10.0)
    assert res.allocated_capital == pytest.approx(100000.0)  # 10.0 * 10,000


def test_position_sizing_kelly(container: Container, event_bus: InMemoryEventBus) -> None:
    sizer = container.resolve(PositionSizingOrchestrator)
    sizer._config.method = "kelly"
    sizer._config.win_rate = 0.60
    sizer._config.payoff_ratio = 2.0
    sizer._config.kelly_leverage_frac = 0.5  # half Kelly
    sizer._config.max_symbol_exposure_pct = 1.0
    sizer._config.max_portfolio_exposure_pct = 1.0

    event_bus.publish(MarketDataReceived(payload={"symbol": "BTC/USDT", "price": 10000.0}))

    # Kelly = 0.60 - (0.40 / 2.0) = 0.40
    # Half Kelly = 0.20
    # Risk capital = 100,000 * 0.20 = 20,000. Stop distance = 200
    # Qty = 20,000 / 200 = 100.0
    res = sizer.calculate_size("BTC/USDT", "BUY")
    assert res.raw_qty == pytest.approx(100.0)


def test_position_sizing_volatility(container: Container, event_bus: InMemoryEventBus) -> None:
    # FP-3D: seed 'annualized_vol' (canonical key) in the feature store.
    # vol=0.05 is at the minimum floor (target_vol/max_leverage = 0.10/2.0 = 0.05),
    # so scale = min(0.10/0.05, 2.0) = 2.0x leverage.
    # Target Capital = 100,000 * 2.0 = 200,000
    # Qty = 200,000 / 10,000 = 20.0
    feat_orch = container.resolve("FeaturePlatformOrchestrator")
    now = datetime.now(timezone.utc)
    vol_df = pd.DataFrame([{
        "annualized_vol": 0.05,
        "effective_time": now,
        "as_of": now,
        "symbol": "BTC/USDT"
    }])
    feat_orch.store.save_features("annualized_vol", "1.0.0", "BTC/USDT", vol_df)

    sizer = container.resolve(PositionSizingOrchestrator)
    sizer._config.method = "volatility"
    sizer._config.target_volatility = 0.10
    sizer._config.max_leverage = 2.0
    sizer._config.max_symbol_exposure_pct = 1.0
    sizer._config.max_portfolio_exposure_pct = 1.0

    event_bus.publish(MarketDataReceived(payload={"symbol": "BTC/USDT", "price": 10000.0}))

    # vol=0.05 = floor (target/max_leverage = 0.10/2.0)
    # scale = min(0.10/0.05, 2.0) = 2.0x (leverage cap)
    # Target Capital = 100,000 * 2.0 = 200,000
    # Qty = 200,000 / 10,000 = 20.0
    res = sizer.calculate_size("BTC/USDT", "BUY")
    assert res.raw_qty == pytest.approx(20.0)


def test_position_sizing_equal_weight(container: Container, event_bus: InMemoryEventBus) -> None:
    sizer = container.resolve(PositionSizingOrchestrator)
    sizer._config.method = "equal_weight"
    sizer._config.max_open_positions = 5
    sizer._config.max_symbol_exposure_pct = 1.0
    sizer._config.max_portfolio_exposure_pct = 1.0

    event_bus.publish(MarketDataReceived(payload={"symbol": "BTC/USDT", "price": 10000.0}))

    # Weight = 1 / 5 = 0.20
    # Capital = 20,000
    # Qty = 20,000 / 10,000 = 2.0
    res = sizer.calculate_size("BTC/USDT", "BUY")
    assert res.raw_qty == pytest.approx(2.0)


def test_position_sizing_exposure_limits(container: Container, event_bus: InMemoryEventBus) -> None:
    sizer = container.resolve(PositionSizingOrchestrator)
    sizer._config.method = "equal_weight"
    sizer._config.max_open_positions = 2
    # Set symbol exposure cap to 10% (0.10)
    sizer._config.max_symbol_exposure_pct = 0.10
    sizer._config.max_portfolio_exposure_pct = 1.0

    event_bus.publish(MarketDataReceived(payload={"symbol": "BTC/USDT", "price": 10000.0}))

    # Equal weight allocation would normally allocate 50,000 capital (Qty = 5.0)
    # But symbol exposure is capped at 10% of equity (10,000 capital, Qty = 1.0)
    res = sizer.calculate_size("BTC/USDT", "BUY")
    assert res.raw_qty == pytest.approx(5.0)
    assert res.final_qty == pytest.approx(1.0)


def test_position_sizing_cash_limits(container: Container, event_bus: InMemoryEventBus) -> None:
    # Open position to deduct cash (consumes 90,000 cash, leaving 10,000 cash)
    event_bus.publish(PaperOrderMatched(payload={
        "symbol": "BTC/USDT",
        "side": "BUY",
        "quantity": 9.0,
        "price": 10000.0,
        "strategy": "MOCK",
        "ai_confidence": 0.8,
        "rationale": "test"
    }))

    sizer = container.resolve(PositionSizingOrchestrator)
    sizer._config.method = "equal_weight"
    sizer._config.max_open_positions = 1
    sizer._config.max_symbol_exposure_pct = 1.0
    sizer._config.max_portfolio_exposure_pct = 1.0  # disable portfolio cap

    event_bus.publish(MarketDataReceived(payload={"symbol": "BTC/USDT", "price": 10000.0}))

    # Equal weight allocation wants to allocate 100,000 (Qty = 10.0)
    # But only 9,946 cash is left (due to fee/slippage), so cash check caps Qty at ~0.9946
    res = sizer.calculate_size("BTC/USDT", "BUY")
    assert res.final_qty == pytest.approx(0.9946, rel=1e-3)


def test_position_sizing_e2e_pipeline(container: Container, event_bus: InMemoryEventBus, monkeypatch: pytest.MonkeyPatch) -> None:
    # Mock gateway constructor to avoid background socket tick loops
    class MockGateway:
        def start(self) -> None:
            pass
        def stop(self) -> None:
            pass

    from research_platform.live_trading.factory import MarketProviderFactory
    monkeypatch.setattr(
        MarketProviderFactory,
        "create_provider",
        lambda *args, **kwargs: MockGateway()
    )

    monkeypatch.setenv("POSITION_SIZING_METHOD", "fixed_risk")
    monkeypatch.setenv("RISK_PERCENT", "0.02")  # 2% Risk
    monkeypatch.setenv("TRADING_MODE", "paper")  # paper mode routing

    # Boot live trading engine plugin
    from research_platform.execution_engine.plugin import ExecutionEnginePlugin
    from research_platform.live_trading.plugin import LiveTradingEnginePlugin
    from research_platform.paper_market.plugin import PaperMarketPlugin
    from research_platform.institutional_memory.plugin import InstitutionalMemoryPlugin
    from research_platform.knowledge_graph.plugin import KnowledgeGraphPlugin

    # Initialize live plugins
    InstitutionalMemoryPlugin(container).initialize()
    KnowledgeGraphPlugin(container).initialize()
    ExecutionEnginePlugin(container).initialize()
    PaperMarketPlugin(container).initialize()
    LiveTradingEnginePlugin(container).initialize()

    # Get PositionSizingOrchestrator and set multipliers/caps
    sizer = container.resolve(PositionSizingOrchestrator)
    sizer._config.method = "fixed_risk"
    sizer._config.risk_percent = 0.02
    sizer._config.max_symbol_exposure_pct = 1.0 # disable symbol cap for test
    sizer._config.max_portfolio_exposure_pct = 1.0 # disable portfolio cap for test

    # Seed market price tick
    event_bus.publish(MarketDataReceived(payload={"symbol": "BTC/USDT", "price": 10000.0}))

    # Get LiveTradingOrchestrator
    live_orch = container.resolve(LiveTradingOrchestrator)

    # Ingest BUY signal
    sig = ActiveSignal(signal_id="sig_e2e_sizing", symbol="BTC/USDT", direction="BUY", strength=0.9)
    success = live_orch.ingest_market_signal(sig)
    assert success is True

    # Assert that the fill quantity in accounting is exactly the calculated sized quantity (10.0)
    accounting = container.resolve("PortfolioAccounting")
    pos = accounting.valuation_engine.get_position("BTC/USDT")
    assert pos is not None
    assert pos.quantity == pytest.approx(10.0)

    # Assert Runtime API summary contains sizing information
    summary = container.resolve(PositionSizingOrchestrator).get_summary()
    assert summary["sizing_method"] == "FIXED_RISK"
    assert summary["cash_remaining"] == pytest.approx(-60.1001, rel=1e-3)
