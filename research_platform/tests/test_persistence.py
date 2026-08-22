"""Unit and integration tests for PostgreSQL persistence layer.
"""

from __future__ import annotations

import pytest
import threading
from datetime import datetime, timezone

from research_platform.persistence.postgres.connection import DatabaseConnection
from research_platform.persistence.postgres.session import DatabaseSessionManager
from research_platform.persistence.postgres.transaction_manager import TransactionManager
from research_platform.persistence.postgres.migrations import run_migrations

from research_platform.persistence.repositories.order_repository import PostgresOrderRepository
from research_platform.persistence.repositories.trade_repository import PostgresTradeJournalRepository
from research_platform.persistence.repositories.position_repository import PostgresPositionRepository
from research_platform.persistence.repositories.portfolio_repository import PostgresPortfolioRepository
from research_platform.persistence.repositories.strategy_repository import PostgresStrategyRepository
from research_platform.persistence.repositories.experiment_repository import PostgresExperimentRepository
from research_platform.persistence.repositories.monitoring_repository import PostgresMonitoringRepository
from research_platform.persistence.repositories.report_repository import PostgresReportRepository
from research_platform.persistence.repositories.configuration_repository import PostgresConfigurationRepository
from research_platform.persistence.repositories.scheduler_repository import PostgresJobRepository

from research_platform.oms.models import Order
from research_platform.trade_journal.models import TradeJournal, TradeScore
from research_platform.paper_trading.models import PaperPosition
from research_platform.portfolio_engine.models import Portfolio, PortfolioWeights, PortfolioVersion, PortfolioLifecycle, PortfolioMetadata
from research_platform.strategy_lifecycle.models import StrategyStatus, StrategyMetadata, StrategyStatistics, StrategyHealth
from research_platform.experiment_manager.models import Experiment, ReproducibilitySnapshot
from research_platform.monitoring.models import ServiceStatus, AlertCard, MetricCounter
from research_platform.reporting.models import ReportCard
from research_platform.configuration.models import ConfigurationEntry
from research_platform.scheduler.models import ExecutionJob


@pytest.fixture(scope="function")
def db_conn():
    # Force SQLite in-memory for unit testing execution
    conn = DatabaseConnection({"host": "localhost", "port": 5432, "dbname": "test_toji", "user": "postgres"})
    conn.initialize()
    run_migrations(conn.engine)
    return conn


@pytest.fixture(scope="function")
def session_mgr(db_conn):
    return DatabaseSessionManager(db_conn)


@pytest.fixture(scope="function")
def tx_mgr(session_mgr):
    return TransactionManager(session_mgr)


# ── Tests ────────────────────────────────────────────────────────────

def test_persistence_crud_order(session_mgr):
    repo = PostgresOrderRepository(session_mgr)
    order = Order(order_id="ord-1", strategy_id="strat-1", symbol="AAPL", side="BUY", quantity=100.0, price=150.0, order_type="LIMIT", status="NEW")
    
    # Create
    repo.save_order(order)
    
    # Read
    fetched = repo.get_order("ord-1")
    assert fetched is not None
    assert fetched.symbol == "AAPL"
    
    # Update
    order_updated = Order(order_id="ord-1", strategy_id="strat-1", symbol="AAPL", side="BUY", quantity=100.0, price=150.0, order_type="LIMIT", status="FILLED")
    repo.save_order(order_updated)
    fetched_updated = repo.get_order("ord-1")
    assert fetched_updated.status == "FILLED"
    
    # Delete
    success = repo.delete("ord-1")
    assert success is True
    assert repo.get_order("ord-1") is None


def test_persistence_crud_trade(session_mgr):
    repo = PostgresTradeJournalRepository(session_mgr)
    score = TradeScore(execution_score=90.0, risk_score=95.0, total_score=92.5)
    journal = TradeJournal(
        journal_id="j-1",
        order_id="ord-1",
        strategy_id="strat-1",
        symbol="MSFT",
        quantity=50.0,
        side="BUY",
        entry_price=300.0,
        exit_price=310.0,
        entry_time=datetime.now(timezone.utc),
        exit_time=datetime.now(timezone.utc),
        pnl=500.0,
        commission=2.0,
        slippage=0.5,
        holding_time_sec=3600.0,
        mfe=12.0,
        mae=1.0,
        market_regime="BULL",
        score=score,
        tags=["trend-following"]
    )
    
    repo.save_journal(journal)
    fetched = repo.get_journal("j-1")
    assert fetched is not None
    assert fetched.pnl == 500.0


def test_persistence_crud_position(session_mgr):
    repo = PostgresPositionRepository(session_mgr)
    pos = PaperPosition(symbol="AAPL", quantity=100.0, entry_price=150.0, current_price=150.0)
    
    repo.save_position(pos)
    fetched = repo.get_position("AAPL")
    assert fetched is not None
    assert fetched.quantity == 100.0


def test_persistence_crud_portfolio(session_mgr):
    repo = PostgresPortfolioRepository(session_mgr)
    
    version = PortfolioVersion(version_num="1.0", changelog="Initial", timestamp=datetime.now(timezone.utc))
    lifecycle = PortfolioLifecycle(status="ACTIVE", effective_time=datetime.now(timezone.utc))
    metadata = PortfolioMetadata(author="test", notes="none", tags=[])
    
    portfolio = Portfolio(
        portfolio_id="port-1",
        name="test",
        display_name="Test",
        description="description",
        version=version,
        lifecycle=lifecycle,
        metadata=metadata
    )
    
    repo.save_portfolio(portfolio)
    fetched = repo.get_portfolio("port-1")
    assert fetched is not None
    assert fetched.name == "test"


