"""Comprehensive unit and integration tests for TOJI Strategy Lifecycle Subsystem.
"""

from __future__ import annotations

import pytest
import threading
from datetime import datetime, timezone

from toji_platform.core.dependency_injection import Container
from toji_platform.core.event_bus import InMemoryEventBus

from research_platform.strategy_lifecycle.orchestrator import StrategyLifecycleOrchestrator
from research_platform.strategy_lifecycle.models import StrategyStatus, StrategyStatistics, StrategyHealth, StrategyMetadata
from research_platform.strategy_lifecycle.plugin import StrategyLifecyclePlugin

# Dependencies
from research_platform.oms.oms_core import OmsCore
from research_platform.paper_trading.orchestrator import PaperTradingOrchestrator
from research_platform.paper_market.orchestrator import PaperMarketOrchestrator
from research_platform.trade_journal.orchestrator import TradeJournalOrchestrator
from research_platform.portfolio_analytics.orchestrator import PortfolioAnalyticsOrchestrator
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

    analytics_orch = PortfolioAnalyticsOrchestrator(event_bus, container=c)
    c.register("research_platform.portfolio_analytics.orchestrator.PortfolioAnalyticsOrchestrator", instance=analytics_orch)

    return c


@pytest.fixture
def orchestrator(event_bus, container):
    return StrategyLifecycleOrchestrator(event_bus, container=container)


# 1. Lifecycle initialization
def test_strategy_creation(orchestrator):
    status = orchestrator.create_strategy("s-alpha", "Alpha", "Desc", "Author", "Crypto")
    assert status.status == "DRAFT"
    assert status.strategy_id == "s-alpha"


# 2-9. Valid state transitions
def test_transition_draft_to_research(orchestrator):
    orchestrator.create_strategy("s1", "Alpha", "Desc", "Author", "Crypto")
    res = orchestrator.transition_strategy_state("s1", "RESEARCH", "cto", "Proceed")
    assert res.status == "RESEARCH"


def test_transition_research_to_backtest(orchestrator):
    orchestrator.create_strategy("s1", "Alpha", "Desc", "Author", "Crypto")
    orchestrator.transition_strategy_state("s1", "RESEARCH", "cto", "Proceed")
    res = orchestrator.transition_strategy_state("s1", "BACKTEST", "cto", "Proceed")
    assert res.status == "BACKTEST"


def test_transition_backtest_to_optimization(orchestrator):
    orchestrator.create_strategy("s1", "Alpha", "Desc", "Author", "Crypto")
    orchestrator.transition_strategy_state("s1", "RESEARCH", "cto", "Proceed")
    orchestrator.transition_strategy_state("s1", "BACKTEST", "cto", "Proceed")
    res = orchestrator.transition_strategy_state("s1", "OPTIMIZATION", "cto", "Proceed")
    assert res.status == "OPTIMIZATION"


def test_transition_optimization_to_walkforward(orchestrator):
    orchestrator.create_strategy("s1", "Alpha", "Desc", "Author", "Crypto")
    orchestrator.transition_strategy_state("s1", "RESEARCH", "cto", "Proceed")
    orchestrator.transition_strategy_state("s1", "BACKTEST", "cto", "Proceed")
    orchestrator.transition_strategy_state("s1", "OPTIMIZATION", "cto", "Proceed")
    res = orchestrator.transition_strategy_state("s1", "WALKFORWARD", "cto", "Proceed")
    assert res.status == "WALKFORWARD"


def test_transition_walkforward_to_paper(orchestrator):
    orchestrator.create_strategy("s1", "Alpha", "Desc", "Author", "Crypto")
    orchestrator.transition_strategy_state("s1", "RESEARCH", "cto", "Proceed")
    orchestrator.transition_strategy_state("s1", "BACKTEST", "cto", "Proceed")
    orchestrator.transition_strategy_state("s1", "OPTIMIZATION", "cto", "Proceed")
    orchestrator.transition_strategy_state("s1", "WALKFORWARD", "cto", "Proceed")
    res = orchestrator.transition_strategy_state("s1", "PAPER", "cto", "Proceed")
    assert res.status == "PAPER"


