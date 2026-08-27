"""DATA-001-P0-03A — PostgreSQL integration tests for active schema.

These tests apply the foundation migration against a disposable PostgreSQL
database and introspect the resulting schema.  They verify tables, columns,
primary keys, foreign keys, unique constraints, indexes, CHECK constraints,
schema_version record, research-table isolation, and clean teardown.

Requirements:
    - Docker daemon running (for testcontainers)
    - ``testcontainers[postgres]`` and ``psycopg2-binary`` installed

If Docker is unavailable the entire module is skipped.
"""

from __future__ import annotations

import os
import re
from typing import Generator

import pytest

# ── Guard: skip if Docker / testcontainers unavailable ───────────────────────

try:
    from testcontainers.postgres import PostgresContainer  # type: ignore[import-untyped]
    import psycopg2  # type: ignore[import-untyped]
    import psycopg2.extras  # type: ignore[import-untyped]
    _HAS_DEPS = True
except ImportError:
    _HAS_DEPS = False

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _HAS_DEPS, reason="testcontainers or psycopg2 not installed"),
]

from toji_platform.persistence.schema import (
    REQUIRED_TABLES,
    SCHEMA_NAME,
    SchemaManifest,
)

# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def postgres_container() -> Generator:
    """Start a disposable PostgreSQL container for the module."""
    try:
        with PostgresContainer("postgres:16-alpine") as pg:
            yield pg
    except Exception as exc:
        pytest.skip(f"Docker unavailable or container failed: {exc}")


@pytest.fixture(scope="module")
def db_connection(postgres_container):
    """Return a psycopg2 connection to the disposable container."""
    conn = psycopg2.connect(
        host=postgres_container.get_container_host_ip(),
        port=postgres_container.get_exposed_port(5432),
        user=postgres_container.username,
        password=postgres_container.password,
        dbname=postgres_container.dbname,
    )
    conn.autocommit = False
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def applied_migration(db_connection) -> str:
    """Apply the 0001 migration and return the SQL text."""
    manifest = SchemaManifest()
    entry = manifest.get_version("0001")
    assert entry is not None, "Migration 0001 must exist"
    sql = entry.sql_text
    cur = db_connection.cursor()
    cur.execute(sql)
    db_connection.commit()
    return sql


@pytest.fixture
def cursor(db_connection, applied_migration):
    """Fresh cursor with migration already applied."""
    cur = db_connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    yield cur
    cur.close()


# ── Helpers ──────────────────────────────────────────────────────────────────


def _get_tables(cursor) -> list[str]:
    """List all tables in the toji_active schema."""
    cursor.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'toji_active' ORDER BY table_name"
    )
    return [row["table_name"] for row in cursor.fetchall()]


def _get_columns(cursor, table: str) -> list[dict]:
    """Get column info for a table in toji_active."""
    cursor.execute(
        "SELECT column_name, data_type, is_nullable, column_default "
        "FROM information_schema.columns "
        "WHERE table_schema = 'toji_active' AND table_name = %s "
        "ORDER BY ordinal_position",
        (table,),
    )
    return [dict(row) for row in cursor.fetchall()]


def _get_primary_keys(cursor, table: str) -> list[str]:
    """Get PK columns for a table."""
    cursor.execute(
        """
        SELECT kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        WHERE tc.table_schema = 'toji_active'
            AND tc.table_name = %s
            AND tc.constraint_type = 'PRIMARY KEY'
        ORDER BY kcu.ordinal_position
        """,
        (table,),
    )
    return [row["column_name"] for row in cursor.fetchall()]


def _get_foreign_keys(cursor, table: str) -> list[dict]:
    """Get FK info for a table."""
    cursor.execute(
        """
        SELECT
            kcu.column_name,
            ccu.table_name AS foreign_table,
            ccu.column_name AS foreign_column
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu
            ON tc.constraint_name = ccu.constraint_name
            AND tc.table_schema = ccu.table_schema
        WHERE tc.table_schema = 'toji_active'
            AND tc.table_name = %s
            AND tc.constraint_type = 'FOREIGN KEY'
        """,
        (table,),
    )
    return [dict(row) for row in cursor.fetchall()]


def _get_unique_constraints(cursor, table: str) -> list[str]:
    """Get unique constraint names for a table (includes unique indexes)."""
    cursor.execute(
        """
        SELECT indexname FROM pg_indexes
        WHERE schemaname = 'toji_active' AND tablename = %s
            AND indexdef ILIKE '%%UNIQUE%%'
        """,
        (table,),
    )
    return [row["indexname"] for row in cursor.fetchall()]