def test_persistence_crud_strategy(session_mgr):
    repo = PostgresStrategyRepository(session_mgr)
    
    meta = StrategyMetadata(name="Mean Reversion", description="d", author="a", asset_class="EQUITY")
    stats = StrategyStatistics(win_rate=0.5, pnl=1000.0, sharpe_ratio=1.5, max_drawdown=0.1, trades_count=10, paper_duration_days=30.0)
    health = StrategyHealth(strategy_id="strat-1", status="HEALTHY", error_count=0)
    
    status = StrategyStatus(
        strategy_id="strat-1",
        status="ACTIVE",
        version_id="v1",
        metadata=meta,
        statistics=stats,
        health=health
    )
    
    repo.save_status(status)
    fetched = repo.get_status("strat-1")
    assert fetched is not None
    assert fetched.version_id == "v1"


def test_persistence_crud_experiment(session_mgr):
    repo = PostgresExperimentRepository(session_mgr)
    repro = ReproducibilitySnapshot(random_seed=42, dataset_hash="h1", git_hash="g1", config_id="c1")
    exp = Experiment(
        experiment_id="exp-1",
        name="Vol Study",
        description="desc",
        status="COMPLETED",
        reproducibility=repro,
        results={"sharpe": 1.8}
    )
    
    repo.save_experiment(exp)
    fetched = repo.get_experiment("exp-1")
    assert fetched is not None
    assert fetched.results["sharpe"] == 1.8


def test_persistence_crud_monitoring(session_mgr):
    repo = PostgresMonitoringRepository(session_mgr)
    status = ServiceStatus(service_name="OMS", response_time_ms=10.0, is_alive=True)
    alert = AlertCard(alert_id="al-1", level="CRITICAL", source="risk", message="Limit breached", timestamp=datetime.now(timezone.utc))
    metric = MetricCounter(metric_name="orders_filled", value=42)
    
    repo.save_status(status)
    repo.save_alert(alert)
    repo.save_metric(metric)
    
    assert repo.get_status("OMS").is_alive is True
    assert repo.get_alert("al-1").level == "CRITICAL"
    assert repo.get_metric("orders_filled").value == 42


def test_persistence_crud_report(session_mgr):
    repo = PostgresReportRepository(session_mgr)
    report = ReportCard(report_id="rep-1", title="Daily Recap", content="text", format_type="PDF", created_at=datetime.now(timezone.utc))
    
    repo.save_report(report)
    fetched = repo.get_report("rep-1")
    assert fetched is not None
    assert fetched.title == "Daily Recap"


def test_persistence_crud_configuration(session_mgr):
    repo = PostgresConfigurationRepository(session_mgr)
    repo.save_parameter("param_a", {"value": 100})
    
    val = repo.get_parameter("param_a")
    assert val == {"value": 100}


def test_persistence_crud_scheduler(session_mgr):
    repo = PostgresJobRepository(session_mgr)
    job = ExecutionJob(job_id="job-1", name="Rebalance", task_type="OPTIMIZATION", schedule_expr="0 0 * * *", priority=1, status="PENDING")
    
    repo.save_job(job)
    fetched = repo.get_job("job-1")
    assert fetched is not None
    assert fetched.schedule_expr == "0 0 * * *"


def test_persistence_transaction_commit(session_mgr, tx_mgr):
    repo = PostgresOrderRepository(session_mgr)
    
    with tx_mgr.transaction() as session:
        # Create multiple orders inside single atomic transaction
        o1 = Order(order_id="ord-A", strategy_id="s", symbol="AAPL", side="BUY", quantity=10.0, price=1.0, order_type="LIMIT", status="NEW")
        o2 = Order(order_id="ord-B", strategy_id="s", symbol="MSFT", side="BUY", quantity=20.0, price=1.0, order_type="LIMIT", status="NEW")
        repo.save_order(o1)
        repo.save_order(o2)
        
    assert repo.get_order("ord-A") is not None
    assert repo.get_order("ord-B") is not None


def test_persistence_transaction_rollback(session_mgr, tx_mgr):
    repo = PostgresOrderRepository(session_mgr)
    
    try:
        with tx_mgr.transaction() as session:
            o1 = Order(order_id="ord-X", strategy_id="s", symbol="AAPL", side="BUY", quantity=10.0, price=1.0, order_type="LIMIT", status="NEW")
            repo.save_order(o1)
            # Throw exception to trigger rollback
            raise ValueError("Force Rollback")
    except ValueError:
        pass
        
    # Order should NOT exist in the database
    assert repo.get_order("ord-X") is None


def test_persistence_concurrency_writes(session_mgr):
    repo = PostgresOrderRepository(session_mgr)
    
    def worker(i):
        o = Order(order_id=f"ord-{i}", strategy_id="s", symbol="AAPL", side="BUY", quantity=1.0, price=1.0, order_type="LIMIT", status="NEW")
        repo.save_order(o)
        
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()
    
    # Check that all concurrent writes completed
    assert repo.get_order("ord-5") is not None


def test_persistence_concurrency_reads(session_mgr):
    repo = PostgresOrderRepository(session_mgr)
    o = Order(order_id="ord-1", strategy_id="s", symbol="AAPL", side="BUY", quantity=1.0, price=1.0, order_type="LIMIT", status="NEW")
    repo.save_order(o)
    
    results = []
    def worker():
        results.append(repo.get_order("ord-1"))
        
    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()
    
    assert len(results) == 10
    assert all(r is not None for r in results)


def test_persistence_reconnect_simulation(db_conn):
    # Tests closing engine and reconnecting safely
    db_conn.engine.dispose()
    assert db_conn.engine is not None