def test_transition_paper_to_candidate_success(orchestrator):
    orchestrator.create_strategy("s1", "Alpha", "Desc", "Author", "Crypto")
    orchestrator.transition_strategy_state("s1", "RESEARCH", "cto", "Proceed")
    orchestrator.transition_strategy_state("s1", "BACKTEST", "cto", "Proceed")
    orchestrator.transition_strategy_state("s1", "OPTIMIZATION", "cto", "Proceed")
    orchestrator.transition_strategy_state("s1", "WALKFORWARD", "cto", "Proceed")
    orchestrator.transition_strategy_state("s1", "PAPER", "cto", "Proceed")

    # Manually configure statistics to pass thresholds
    strategy = orchestrator.repository.get_status("s1")
    stats = StrategyStatistics(
        win_rate=0.55,
        pnl=1500.0,
        sharpe_ratio=2.1,
        max_drawdown=0.08,
        trades_count=12,
        paper_duration_days=6.0
    )
    orchestrator.repository.save_status(strategy.model_copy(update={"statistics": stats}))

    res = orchestrator.transition_strategy_state("s1", "CANDIDATE", "cto", "Proceed")
    assert res.status == "CANDIDATE"


def test_transition_candidate_to_approved(orchestrator):
    orchestrator.create_strategy("s1", "Alpha", "Desc", "Author", "Crypto")
    orchestrator.repository.save_status(orchestrator.repository.get_status("s1").model_copy(update={"status": "CANDIDATE"}))
    res = orchestrator.transition_strategy_state("s1", "APPROVED", "cto", "Proceed")
    assert res.status == "APPROVED"


def test_transition_approved_to_production(orchestrator):
    orchestrator.create_strategy("s1", "Alpha", "Desc", "Author", "Crypto")
    orchestrator.repository.save_status(orchestrator.repository.get_status("s1").model_copy(update={"status": "APPROVED"}))
    res = orchestrator.transition_strategy_state("s1", "PRODUCTION", "cto", "Proceed")
    assert res.status == "PRODUCTION"


# 10-12. Paused/retired workflows
def test_transition_production_to_paused(orchestrator):
    orchestrator.create_strategy("s1", "Alpha", "Desc", "Author", "Crypto")
    orchestrator.repository.save_status(orchestrator.repository.get_status("s1").model_copy(update={"status": "PRODUCTION"}))
    res = orchestrator.transition_strategy_state("s1", "PAUSED", "cto", "Proceed")
    assert res.status == "PAUSED"


def test_transition_paused_to_production(orchestrator):
    orchestrator.create_strategy("s1", "Alpha", "Desc", "Author", "Crypto")
    orchestrator.repository.save_status(orchestrator.repository.get_status("s1").model_copy(update={"status": "PAUSED"}))
    res = orchestrator.transition_strategy_state("s1", "PRODUCTION", "cto", "Proceed")
    assert res.status == "PRODUCTION"


def test_transition_production_to_retired(orchestrator):
    orchestrator.create_strategy("s1", "Alpha", "Desc", "Author", "Crypto")
    orchestrator.repository.save_status(orchestrator.repository.get_status("s1").model_copy(update={"status": "PRODUCTION"}))
    res = orchestrator.transition_strategy_state("s1", "RETIRED", "cto", "Proceed")
    assert res.status == "RETIRED"


# 13-15. Invalid state transitions blocks
def test_invalid_transition_draft_to_production(orchestrator):
    orchestrator.create_strategy("s1", "Alpha", "Desc", "Author", "Crypto")
    with pytest.raises(ValueError, match="Invalid Transition"):
        orchestrator.transition_strategy_state("s1", "PRODUCTION", "cto", "Proceed")


def test_invalid_transition_backtest_to_paper(orchestrator):
    orchestrator.create_strategy("s1", "Alpha", "Desc", "Author", "Crypto")
    orchestrator.repository.save_status(orchestrator.repository.get_status("s1").model_copy(update={"status": "BACKTEST"}))
    with pytest.raises(ValueError, match="Invalid Transition"):
        orchestrator.transition_strategy_state("s1", "PAPER", "cto", "Proceed")


def test_invalid_transition_paused_to_backtest(orchestrator):
    orchestrator.create_strategy("s1", "Alpha", "Desc", "Author", "Crypto")
    orchestrator.repository.save_status(orchestrator.repository.get_status("s1").model_copy(update={"status": "PAUSED"}))
    with pytest.raises(ValueError, match="Invalid Transition"):
        orchestrator.transition_strategy_state("s1", "BACKTEST", "cto", "Proceed")


