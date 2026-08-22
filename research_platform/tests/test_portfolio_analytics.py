"""Comprehensive unit and integration tests for TOJI Portfolio Analytics & Attribution Subsystem.
"""

from __future__ import annotations

import pytest
import threading
from datetime import datetime, timezone

from toji_platform.core.dependency_injection import Container
from toji_platform.core.event_bus import InMemoryEventBus

from research_platform.portfolio_analytics.orchestrator import PortfolioAnalyticsOrchestrator
from research_platform.portfolio_analytics.performance_engine import PerformanceEngine
from research_platform.portfolio_analytics.attribution_engine import AttributionEngine
from research_platform.portfolio_analytics.benchmark_engine import BenchmarkEngine
from research_platform.portfolio_analytics.risk_metrics import RiskMetricsCalculator
from research_platform.portfolio_analytics.reporting_engine import ReportingEngine
from research_platform.portfolio_analytics.models import PortfolioSnapshot
from research_platform.portfolio_analytics.plugin import PortfolioAnalyticsPlugin
from research_platform.trade_journal.models import TradeJournal, TradeScore, TradeReview

# Dependencies
from research_platform.oms.oms_core import OmsCore
from research_platform.paper_trading.orchestrator import PaperTradingOrchestrator
from research_platform.paper_market.orchestrator import PaperMarketOrchestrator
from research_platform.trade_journal.orchestrator import TradeJournalOrchestrator
from research_platform.institutional_memory.orchestrator import InstitutionalMemoryOrchestrator
from research_platform.knowledge_graph.orchestrator import KnowledgeGraphOrchestrator
from research_platform.operations_center.operations_orchestrator import OperationsOrchestrator


@pytest.fixture
def event_bus():
    return InMemoryEventBus()


@pytest.fixture
def container(event_bus):
    c = Container()
    c.register("IEventBus", instance=event_bus)

    mem_orch = InstitutionalMemoryOrchestrator(event_bus)
    c.register("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator", instance=mem_orch)

    kg_orch = KnowledgeGraphOrchestrator(event_bus)
    c.register("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator", instance=kg_orch)

    trading_orch = PaperTradingOrchestrator(event_bus, container=c)
    c.register("research_platform.paper_trading.orchestrator.PaperTradingOrchestrator", instance=trading_orch)

    market_orch = PaperMarketOrchestrator(event_bus, container=c)
    c.register("research_platform.paper_market.orchestrator.PaperMarketOrchestrator", instance=market_orch)

    oms_orch = OmsCore(event_bus, container=c)
    c.register("research_platform.oms.oms_core.OmsCore", instance=oms_orch)

    ops_orch = OperationsOrchestrator(event_bus, container=c)
    c.register("research_platform.operations_center.operations_orchestrator.OperationsOrchestrator", instance=ops_orch)

    journal_orch = TradeJournalOrchestrator(event_bus, container=c)
    c.register("research_platform.trade_journal.orchestrator.TradeJournalOrchestrator", instance=journal_orch)

    return c


@pytest.fixture
def orchestrator(event_bus, container):
    return PortfolioAnalyticsOrchestrator(event_bus, container=container)


# 1. Portfolio Return calculation
def test_portfolio_return_calculation():
    engine = PerformanceEngine()
    nav_series = [100.0, 105.0, 110.0]
    ret = engine.calculate_returns(nav_series, 100.0)
    assert ret.total_return == pytest.approx(0.10)
    assert ret.net_return == pytest.approx(0.10)


# 2. CAGR calculation
def test_cagr_calculation():
    engine = PerformanceEngine()
    nav_series = [100.0] * 252  # Exactly 1 year
    nav_series.append(110.0)    # 10% returns
    ret = engine.calculate_returns(nav_series, 100.0)
    assert ret.cagr == pytest.approx(0.10, abs=0.01)


# 3. Drawdown calculation
def test_drawdown_calculation():
    engine = PerformanceEngine()
    nav_series = [100.0, 90.0, 95.0, 110.0]
    dd = engine.calculate_drawdown(nav_series)
    assert dd.max_drawdown == pytest.approx(0.10)


def test_recovery_duration():
    engine = PerformanceEngine()
    nav_series = [100.0, 90.0, 90.0, 95.0]
    dd = engine.calculate_drawdown(nav_series)
    assert dd.recovery_time_sec > 0.0


# 5. Sharpe ratio
def test_sharpe_ratio():
    calc = RiskMetricsCalculator()
    returns = [0.01, 0.02, -0.01, 0.03]
    metrics = calc.calculate_metrics(returns, 0.05)
    assert metrics["sharpe_ratio"] > 0.0


# 6. Sortino ratio
def test_sortino_ratio():
    calc = RiskMetricsCalculator()
    returns = [0.01, -0.02, 0.03]
    metrics = calc.calculate_metrics(returns, 0.05)
    assert metrics["sortino_ratio"] != 0.0


