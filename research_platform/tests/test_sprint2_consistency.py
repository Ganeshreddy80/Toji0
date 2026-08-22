"""Unit and integration tests for Sprint 2 consistency changes.
"""

from __future__ import annotations

import pytest
import uuid
from datetime import datetime, timezone

from research_platform.persistence.postgres.connection import DatabaseConnection
from research_platform.persistence.postgres.session import DatabaseSessionManager
from research_platform.persistence.postgres.migrations import run_migrations

from research_platform.persistence.repositories.order_repository import PostgresOrderRepository
from research_platform.persistence.repositories.trade_repository import PostgresTradeRepository
from research_platform.persistence.repositories.position_repository import PostgresPositionRepository
from research_platform.persistence.repositories.ledger_repository import PostgresLedgerRepository

from research_platform.oms.models import Order, OrderRequest
from research_platform.oms.order_state_machine import OrderStateMachine
from research_platform.portfolio_accounting.models import TradeLedgerEntry
from research_platform.live_trading.position_manager import PositionManager
from research_platform.live_trading.orchestrator import LiveTradingOrchestrator
from research_platform.live_trading.models import ActiveSignal
from toji_platform.core.event_bus import InMemoryEventBus
from research_platform.platform.service_registry import ServiceRegistry


@pytest.fixture(scope="function")
def db_conn():
    conn = DatabaseConnection({"host": "localhost", "port": 5432, "dbname": "test_toji_s2", "user": "postgres"})
    conn.initialize()
    run_migrations(conn.engine)
    return conn


@pytest.fixture(scope="function")
def session_mgr(db_conn):
    return DatabaseSessionManager(db_conn)


def test_order_state_machine_preserves_fields():
    state_machine = OrderStateMachine()
    
    req = OrderRequest(
        order_id="ord-123",
        symbol="BTCUSDT",
        direction="BUY",
        quantity=0.5,
        order_type="LIMIT",
        price=50000.0,
        strategy_id="strat-xyz"
    )
    
    order = Order(
        order_id="ord-123",
        strategy_id="strat-xyz",
        symbol="BTCUSDT",
        quantity=0.5,
        price=50000.0,
        order_type="LIMIT",
        side="BUY",
        status="NEW",
        request=req
    )
    
    validated = state_machine.transition(order, "VALIDATED")
    assert validated.status == "VALIDATED"
    assert validated.symbol == "BTCUSDT"
    assert validated.strategy_id == "strat-xyz"
    assert validated.quantity == 0.5
    assert validated.price == 50000.0
    assert validated.side == "BUY"


def test_ledger_repository_persistence(session_mgr):
    repo = PostgresLedgerRepository(session_mgr)
    
    entry = TradeLedgerEntry(
        trade_id="trd-1",
        order_id="ord-123",
        symbol="BTCUSDT",
        side="BUY",
        quantity=0.5,
        entry_price=50000.0,
        exit_price=0.0,
        commission=25.0,
        slippage=5.0,
        realized_pnl=0.0,
        timestamp=datetime.now(timezone.utc)
    )
    
    repo.save_entry(entry)
    
    fetched = repo.get_entry("trd-1")
    assert fetched is not None
    assert fetched.trade_id == "trd-1"
    assert fetched.symbol == "BTCUSDT"
    assert fetched.quantity == 0.5
    assert fetched.commission == 25.0
    
    # Duplicate save raises error on append-only logic (if implemented at database layer or facade)
    all_entries = repo.list_entries()
    assert len(all_entries) == 1
    assert all_entries[0].trade_id == "trd-1"


def test_position_manager_handles_reduction_to_zero():
    pm = PositionManager()
    
    # 1. Open position
    pm.update_position("BTCUSDT", 0.4, 50000.0)
    pos = pm.get_position("BTCUSDT")
    assert pos is not None
    assert pos.quantity == 0.4
    assert pos.entry_price == 50000.0
    
    # 2. Reduce to zero (closed)
    pm.update_position("BTCUSDT", -0.4, 55000.0)
    pos_closed = pm.get_position("BTCUSDT")
    assert pos_closed is None or pos_closed.quantity == 0.0
    assert pm.realized_pnl == 2000.0


def test_live_trading_orchestrator_open_position_guard():
    class DummyEMS:
        pass
    class DummyOMS:
        def __init__(self):
            self.orders = []
        def ingest_order(self, req):
            self.orders.append(req)
            return Order(order_id=req.order_id, status="ROUTED")
    class DummyTradeManager:
        def __init__(self, oms):
            self.oms = oms
        def execute_signal_trade(self, order_id, symbol, direction, quantity, price):
            req = OrderRequest(
                order_id=order_id, symbol=symbol, direction=direction,
                quantity=quantity, price=price, order_type="LIMIT"
            )
            self.oms.ingest_order(req)
            return True
            
    eb = InMemoryEventBus()
    oms = DummyOMS()
    ems = DummyEMS()
    
    orch = LiveTradingOrchestrator(
        event_bus=eb,
        oms=oms,
        ems=ems,
        governor=None
    )
    from unittest.mock import MagicMock
    orch._account = MagicMock()
    orch._recovery = MagicMock()
    orch._repo = MagicMock()
    orch._session_manager = MagicMock()
    orch._session_manager.session_id = "test-session"
    orch._trade_manager = DummyTradeManager(oms)
    
    signal1 = ActiveSignal(
        signal_id="sig-1",
        symbol="BTCUSDT",
        direction="BUY",
        strength=0.9
    )
    
    # 1. First signal goes through
    res1 = orch.ingest_market_signal(signal1)
    assert res1 is True
    # Fake successful execution position update
    orch._positions.update_position("BTCUSDT", 0.5, 50000.0)
    
    # 2. Same direction duplicate signal is blocked
    signal2 = ActiveSignal(
        signal_id="sig-2",
        symbol="BTCUSDT",
        direction="BUY",
        strength=0.85
    )
    res2 = orch.ingest_market_signal(signal2)
    assert res2 is False