# 16-20. Promotion Engine threshold validation rejections
def test_promotion_rejected_low_trades(orchestrator):
    orchestrator.create_strategy("s1", "Alpha", "Desc", "Author", "Crypto")
    orchestrator.repository.save_status(orchestrator.repository.get_status("s1").model_copy(update={"status": "PAPER"}))
    
    # 5 trades count (threshold = 10)
    stats = StrategyStatistics(win_rate=0.55, pnl=1500.0, sharpe_ratio=2.1, max_drawdown=0.08, trades_count=5, paper_duration_days=6.0)
    orchestrator.repository.save_status(orchestrator.repository.get_status("s1").model_copy(update={"statistics": stats}))

    with pytest.raises(ValueError, match="Promotion Blocked"):
        orchestrator.transition_strategy_state("s1", "CANDIDATE", "cto", "Proceed")


def test_promotion_rejected_low_sharpe(orchestrator):
    orchestrator.create_strategy("s1", "Alpha", "Desc", "Author", "Crypto")
    orchestrator.repository.save_status(orchestrator.repository.get_status("s1").model_copy(update={"status": "PAPER"}))
    
    # 0.8 Sharpe (threshold = 1.5)
    stats = StrategyStatistics(win_rate=0.55, pnl=1500.0, sharpe_ratio=0.8, max_drawdown=0.08, trades_count=12, paper_duration_days=6.0)
    orchestrator.repository.save_status(orchestrator.repository.get_status("s1").model_copy(update={"statistics": stats}))

    with pytest.raises(ValueError, match="Promotion Blocked"):
        orchestrator.transition_strategy_state("s1", "CANDIDATE", "cto", "Proceed")


def test_promotion_rejected_high_drawdown(orchestrator):
    orchestrator.create_strategy("s1", "Alpha", "Desc", "Author", "Crypto")
    orchestrator.repository.save_status(orchestrator.repository.get_status("s1").model_copy(update={"status": "PAPER"}))
    
    # 22% drawdown (threshold = 15%)
    stats = StrategyStatistics(win_rate=0.55, pnl=1500.0, sharpe_ratio=2.1, max_drawdown=0.22, trades_count=12, paper_duration_days=6.0)
    orchestrator.repository.save_status(orchestrator.repository.get_status("s1").model_copy(update={"statistics": stats}))

    with pytest.raises(ValueError, match="Promotion Blocked"):
        orchestrator.transition_strategy_state("s1", "CANDIDATE", "cto", "Proceed")


def test_promotion_rejected_low_winrate(orchestrator):
    orchestrator.create_strategy("s1", "Alpha", "Desc", "Author", "Crypto")
    orchestrator.repository.save_status(orchestrator.repository.get_status("s1").model_copy(update={"status": "PAPER"}))
    
    # 35% win rate (threshold = 40%)
    stats = StrategyStatistics(win_rate=0.35, pnl=1500.0, sharpe_ratio=2.1, max_drawdown=0.08, trades_count=12, paper_duration_days=6.0)
    orchestrator.repository.save_status(orchestrator.repository.get_status("s1").model_copy(update={"statistics": stats}))

    with pytest.raises(ValueError, match="Promotion Blocked"):
        orchestrator.transition_strategy_state("s1", "CANDIDATE", "cto", "Proceed")


def test_promotion_rejected_low_duration(orchestrator):
    orchestrator.create_strategy("s1", "Alpha", "Desc", "Author", "Crypto")
    orchestrator.repository.save_status(orchestrator.repository.get_status("s1").model_copy(update={"status": "PAPER"}))
    
    # 3 days duration (threshold = 5 days)
    stats = StrategyStatistics(win_rate=0.55, pnl=1500.0, sharpe_ratio=2.1, max_drawdown=0.08, trades_count=12, paper_duration_days=3.0)
    orchestrator.repository.save_status(orchestrator.repository.get_status("s1").model_copy(update={"statistics": stats}))

    with pytest.raises(ValueError, match="Promotion Blocked"):
        orchestrator.transition_strategy_state("s1", "CANDIDATE", "cto", "Proceed")


# 21. Rollback Execution
def test_rollback_execution(orchestrator):
    res = orchestrator._rollback_engine.execute_rollback("s1", "v1.0.0", "Error rollback")
    assert res.strategy_id == "s1"
    assert res.to_version == "v1.0.0"


# 22. Approval engine logs
def test_approval_engine_logs(orchestrator):
    res = orchestrator._approval_engine.approve_gate("s1", "RISK", True, "reviewer-1", "Pass")
    assert res.gate_name == "RISK"
    assert res.approved is True