def _get_indexes(cursor, table: str) -> list[dict]:
    """Get all indexes for a table."""
    cursor.execute(
        """
        SELECT indexname, indexdef FROM pg_indexes
        WHERE schemaname = 'toji_active' AND tablename = %s
        ORDER BY indexname
        """,
        (table,),
    )
    return [dict(row) for row in cursor.fetchall()]


def _get_check_constraints(cursor, table: str) -> list[dict]:
    """Get CHECK constraints for a table."""
    cursor.execute(
        """
        SELECT conname, pg_get_constraintdef(oid) AS definition
        FROM pg_constraint
        WHERE connamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'toji_active')
            AND conrelid = (
                SELECT oid FROM pg_class
                WHERE relname = %s
                    AND relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'toji_active')
            )
            AND contype = 'c'
        """,
        (table,),
    )
    return [dict(row) for row in cursor.fetchall()]


# ── 1. Schema existence ─────────────────────────────────────────────────────


class TestSchemaExists:
    def test_toji_active_schema_exists(self, cursor) -> None:
        cursor.execute(
            "SELECT schema_name FROM information_schema.schemata "
            "WHERE schema_name = 'toji_active'"
        )
        result = cursor.fetchone()
        assert result is not None
        assert result["schema_name"] == "toji_active"


# ── 2. Table inspection ─────────────────────────────────────────────────────


class TestTables:
    def test_all_required_tables_exist(self, cursor) -> None:
        tables = set(_get_tables(cursor))
        for table in REQUIRED_TABLES:
            assert table in tables, f"Table '{table}' missing from toji_active"

    def test_exactly_16_tables(self, cursor) -> None:
        tables = _get_tables(cursor)
        assert len(tables) == 16, f"Expected 16 tables, got {len(tables)}: {tables}"


# ── 3. Column inspection ────────────────────────────────────────────────────


class TestColumns:
    @pytest.mark.parametrize(
        "table,expected_columns",
        [
            (
                "execution_requests",
                ["request_id", "account_id", "strategy_id", "symbol", "side",
                 "quantity", "order_type", "limit_price", "stop_price",
                 "time_in_force", "urgency", "metadata", "created_at",
                 "correlation_id"],
            ),
            (
                "orders",
                ["order_id", "intent_id", "decision_id", "account_id",
                 "exchange_order_id", "symbol", "side", "quantity",
                 "filled_quantity", "order_type", "limit_price", "stop_price",
                 "time_in_force", "status", "venue", "submitted_at",
                 "acknowledged_at", "completed_at", "metadata", "version",
                 "created_at", "updated_at"],
            ),
            (
                "fills",
                ["fill_id", "order_id", "account_id", "exchange_fill_id",
                 "symbol", "side", "quantity", "price", "commission",
                 "commission_asset", "liquidity", "venue", "filled_at",
                 "metadata", "created_at"],
            ),
            (
                "positions",
                ["position_id", "account_id", "symbol", "side", "quantity",
                 "average_entry_price", "realized_pnl", "unrealized_pnl",
                 "cost_basis", "market_value", "metadata", "version",
                 "opened_at", "updated_at"],
            ),
            (
                "oms_state",
                ["oms_state_id", "account_id", "status", "open_order_count",
                 "pending_fills", "last_heartbeat", "state_data", "version",
                 "created_at", "updated_at"],
            ),
            (
                "ledger_entries",
                ["entry_id", "account_id", "ledger_type", "entry_type",
                 "amount", "currency", "balance_after", "reference_type",
                 "reference_id", "description", "metadata", "created_at"],
            ),
            (
                "outbox_messages",
                ["message_id", "account_id", "topic", "event_type",
                 "payload", "status", "retry_count", "max_retries",
                 "last_error", "correlation_id", "created_at", "updated_at",
                 "sent_at"],
            ),
        ],
    )
    def test_table_has_expected_columns(
        self, cursor, table: str, expected_columns: list[str]
    ) -> None:
        columns = _get_columns(cursor, table)
        column_names = {c["column_name"] for c in columns}
        for col in expected_columns:
            assert col in column_names, (
                f"Column '{col}' missing from {table}. "
                f"Found: {sorted(column_names)}"
            )

    def test_all_timestamps_are_timestamptz(self, cursor) -> None:
        """Every column ending in _at should be timestamp with time zone."""
        for table in REQUIRED_TABLES:
            columns = _get_columns(cursor, table)
            for col in columns:
                if col["column_name"].endswith("_at"):
                    assert col["data_type"] == "timestamp with time zone", (
                        f"{table}.{col['column_name']} is {col['data_type']}, "
                        "expected 'timestamp with time zone'"
                    )

    def test_uuid_primary_key_type(self, cursor) -> None:
        """All primary key columns should be UUID type."""
        for table in REQUIRED_TABLES:
            pk_cols = _get_primary_keys(cursor, table)
            columns = _get_columns(cursor, table)
            col_map = {c["column_name"]: c for c in columns}
            for pk in pk_cols:
                assert col_map[pk]["data_type"] == "uuid", (
                    f"{table}.{pk} PK is {col_map[pk]['data_type']}, expected uuid"
                )


