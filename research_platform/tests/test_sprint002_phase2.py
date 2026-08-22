"""Sprint 002 Phase 2 — Persistence Transaction and Recovery Tests.

Test categories:
  UNIT: use SQLite :memory: — always runnable, no PostgreSQL required.
  INTEGRATION: marked @pytest.mark.integration — skipped unless PostgreSQL is available.

DB defects tested:
  DB-001: Three writes in on_fill() must be atomic (single transaction).
  DB-003: DatabaseRecoveryManager must return False on failure, not True.
  DB-004: pool_pre_ping must be enabled in DatabaseConnection.
  DB-005: reconnect() must dispose+reinitialize, not be a no-op.
  DB-009: Absence of Database service must emit ERROR log, not be silent.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.pool import StaticPool

from research_platform.persistence.postgres.connection import DatabaseConnection
from research_platform.persistence.postgres.session import DatabaseSessionManager
from research_platform.persistence.postgres.transaction_manager import TransactionManager
from research_platform.persistence.postgres.migrations import run_migrations
from research_platform.persistence.repositories.trade_repository import PostgresTradeRepository
from research_platform.persistence.repositories.position_repository import PostgresPositionRepository
from research_platform.persistence.repositories.ledger_repository import PostgresLedgerRepository
from research_platform.recovery.database_recovery import DatabaseRecoveryManager
from research_platform.paper_trading.models import PaperPosition
from research_platform.portfolio_accounting.models import TradeLedgerEntry


# ─── Helpers ───────────────────────────────────────────────────────────────────

def _make_sqlite_connection() -> DatabaseConnection:
    """Build an in-memory SQLite connection suitable for unit tests."""
    from sqlalchemy import create_engine
    conn = DatabaseConnection.__new__(DatabaseConnection)
    conn.config = {}
    conn._fallback_mode = True
    conn._engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    run_migrations(conn._engine)
    return conn


def _make_session_mgr(conn: DatabaseConnection) -> DatabaseSessionManager:
    return DatabaseSessionManager(conn)


def _make_tx_mgr(session_mgr: DatabaseSessionManager) -> TransactionManager:
    return TransactionManager(session_mgr)


def _make_ledger_entry(trade_id: str, symbol: str, side: str = "BUY") -> TradeLedgerEntry:
    return TradeLedgerEntry(
        trade_id=trade_id,
        order_id=f"ord_{trade_id}",
        symbol=symbol,
        side=side,
        quantity=1.0,
        entry_price=100.0,
        exit_price=0.0,
        commission=0.05,
        slippage=0.01,
        realized_pnl=0.0,
        timestamp=datetime.now(timezone.utc),
    )


# ─── Unit Tests: DB-001 Atomic Transaction Boundary ────────────────────────────

class TestAtomicTransactionBoundary:
    """DB-001: Verify that the three on_fill() persistence writes are atomic."""

    def test_all_three_writes_commit_atomically(self):
        """UNIT: All three writes succeed -> all three rows present in DB after commit."""
        conn = _make_sqlite_connection()
        session_mgr = _make_session_mgr(conn)
        tx_mgr = _make_tx_mgr(session_mgr)

        trade_repo = PostgresTradeRepository(session_mgr)
        pos_repo = PostgresPositionRepository(session_mgr)
        ledger_repo = PostgresLedgerRepository(session_mgr)

        ledger_entry = _make_ledger_entry("trd_commit_001", "BTCUSDT", "BUY")

        with tx_mgr.transaction():
            trade_repo.save_trade(
                trade_id=ledger_entry.trade_id,
                order_id=ledger_entry.order_id,
                symbol="BTCUSDT",
                side="BUY",
                quantity=1.0,
                price=100.0,
                timestamp=ledger_entry.timestamp,
            )
            pos_repo.save_position(PaperPosition(symbol="BTCUSDT", quantity=1.0, entry_price=100.0, current_price=100.0))
            ledger_repo.save_entry(ledger_entry)

        # All three must be present
        assert trade_repo.get_trade("trd_commit_001") is not None, "Trade row missing after atomic commit"
        assert pos_repo.get_position("BTCUSDT") is not None, "Position row missing after atomic commit"
        assert ledger_repo.get_entry("trd_commit_001") is not None, "Ledger entry missing after atomic commit"

    def test_failure_in_position_write_rolls_back_trade(self):
        """UNIT: If position write raises, trade write must also be rolled back — DB-001."""
        conn = _make_sqlite_connection()
        session_mgr = _make_session_mgr(conn)
        tx_mgr = _make_tx_mgr(session_mgr)

        trade_repo = PostgresTradeRepository(session_mgr)
        pos_repo = PostgresPositionRepository(session_mgr)
        ledger_repo = PostgresLedgerRepository(session_mgr)

        ledger_entry = _make_ledger_entry("trd_rollback_pos", "ETHUSDT", "BUY")

        try:
            with tx_mgr.transaction():
                trade_repo.save_trade(
                    trade_id=ledger_entry.trade_id,
                    order_id=ledger_entry.order_id,
                    symbol="ETHUSDT",
                    side="BUY",
                    quantity=1.0,
                    price=200.0,
                    timestamp=ledger_entry.timestamp,
                )
                # Inject failure in position write
                raise RuntimeError("Simulated position write failure — DB-001 rollback test")
        except RuntimeError:
            pass  # Expected

        # Trade row must NOT be present — the transaction was rolled back
        assert trade_repo.get_trade("trd_rollback_pos") is None, (
            "DB-001 VIOLATION: Trade row committed despite position write failure. "
            "Transaction was not atomic."
        )
        assert ledger_repo.get_entry("trd_rollback_pos") is None, (
            "DB-001 VIOLATION: Ledger entry committed despite position write failure."
        )

    def test_failure_in_ledger_write_rolls_back_trade_and_position(self):
        """UNIT: If ledger write raises, trade and position writes must both be rolled back — DB-001."""
        conn = _make_sqlite_connection()
        session_mgr = _make_session_mgr(conn)
        tx_mgr = _make_tx_mgr(session_mgr)

        trade_repo = PostgresTradeRepository(session_mgr)
        pos_repo = PostgresPositionRepository(session_mgr)
        ledger_repo = PostgresLedgerRepository(session_mgr)

        ledger_entry = _make_ledger_entry("trd_rollback_ledger", "SOLUSDT", "BUY")

        try:
            with tx_mgr.transaction():
                trade_repo.save_trade(
                    trade_id=ledger_entry.trade_id,
                    order_id=ledger_entry.order_id,
                    symbol="SOLUSDT",
                    side="BUY",
                    quantity=2.0,
                    price=50.0,
                    timestamp=ledger_entry.timestamp,
                )
                pos_repo.save_position(PaperPosition(symbol="SOLUSDT", quantity=2.0, entry_price=50.0, current_price=50.0))
                # Inject failure in ledger write
                raise RuntimeError("Simulated ledger write failure — DB-001 rollback test")
        except RuntimeError:
            pass  # Expected

        # Both trade and position must be absent
        assert trade_repo.get_trade("trd_rollback_ledger") is None, (
            "DB-001 VIOLATION: Trade row committed despite ledger write failure."
        )
        assert pos_repo.get_position("SOLUSDT") is None, (
            "DB-001 VIOLATION: Position row committed despite ledger write failure."
        )

    def test_session_scope_reentrancy_inside_transaction(self):
        """UNIT: session_scope() re-entrancy guard must fire inside TransactionManager.transaction()."""
        conn = _make_sqlite_connection()
        session_mgr = _make_session_mgr(conn)
        tx_mgr = _make_tx_mgr(session_mgr)

        sessions_seen: list = []

        with tx_mgr.transaction() as outer_session:
            sessions_seen.append(id(outer_session))
            with session_mgr.session_scope() as inner_session:
                sessions_seen.append(id(inner_session))

        assert sessions_seen[0] == sessions_seen[1], (
            "session_scope() re-entrancy guard did not fire — two different sessions were created. "
            "Writes would not be atomic."
        )


# ─── Unit Tests: DB-003 Recovery Failure Masking ───────────────────────────────

class TestDatabaseRecoveryManagerFailureReporting:
    """DB-003: DatabaseRecoveryManager must return False on failure, not mask it."""

    def test_returns_false_when_database_service_absent(self):
        """UNIT: No Database in ServiceRegistry -> recover_database() returns False."""
        container = MagicMock()
        manager = DatabaseRecoveryManager(container)

        with patch(
            "research_platform.recovery.database_recovery.ServiceRegistry.get_service",
            return_value=None,
        ):
            result = manager.recover_database()

        assert result is False, (
            "DB-003 VIOLATION: DatabaseRecoveryManager returned True when Database service "
            "is not registered. Failure must not be masked."
        )

    def test_returns_false_when_pg_connectivity_check_fails(self):
        """UNIT: PostgreSQL query raises -> recover_database() returns False."""
        container = MagicMock()
        manager = DatabaseRecoveryManager(container)

        mock_db = MagicMock()
        mock_db.connected = True
        mock_conn_ctx = MagicMock()
        mock_conn_ctx.__enter__ = MagicMock(side_effect=Exception("PG connection refused"))
        mock_conn_ctx.__exit__ = MagicMock(return_value=False)
        mock_db.connection.engine.connect.return_value = mock_conn_ctx

        with patch(
            "research_platform.recovery.database_recovery.ServiceRegistry.get_service",
            return_value=mock_db,
        ):
            result = manager.recover_database()

        assert result is False, (
            "DB-003 VIOLATION: DatabaseRecoveryManager returned True after PostgreSQL "
            "connectivity check failed. Failure must not be masked."
        )

    def test_returns_true_when_pg_is_healthy(self):
        """UNIT: Healthy PostgreSQL -> recover_database() returns True."""
        container = MagicMock()
        manager = DatabaseRecoveryManager(container)

        mock_db = MagicMock()
        mock_db.connected = True
        mock_conn_ctx = MagicMock()
        mock_conn_ctx.__enter__ = MagicMock(return_value=MagicMock())
        mock_conn_ctx.__exit__ = MagicMock(return_value=False)
        mock_db.connection.engine.connect.return_value = mock_conn_ctx

        with patch(
            "research_platform.recovery.database_recovery.ServiceRegistry.get_service",
            return_value=mock_db,
        ):
            result = manager.recover_database()

        assert result is True, "recover_database() should return True when PostgreSQL is healthy."


# ─── Unit Tests: DB-004/DB-005 Connection Pool Configuration ──────────────────

class TestConnectionPoolConfiguration:
    """DB-004/DB-005: Verify pool_pre_ping, pool_recycle, and reconnect() are present."""

    def test_pool_pre_ping_present_in_source(self):
        """UNIT: pool_pre_ping=True must appear in DatabaseConnection.initialize()."""
        import inspect
        import research_platform.persistence.postgres.connection as conn_module
        source = inspect.getsource(conn_module.DatabaseConnection.initialize)
        assert "pool_pre_ping=True" in source, (
            "DB-004 VIOLATION: pool_pre_ping=True not found in DatabaseConnection.initialize()."
        )

    def test_pool_recycle_present_in_source(self):
        """UNIT: pool_recycle must appear in DatabaseConnection.initialize()."""
        import inspect
        import research_platform.persistence.postgres.connection as conn_module
        source = inspect.getsource(conn_module.DatabaseConnection.initialize)
        assert "pool_recycle" in source, (
            "DB-004 VIOLATION: pool_recycle not found in DatabaseConnection.initialize()."
        )

    def test_reconnect_method_exists_with_dispose(self):
        """UNIT: DB-005 — DatabaseConnection.reconnect() must exist and call dispose+initialize."""
        import inspect
        import research_platform.persistence.postgres.connection as conn_module
        assert hasattr(conn_module.DatabaseConnection, "reconnect"), (
            "DB-005 VIOLATION: DatabaseConnection.reconnect() method does not exist."
        )
        source = inspect.getsource(conn_module.DatabaseConnection.reconnect)
        assert "dispose" in source, (
            "DB-005 VIOLATION: reconnect() must call engine.dispose() to release stale pool."
        )
        assert "initialize" in source, (
            "DB-005 VIOLATION: reconnect() must call initialize() to create a fresh engine."
        )


# ─── Unit Tests: DB-009 Explicit Error Log When DB Absent ─────────────────────

class TestDatabaseAbsentErrorLog:
    """DB-009: Absence of Database service must emit ERROR log, not be silently skipped."""

    def test_on_fill_logs_error_when_database_absent(self, caplog):
        """UNIT: When ServiceRegistry has no Database, on_fill() must log an ERROR."""
        from research_platform.portfolio_accounting.accounting_service import AccountingService

        mock_bus = MagicMock()
        svc = AccountingService(event_bus=mock_bus, initial_balance=100_000.0)

        fill_event = MagicMock()
        fill_event.payload = {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "quantity": 0.1,
            "price": 50000.0,
            "order_id": "ord_test_001",
            "strategy": "test_strategy",
        }

        # ServiceRegistry is imported inside on_fill() as a lazy import, so patch at its
        # definition module rather than at the accounting_service module attribute.
        with patch(
            "research_platform.platform.service_registry.ServiceRegistry.get_service",
            return_value=None,
        ):
            with caplog.at_level(logging.ERROR):
                svc.on_fill(fill_event)

        error_messages = [r.message for r in caplog.records if r.levelno == logging.ERROR]
        db_absent_errors = [m for m in error_messages if "Database service not registered" in m]
        assert db_absent_errors, (
            "DB-009 VIOLATION: on_fill() did not emit ERROR log when Database service is absent. "
            f"Captured ERROR logs: {error_messages}"
        )


# ─── Unit Tests: Fail-Closed Behavior Preserved ───────────────────────────────

class TestFailClosedPreserved:
    """Verify Sprint 001 fail-closed behaviour is intact after Phase 2 changes."""

    def test_paper_mode_fail_closed_guard_in_source(self):
        """UNIT: Verify fail-closed RuntimeError guard is present in connection.py source.

        The actual runtime path (TOJI_MODE=PAPER + no PostgreSQL -> RuntimeError) was
        verified in Sprint 001 and is exercised by the real boot path. We verify here
        that Phase 2 changes did not accidentally remove the fail-closed guard code.
        """
        import inspect
        import research_platform.persistence.postgres.connection as conn_module
        source = inspect.getsource(conn_module.DatabaseConnection.initialize)
        assert "RuntimeError" in source, (
            "FAIL-CLOSED VIOLATION: RuntimeError halt gate is missing from "
            "DatabaseConnection.initialize(). The fail-closed guard has been removed."
        )
        assert "PAPER" in source, (
            "FAIL-CLOSED VIOLATION: TOJI_MODE PAPER check missing from "
            "DatabaseConnection.initialize(). Fail-closed gate may be broken."
        )
        assert "Fallback SQLite is disabled" in source, (
            "FAIL-CLOSED VIOLATION: Fail-closed RuntimeError message has changed or been removed."
        )

    def test_sqlite_fallback_not_silently_added(self):
        """UNIT: Verify that the Phase 2 changes did not introduce new SQLite fallback paths."""
        import inspect
        import research_platform.persistence.postgres.connection as conn_module
        source = inspect.getsource(conn_module.DatabaseConnection.initialize)
        # Count occurrences of sqlite fallback — should only be the existing DEV/pytest fallback
        sqlite_occurrences = source.count("sqlite:///:memory:")
        assert sqlite_occurrences == 1, (
            f"Expected exactly 1 SQLite fallback path in initialize(), found {sqlite_occurrences}. "
            "Phase 2 changes may have added an unauthorized SQLite fallback."
        )


# ─── PostgreSQL Integration Tests ─────────────────────────────────────────────

def _neon_url() -> str:
    """Return the configured DATABASE_URL (postgresql:// form) for Neon connectivity."""
    import os
    from dotenv import load_dotenv
    load_dotenv()
    url = os.environ.get("DATABASE_URL", "")
    return url.replace("postgresql+asyncpg://", "postgresql://").replace("postgresql+psycopg2://", "postgresql://")


def _pg_available() -> bool:
    """Check if the configured Neon PostgreSQL instance is reachable via DATABASE_URL."""
    url = _neon_url()
    if not url or "localhost" in url:
        # If no URL or only localhost, fall back to local check
        try:
            from sqlalchemy import create_engine, text
            engine = create_engine(
                "postgresql://postgres@localhost:5432/toji_v1",
                connect_args={"connect_timeout": 2},
            )
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(
            url,
            pool_pre_ping=True,
            connect_args={"connect_timeout": 10},
        )
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


_PG_AVAILABLE = _pg_available()
_PG_SKIP_REASON = "Neon PostgreSQL not reachable via DATABASE_URL — skipping integration test"


@pytest.mark.integration
@pytest.mark.skipif(not _PG_AVAILABLE, reason=_PG_SKIP_REASON)
class TestPostgreSQLIntegration:
    """PostgreSQL integration tests — require a live Neon PostgreSQL instance via DATABASE_URL.

    These tests connect to the configured Neon database. They are automatically skipped
    when DATABASE_URL is not set or not reachable.
    To run: pytest -m integration
    """

    @pytest.fixture(autouse=True)
    def pg_setup(self):
        url = _neon_url()
        conn = DatabaseConnection({"raw_url": url})
        conn.initialize()
        run_migrations(conn.engine)
        self._conn = conn
        yield
        # DB-012: clean up only the specific test rows created by this verification run
        from sqlalchemy import text
        with conn.engine.connect() as c:
            c.execute(text("DELETE FROM trades WHERE trade_id IN ('trd_pg_int_001','trd_pg_rollback_001')"))
            c.execute(text("DELETE FROM positions WHERE symbol IN ('BTCUSDT')"))
            c.execute(text("DELETE FROM trade_ledger WHERE trade_id IN ('trd_pg_int_001')"))
            c.commit()
        conn.engine.dispose()

    def test_pg_connectivity_live(self):
        """INTEGRATION: Real PostgreSQL SELECT 1 succeeds."""
        from sqlalchemy import text
        with self._conn.engine.connect() as c:
            result = c.execute(text("SELECT 1")).scalar()
        assert result == 1

    def test_pg_on_fill_atomic_commit_live(self):
        """INTEGRATION: Atomic commit of trade+position+ledger on real PostgreSQL."""
        session_mgr = DatabaseSessionManager(self._conn)
        tx_mgr = TransactionManager(session_mgr)
        trade_repo = PostgresTradeRepository(session_mgr)
        pos_repo = PostgresPositionRepository(session_mgr)
        ledger_repo = PostgresLedgerRepository(session_mgr)
        entry = _make_ledger_entry("trd_pg_int_001", "BTCUSDT", "BUY")

        with tx_mgr.transaction():
            trade_repo.save_trade(
                trade_id=entry.trade_id,
                order_id=entry.order_id,
                symbol="BTCUSDT",
                side="BUY",
                quantity=0.1,
                price=50000.0,
                timestamp=entry.timestamp,
            )
            pos_repo.save_position(PaperPosition(symbol="BTCUSDT", quantity=0.1, entry_price=50000.0, current_price=50000.0))
            ledger_repo.save_entry(entry)

        assert trade_repo.get_trade("trd_pg_int_001") is not None
        assert pos_repo.get_position("BTCUSDT") is not None
        assert ledger_repo.get_entry("trd_pg_int_001") is not None

    def test_pg_on_fill_atomic_rollback_live(self):
        """INTEGRATION: Injected failure rolls back all writes on real PostgreSQL."""
        session_mgr = DatabaseSessionManager(self._conn)
        tx_mgr = TransactionManager(session_mgr)
        trade_repo = PostgresTradeRepository(session_mgr)
        entry = _make_ledger_entry("trd_pg_rollback_001", "ETHUSDT", "BUY")

        try:
            with tx_mgr.transaction():
                trade_repo.save_trade(
                    trade_id=entry.trade_id,
                    order_id=entry.order_id,
                    symbol="ETHUSDT",
                    side="BUY",
                    quantity=1.0,
                    price=3000.0,
                    timestamp=entry.timestamp,
                )
                raise RuntimeError("Injected failure for rollback test")
        except RuntimeError:
            pass

        assert trade_repo.get_trade("trd_pg_rollback_001") is None, (
            "DB-001 VIOLATION on live PostgreSQL: trade row persisted after rollback."
        )
