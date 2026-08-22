"""Unit and integration tests for the TOJI Institutional Paper Trading Foundation.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from toji_platform.core.dependency_injection import Container
from toji_platform.core.event_bus import InMemoryEventBus

from research_platform.paper_trading.models import (
    PaperAccount,
    PaperOrder,
    PaperPosition,
)
from research_platform.paper_trading.orchestrator import PaperTradingOrchestrator
from research_platform.paper_trading.paper_exchange import PaperExchange
from research_platform.paper_trading.broker_adapter import PaperBrokerAdapter
from research_platform.paper_trading.account import AccountManager
from research_platform.paper_trading.portfolio_tracker import PortfolioTracker

# Integration components
from research_platform.institutional_memory.orchestrator import InstitutionalMemoryOrchestrator
from research_platform.knowledge_graph.orchestrator import KnowledgeGraphOrchestrator


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

    return c


@pytest.fixture
def orchestrator(event_bus, container):
    return PaperTradingOrchestrator(event_bus, container=container)


def test_paper_exchange_order_matching():
    """Verify market and limit order matching logic."""
    exchange = PaperExchange()

    # Market BUY matches with half-spread slippage
    order = PaperOrder(order_id="o1", strategy_id="s1", symbol="AAPL", quantity=10, price=0.0, order_type="MARKET", side="BUY")
    res = exchange.match_order(order, price=150.0, spread=0.10)
    assert res.status == "FILLED"
    assert res.executed_price == 150.05
    assert res.executed_quantity == 10

    # Limit BUY remains pending if ask is above limit price
    order_limit = PaperOrder(order_id="o2", strategy_id="s1", symbol="AAPL", quantity=10, price=149.0, order_type="LIMIT", side="BUY")
    res_limit = exchange.match_order(order_limit, price=150.0, spread=0.10)  # Ask is 150.05
    assert res_limit.status == "PENDING"

    # Limit BUY fills if ask is lower or equal to limit price
    order_limit_fill = PaperOrder(order_id="o3", strategy_id="s1", symbol="AAPL", quantity=10, price=151.0, order_type="LIMIT", side="BUY")
    res_limit_fill = exchange.match_order(order_limit_fill, price=150.0, spread=0.10)
    assert res_limit_fill.status == "FILLED"
    assert res_limit_fill.executed_price == 151.0


def test_account_balance_adjustments_on_fills():
    """Verify that virtual account cash balance updates correctly on buy fills."""
    manager = AccountManager()
    account = PaperAccount(account_id="acc-1", initial_balance=100000.0, cash=100000.0, equity=100000.0)

    # Buy AAPL costing 1500 USD with 1 USD commission fee
    updated = manager.update_balance_on_fill(account, quantity=10, price=150.0, side="BUY", commission=1.0)
    assert updated.cash == 98499.0


def test_peak_drawdown_calculation():
    """Verify portfolio tracker correctly tracks peak equity and drawdowns."""
    tracker = PortfolioTracker()
    account = PaperAccount(account_id="acc-1", initial_balance=100000.0, cash=100000.0, equity=100000.0)

    # 1. Equity grows to 105,000 -> peak equity becomes 105,000, drawdown is 0
    updated_1 = tracker.calculate_drawdown(account, open_positions_val=5000.0)
    assert updated_1.equity == 105000.0
    assert updated_1.drawdown == 0.0

    # 2. Equity drops to 99,750 (drawdown from peak 105,000 is 5%)
    updated_2 = tracker.calculate_drawdown(updated_1, open_positions_val=-250.0)
    assert updated_2.equity == 99750.0
    assert updated_2.drawdown == pytest.approx(0.05)


def test_orchestrator_paper_trading_session_flow(orchestrator, container):
    """Verify paper orchestrator executes full session boot, trade matching, and downstreams."""
    # 1. Start Session
    sess = orchestrator.start_paper_session(account_id="acc-prod", initial_balance=100000.0)
    assert orchestrator.active_session is not None
    assert orchestrator.active_session.session_id == sess.session_id

    # 2. Submit order -> will execute immediately against mock broker
    filled = orchestrator.submit_paper_order(
        strategy_id="strat-alpha",
        symbol="AAPL",
        quantity=10,
        price=0.0,
        order_type="MARKET",
        side="BUY",
        rationale="Sandbox test rationale"
    )
    assert filled.status == "FILLED"
    assert filled.executed_price == 100.01  # price=100.0 + half-spread=0.01

    # Check journal logged
    journals = orchestrator.repository.list_journals()
    assert len(journals) == 1
    assert journals[0].symbol == "AAPL"

    # Update market price to evaluate unrealized PnL
    orchestrator.update_market_price("AAPL", 110.0)
    assert orchestrator.active_session.account.unrealized_pnl == 0.0  # (Updated position unrealized pnl = 10 * (110 - 100.01) = 99.9)
    # Check position open value
    pos = orchestrator.repository.get_position("AAPL")
    assert pos.unrealized_pnl == pytest.approx(99.9)

    # 3. Stop Session
    stopped = orchestrator.stop_paper_session()
    assert stopped.status == "INACTIVE"
    assert orchestrator.active_session is None