# ── 4. Primary keys ─────────────────────────────────────────────────────────


class TestPrimaryKeys:
    @pytest.mark.parametrize(
        "table,expected_pk",
        [
            ("schema_version", ["id"]),
            ("execution_requests", ["request_id"]),
            ("order_intents", ["intent_id"]),
            ("routing_decisions", ["decision_id"]),
            ("orders", ["order_id"]),
            ("fills", ["fill_id"]),
            ("execution_results", ["result_id"]),
            ("execution_metrics", ["metric_id"]),
            ("execution_journal", ["entry_id"]),
            ("audit_records", ["audit_id"]),
            ("oms_state", ["oms_state_id"]),
            ("positions", ["position_id"]),
            ("position_updates", ["update_id"]),
            ("portfolio_snapshots", ["snapshot_id"]),
            ("ledger_entries", ["entry_id"]),
            ("outbox_messages", ["message_id"]),
        ],
    )
    def test_primary_key(self, cursor, table: str, expected_pk: list[str]) -> None:
        pks = _get_primary_keys(cursor, table)
        assert pks == expected_pk, f"{table} PKs: {pks}, expected: {expected_pk}"


# ── 5. Foreign keys ─────────────────────────────────────────────────────────


class TestForeignKeys:
    @pytest.mark.parametrize(
        "table,column,ref_table,ref_column",
        [
            ("order_intents", "request_id", "execution_requests", "request_id"),
            ("routing_decisions", "intent_id", "order_intents", "intent_id"),
            ("orders", "intent_id", "order_intents", "intent_id"),
            ("orders", "decision_id", "routing_decisions", "decision_id"),
            ("fills", "order_id", "orders", "order_id"),
            ("execution_results", "request_id", "execution_requests", "request_id"),
            ("execution_metrics", "request_id", "execution_requests", "request_id"),
            ("position_updates", "position_id", "positions", "position_id"),
            ("position_updates", "fill_id", "fills", "fill_id"),
        ],
    )
    def test_foreign_key(
        self, cursor, table: str, column: str, ref_table: str, ref_column: str
    ) -> None:
        fks = _get_foreign_keys(cursor, table)
        match = [
            fk for fk in fks
            if fk["column_name"] == column
            and fk["foreign_table"] == ref_table
            and fk["foreign_column"] == ref_column
        ]
        assert len(match) >= 1, (
            f"FK {table}.{column} -> {ref_table}.{ref_column} not found. "
            f"Found: {fks}"
        )


# ── 6. Unique constraints ───────────────────────────────────────────────────


class TestUniqueConstraints:
    def test_schema_version_unique(self, cursor) -> None:
        uniq = _get_unique_constraints(cursor, "schema_version")
        assert any("uq_schema_version_version" in u for u in uniq)

    def test_oms_state_active_account_unique(self, cursor) -> None:
        uniq = _get_unique_constraints(cursor, "oms_state")
        assert any("uq_oms_state_active_account" in u for u in uniq)

    def test_positions_account_symbol_unique(self, cursor) -> None:
        uniq = _get_unique_constraints(cursor, "positions")
        assert any("uq_positions_account_symbol" in u for u in uniq)


# ── 7. Indexes ───────────────────────────────────────────────────────────────