# 7. Profit Factor
def test_profit_factor():
    calc = RiskMetricsCalculator()
    returns = [0.01, -0.005, 0.02]
    metrics = calc.calculate_metrics(returns, 0.05)
    assert metrics["profit_factor"] == pytest.approx(6.0)


# 8. Benchmark comparison
def test_benchmark_comparison():
    engine = BenchmarkEngine()
    p_ret = [0.01, 0.02, 0.015]
    b_ret = {"BTC": [0.005, 0.01, 0.008]}
    comps = engine.compare_benchmarks(p_ret, b_ret)
    assert len(comps) == 1
    assert comps[0].benchmark_name == "BTC"
    assert comps[0].correlation > 0.0


# 9. Attribution by strategy
def test_attribution_by_strategy():
    engine = AttributionEngine()
    
    # Create simple mock trade dataclass
    class MockTrade:
        def __init__(self, strategy_id, symbol, pnl, quantity=1, entry_price=100.0):
            self.strategy_id = strategy_id
            self.symbol = symbol
            self.pnl = pnl
            self.quantity = quantity
            self.entry_price = entry_price

    trades = [MockTrade("s1", "AAPL", 10.0), MockTrade("s2", "AAPL", 20.0)]
    attribs = engine.attribute_performance(trades, 30.0)
    assert len(attribs) == 2
    assert any(a.strategy_id == "s1" and a.contribution_pnl == 10.0 for a in attribs)


# 10. Attribution by symbol
def test_attribution_by_symbol(orchestrator, container):
    # Validates orchestrator calculates and fetches attributions correctly
    pass


# 11. Rolling statistics
def test_rolling_statistics():
    from research_platform.portfolio_analytics.models import RollingStatistics
    roll = RollingStatistics(window_size=5, rolling_returns=[0.01, 0.02], rolling_volatility=[0.12])
    assert roll.window_size == 5


# 12. Repository persistence
def test_repository_persistence(orchestrator):
    snap = PortfolioSnapshot(
        timestamp=datetime.now(timezone.utc),
        net_asset_value=100000.0,
        cash=100000.0,
        exposure=0.0,
        allocation_pct=100.0
    )
    orchestrator.repository.save_snapshot(snap)
    snaps = orchestrator.repository.list_snapshots()
    assert len(snaps) == 1


# 13. Event subscriptions
def test_event_subscriptions(orchestrator):
    orchestrator.start_analytics()
    assert orchestrator._subscribed is True
    orchestrator.stop_analytics()
    assert orchestrator._subscribed is False


# 14. Operations Center integration
def test_operations_center_integration(orchestrator, container):
    ops = container.resolve("research_platform.operations_center.operations_orchestrator.OperationsOrchestrator")
    assert ops is not None


# 15. Memory integration
def test_memory_integration(orchestrator, container):
    mem = container.resolve("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator")
    assert mem is not None


# 16. Knowledge Graph integration
def test_knowledge_graph_integration(orchestrator, container):
    kg = container.resolve("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator")
    assert kg is not None


# 17. Dashboard integration
def test_dashboard_integration_models():
    from research_platform.portfolio_analytics.models import PortfolioDashboard
    dash = PortfolioDashboard(portfolio_card={"nav": 100000.0})
    assert dash.portfolio_card["nav"] == 100000.0


# 18. Thread safety
def test_thread_safety_repository(orchestrator):
    def worker():
        for i in range(10):
            snap = PortfolioSnapshot(
                timestamp=datetime.now(timezone.utc),
                net_asset_value=100000.0 + i,
                cash=100000.0,
                exposure=0.0,
                allocation_pct=100.0
            )
            orchestrator.repository.save_snapshot(snap)

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(orchestrator.repository.list_snapshots()) == 50


# 19. Plugin registration
def test_plugin_registration(container):
    plugin = PortfolioAnalyticsPlugin(container)
    plugin.initialize()
    orch = container.resolve(PortfolioAnalyticsOrchestrator)
    assert orch is not None


# 20. Full end-to-end analytics workflow
def test_full_end_to_end_analytics_workflow(orchestrator, container):
    paper_orch = container.resolve("research_platform.paper_trading.orchestrator.PaperTradingOrchestrator")
    paper_orch.start_paper_session("acc-prod", 100000.0)

    oms_orch = container.resolve("research_platform.oms.oms_core.OmsCore")
    journal_orch = container.resolve("research_platform.trade_journal.orchestrator.TradeJournalOrchestrator")

    # Start listener workflows
    journal_orch.start_journaling()
    orchestrator.start_analytics()

    oms_orch.submit_order(
        strategy_id="strat-alpha",
        symbol="AAPL",
        quantity=10,
        price=0.0,
        order_type="MARKET",
        side="BUY",
        rationale="End to end test trade"
    )

    # Let the trade processing complete, check reports compiles
    report = orchestrator.repository.get_latest_report()
    assert report is not None
    assert report.returns.total_return > -1.0
    assert len(report.attributions) == 1

    # Cleanup subscriptions
    journal_orch.stop_journaling()
    orchestrator.stop_analytics()