# 23. Audit engine logs
def test_audit_engine_logs(orchestrator):
    res = orchestrator._audit_engine.log_action("STATE_TRANSITION", "s1", "DRAFT", "RESEARCH", "cto", "Proceed")
    assert res.action == "STATE_TRANSITION"
    assert res.previous_state == "DRAFT"


# 24. Event Bus updates
def test_event_publication(orchestrator, event_bus):
    events = []
    def sub(event):
        events.append(event)
    event_bus.subscribe("system.strategy_created", sub)

    orchestrator.create_strategy("s1", "Alpha", "Desc", "Author", "Crypto")
    assert len(events) == 1


# 25. Repository queries
def test_repository_queries(orchestrator):
    orchestrator.create_strategy("s1", "Alpha", "Desc", "Author", "Crypto")
    orchestrator.create_strategy("s2", "Beta", "Desc", "Author", "Crypto")
    
    strats = orchestrator.repository.list_strategies()
    assert len(strats) == 2


# 26. Thread safety repository
def test_thread_safety_repository(orchestrator):
    def worker(idx):
        metadata = StrategyMetadata(name="Name", description="Desc", author="Author", asset_class="Crypto")
        stats = StrategyStatistics(win_rate=0.0, pnl=0.0, sharpe_ratio=0.0, max_drawdown=0.0, trades_count=0, paper_duration_days=0.0)
        health = StrategyHealth(strategy_id=f"thread-s-{idx}", status="HEALTHY", error_count=0)
        status = StrategyStatus(
            strategy_id=f"thread-s-{idx}",
            status="DRAFT",
            version_id="v1",
            metadata=metadata,
            statistics=stats,
            health=health
        )
        orchestrator.repository.save_status(status)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(orchestrator.repository.list_strategies()) == 10


# 27. Plugin resolution DI
def test_plugin_registration(container):
    plugin = StrategyLifecyclePlugin(container)
    plugin.initialize()
    orch = container.resolve(StrategyLifecycleOrchestrator)
    assert orch is not None


# 28. End-to-end lifecycle workflow
def test_full_end_to_end_lifecycle_workflow(orchestrator, container):
    # Setup paper trading session and mock fill returns to generate analytics
    paper_orch = container.resolve("research_platform.paper_trading.orchestrator.PaperTradingOrchestrator")
    paper_orch.start_paper_session("acc-prod", 100000.0)

    oms_orch = container.resolve("research_platform.oms.oms_core.OmsCore")
    journal_orch = container.resolve("research_platform.trade_journal.orchestrator.TradeJournalOrchestrator")
    analytics_orch = container.resolve("research_platform.portfolio_analytics.orchestrator.PortfolioAnalyticsOrchestrator")

    journal_orch.start_journaling()
    analytics_orch.start_analytics()

    # Place trades to populate analytics statistics
    for i in range(12):
        oms_orch.submit_order(
            strategy_id="strat-alpha",
            symbol="AAPL",
            quantity=10.0 + i,
            price=0.0,
            order_type="MARKET",
            side="BUY",
            rationale="Lifecycle backtest data generation"
        )

    # Compile analytics report
    report = analytics_orch.repository.get_latest_report()
    assert report is not None

    # Step through strategy transitions
    orchestrator.create_strategy("strat-alpha", "Alpha Core", "Core alpha returns", "Architect", "Equities")
    orchestrator.transition_strategy_state("strat-alpha", "RESEARCH", "cto", "Research verified")
    orchestrator.transition_strategy_state("strat-alpha", "BACKTEST", "cto", "Historical backtests run")
    orchestrator.transition_strategy_state("strat-alpha", "OPTIMIZATION", "cto", "Hyperparameters tuned")
    orchestrator.transition_strategy_state("strat-alpha", "WALKFORWARD", "cto", "Walk forward metrics validated")
    orchestrator.transition_strategy_state("strat-alpha", "PAPER", "cto", "Executing in paper sandbox")

    # Promoting to candidate triggers PromotionEngine metrics checks
    candidate_status = orchestrator.transition_strategy_state("strat-alpha", "CANDIDATE", "cto", "Passed paper duration")
    assert candidate_status.status == "CANDIDATE"

    # Complete gates approvals and promote to production
    orchestrator.transition_strategy_state("strat-alpha", "APPROVED", "cto", "Passed compliance signoff")
    prod_status = orchestrator.transition_strategy_state("strat-alpha", "PRODUCTION", "cto", "Deployed live")
    assert prod_status.status == "PRODUCTION"

    # Cleanup listeners
    journal_orch.stop_journaling()
    analytics_orch.stop_analytics()