class TestIndexes:
    @pytest.mark.parametrize(
        "table,index_name",
        [
            ("execution_requests", "idx_execution_requests_account_id"),
            ("execution_requests", "idx_execution_requests_symbol"),
            ("execution_requests", "idx_execution_requests_created_at"),
            ("orders", "idx_orders_account_id"),
            ("orders", "idx_orders_status"),
            ("orders", "idx_orders_symbol"),
            ("fills", "idx_fills_order_id"),
            ("fills", "idx_fills_account_id"),
            ("positions", "idx_positions_account_id"),
            ("positions", "idx_positions_symbol"),
            ("audit_records", "idx_audit_records_account_id"),
            ("audit_records", "idx_audit_records_created_at"),
            ("ledger_entries", "idx_ledger_entries_account_id"),
            ("outbox_messages", "idx_outbox_messages_status"),
            ("outbox_messages", "idx_outbox_pending"),
            ("portfolio_snapshots", "idx_portfolio_snapshots_account_id"),
        ],
    )
    def test_index_exists(self, cursor, table: str, index_name: str) -> None:
        indexes = _get_indexes(cursor, table)
        idx_names = [i["indexname"] for i in indexes]
        assert index_name in idx_names, (
            f"Index '{index_name}' not found on {table}. Found: {idx_names}"
        )

    def test_partial_index_outbox_pending(self, cursor) -> None:
        indexes = _get_indexes(cursor, "outbox_messages")
        pending = [i for i in indexes if i["indexname"] == "idx_outbox_pending"]
        assert len(pending) == 1
        assert "WHERE" in pending[0]["indexdef"]


# ── 8. CHECK constraints ────────────────────────────────────────────────────


class TestCheckConstraints:
    def test_orders_version_positive(self, cursor) -> None:
        checks = _get_check_constraints(cursor, "orders")
        defs = " ".join(c["definition"] for c in checks)
        assert "version" in defs and "> 0" in defs

    def test_orders_side_check(self, cursor) -> None:
        checks = _get_check_constraints(cursor, "orders")
        defs = " ".join(c["definition"] for c in checks)
        assert "BUY" in defs
        assert "SELL" in defs

    def test_orders_status_check(self, cursor) -> None:
        checks = _get_check_constraints(cursor, "orders")
        defs = " ".join(c["definition"] for c in checks)
        assert "PENDING" in defs
        assert "FILLED" in defs

    def test_fills_quantity_positive(self, cursor) -> None:
        checks = _get_check_constraints(cursor, "fills")
        defs = " ".join(c["definition"] for c in checks)
        assert "quantity" in defs and "> " in defs

    def test_ledger_type_check(self, cursor) -> None:
        checks = _get_check_constraints(cursor, "ledger_entries")
        defs = " ".join(c["definition"] for c in checks)
        assert "DEBIT" in defs
        assert "CREDIT" in defs

    def test_oms_state_status_check(self, cursor) -> None:
        checks = _get_check_constraints(cursor, "oms_state")
        defs = " ".join(c["definition"] for c in checks)
        assert "INITIALIZING" in defs
        assert "READY" in defs

    def test_positions_version_positive(self, cursor) -> None:
        checks = _get_check_constraints(cursor, "positions")
        defs = " ".join(c["definition"] for c in checks)
        assert "version" in defs and "> 0" in defs


# ── 9. schema_version record ────────────────────────────────────────────────


class TestSchemaVersionRecord:
    def test_schema_version_row_exists(self, cursor) -> None:
        cursor.execute(
            "SELECT version, name, component FROM toji_active.schema_version "
            "WHERE version = '0001'"
        )
        row = cursor.fetchone()
        assert row is not None
        assert row["version"] == "0001"
        assert row["name"] == "active_authority_foundation"
        assert row["component"] == "active_authority"


# ── 10. Research schema isolation ────────────────────────────────────────────


class TestResearchSchemaIsolation:
    def test_public_schema_not_modified(self, cursor) -> None:
        """Verify no toji_active tables leaked into the public schema."""
        cursor.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' "
            "AND table_name IN %s",
            (tuple(REQUIRED_TABLES),),
        )
        leaked = [row["table_name"] for row in cursor.fetchall()]
        assert leaked == [], (
            f"Tables leaked into public schema: {leaked}"
        )


# ── 11. Clean teardown ──────────────────────────────────────────────────────


class TestCleanTeardown:
    def test_schema_can_be_dropped(self, db_connection, applied_migration) -> None:
        """Verify the schema can be cleanly removed from the disposable DB."""
        cur = db_connection.cursor()
        cur.execute("DROP SCHEMA IF EXISTS toji_active CASCADE")
        db_connection.commit()

        # Verify it's gone
        cur.execute(
            "SELECT schema_name FROM information_schema.schemata "
            "WHERE schema_name = 'toji_active'"
        )
        assert cur.fetchone() is None

        # Re-apply for any subsequent tests
        manifest = SchemaManifest()
        entry = manifest.get_version("0001")
        assert entry is not None
        cur.execute(entry.sql_text)
        db_connection.commit()
        cur.close()
