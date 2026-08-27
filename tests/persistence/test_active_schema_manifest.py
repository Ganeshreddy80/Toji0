"""DATA-001-P0-03A — Offline schema manifest and migration contract tests.

These tests validate the schema manifest, migration integrity, and
contract compliance WITHOUT requiring a database connection.
"""

from __future__ import annotations

import re

import pytest

from toji_platform.persistence.schema import (
    COMPONENT,
    REQUIRED_TABLES,
    SCHEMA_NAME,
    MigrationEntry,
    SchemaManifest,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def manifest() -> SchemaManifest:
    """Fresh SchemaManifest instance."""
    return SchemaManifest()


@pytest.fixture
def migration_0001(manifest: SchemaManifest) -> MigrationEntry:
    """The 0001 foundation migration entry."""
    entry = manifest.get_version("0001")
    assert entry is not None, "Migration 0001 must exist"
    return entry


@pytest.fixture
def migration_sql(migration_0001: MigrationEntry) -> str:
    """Raw SQL text of the foundation migration."""
    return migration_0001.sql_text


# ── Schema Identity ─────────────────────────────────────────────────────────


class TestSchemaIdentity:
    """Verify the schema name and component are canonical."""

    def test_schema_name_is_toji_active(self, manifest: SchemaManifest) -> None:
        assert manifest.schema_name == "toji_active"

    def test_schema_name_constant(self) -> None:
        assert SCHEMA_NAME == "toji_active"

    def test_component_is_active_authority(self, manifest: SchemaManifest) -> None:
        assert manifest.component == "active_authority"

    def test_component_constant(self) -> None:
        assert COMPONENT == "active_authority"


# ── Migration Discovery ─────────────────────────────────────────────────────


class TestMigrationDiscovery:
    """Verify migration 0001 is discovered and well-formed."""

    def test_version_0001_exists(self, manifest: SchemaManifest) -> None:
        entry = manifest.get_version("0001")
        assert entry is not None

    def test_migration_name(self, migration_0001: MigrationEntry) -> None:
        assert migration_0001.name == "active_authority_foundation"

    def test_migration_component(self, migration_0001: MigrationEntry) -> None:
        assert migration_0001.component == "active_authority"

    def test_migration_sql_path_exists(self, migration_0001: MigrationEntry) -> None:
        assert migration_0001.sql_path.exists()

    def test_entries_not_empty(self, manifest: SchemaManifest) -> None:
        assert len(manifest.entries) >= 1


# ── Checksum Determinism ────────────────────────────────────────────────────


class TestChecksumDeterminism:
    """Verify checksums are deterministic across runs."""

    def test_checksum_is_deterministic(self) -> None:
        manifest_a = SchemaManifest()
        manifest_b = SchemaManifest()
        entry_a = manifest_a.get_version("0001")
        entry_b = manifest_b.get_version("0001")
        assert entry_a is not None
        assert entry_b is not None
        assert entry_a.checksum == entry_b.checksum

    def test_checksum_is_sha256_hex(self, migration_0001: MigrationEntry) -> None:
        assert re.fullmatch(r"[0-9a-f]{64}", migration_0001.checksum)

    def test_checksum_is_nonempty(self, migration_0001: MigrationEntry) -> None:
        assert len(migration_0001.checksum) == 64


# ── Required Tables ──────────────────────────────────────────────────────────


class TestRequiredTables:
    """Verify all 16 required tables appear in the migration SQL."""

    EXPECTED_TABLES = (
        "schema_version",
        "execution_requests",
        "order_intents",
        "routing_decisions",
        "orders",
        "fills",
        "execution_results",
        "execution_metrics",
        "execution_journal",
        "audit_records",
        "oms_state",
        "positions",
        "position_updates",
        "portfolio_snapshots",
        "ledger_entries",
        "outbox_messages",
    )

    def test_required_tables_constant_has_16(self) -> None:
        assert len(REQUIRED_TABLES) == 16

    def test_required_tables_match_expected(self) -> None:
        assert set(REQUIRED_TABLES) == set(self.EXPECTED_TABLES)

    @pytest.mark.parametrize("table_name", EXPECTED_TABLES)
    def test_table_in_migration_sql(
        self, migration_sql: str, table_name: str
    ) -> None:
        qualified = f"toji_active.{table_name}"
        assert qualified in migration_sql.lower(), (
            f"Table '{qualified}' not found in migration SQL"
        )

    def test_manifest_validate_required_tables(
        self, manifest: SchemaManifest
    ) -> None:
        missing = manifest.validate_required_tables()
        assert missing == [], f"Missing tables: {missing}"

    def test_create_table_count(self, migration_sql: str) -> None:
        """At least 16 CREATE TABLE statements."""
        count = len(re.findall(r"CREATE\s+TABLE", migration_sql, re.IGNORECASE))
        assert count >= 16, f"Expected >= 16 CREATE TABLE, got {count}"


# ── Required Columns ─────────────────────────────────────────────────────────


class TestRequiredColumns:
    """Spot-check critical columns exist in the migration."""

    @pytest.mark.parametrize(
        "column",
        [
            "request_id",
            "account_id",
            "strategy_id",
            "symbol",
            "side",
            "quantity",
            "order_type",
            "limit_price",
            "time_in_force",
            "correlation_id",
        ],
    )
    def test_execution_requests_columns(
        self, migration_sql: str, column: str
    ) -> None:
        assert column in migration_sql.lower()

    @pytest.mark.parametrize(
        "column",
        [
            "order_id",
            "exchange_order_id",
            "filled_quantity",
            "status",
            "venue",
            "version",
            "submitted_at",
        ],
    )
    def test_orders_columns(self, migration_sql: str, column: str) -> None:
        assert column in migration_sql.lower()

    @pytest.mark.parametrize(
        "column",
        ["fill_id", "price", "commission", "liquidity", "filled_at"],
    )
    def test_fills_columns(self, migration_sql: str, column: str) -> None:
        assert column in migration_sql.lower()

    @pytest.mark.parametrize(
        "column",
        ["position_id", "average_entry_price", "realized_pnl", "unrealized_pnl", "cost_basis"],
    )
    def test_positions_columns(self, migration_sql: str, column: str) -> None:
        assert column in migration_sql.lower()

    @pytest.mark.parametrize(
        "column",
        ["oms_state_id", "open_order_count", "pending_fills", "last_heartbeat"],
    )
    def test_oms_state_columns(self, migration_sql: str, column: str) -> None:
        assert column in migration_sql.lower()

    @pytest.mark.parametrize(
        "column",
        ["entry_id", "ledger_type", "entry_type", "amount", "balance_after"],
    )
    def test_ledger_entries_columns(self, migration_sql: str, column: str) -> None:
        assert column in migration_sql.lower()

    @pytest.mark.parametrize(
        "column",
        ["message_id", "topic", "event_type", "payload", "retry_count", "max_retries"],
    )
    def test_outbox_messages_columns(self, migration_sql: str, column: str) -> None:
        assert column in migration_sql.lower()

    @pytest.mark.parametrize(
        "column",
        ["snapshot_id", "total_equity", "cash_balance", "total_market_value", "positions_data"],
    )
    def test_portfolio_snapshots_columns(
        self, migration_sql: str, column: str
    ) -> None:
        assert column in migration_sql.lower()


# ── Constraints ──────────────────────────────────────────────────────────────


class TestConstraints:
    """Verify CHECK, UNIQUE, and FK constraints in migration SQL."""

    def test_side_check_buy_sell(self, migration_sql: str) -> None:
        assert re.search(
            r"CHECK\s*\(\s*side\s+IN\s*\(\s*'BUY'\s*,\s*'SELL'\s*\)",
            migration_sql,
            re.IGNORECASE,
        )

    def test_order_status_check(self, migration_sql: str) -> None:
        assert "'PENDING'" in migration_sql
        assert "'FILLED'" in migration_sql
        assert "'CANCELLED'" in migration_sql
        assert "'REJECTED'" in migration_sql

    def test_version_check_positive(self, migration_sql: str) -> None:
        assert re.search(
            r"CHECK\s*\(\s*version\s*>\s*0\s*\)", migration_sql, re.IGNORECASE
        )

    def test_quantity_check_positive(self, migration_sql: str) -> None:
        assert re.search(
            r"CHECK\s*\(\s*quantity\s*>\s*0\s*\)", migration_sql, re.IGNORECASE
        )

    def test_ledger_type_check(self, migration_sql: str) -> None:
        assert "'DEBIT'" in migration_sql
        assert "'CREDIT'" in migration_sql

    def test_severity_check(self, migration_sql: str) -> None:
        assert "'DEBUG'" in migration_sql
        assert "'INFO'" in migration_sql
        assert "'WARN'" in migration_sql
        assert "'ERROR'" in migration_sql
        assert "'CRITICAL'" in migration_sql

    def test_oms_status_check(self, migration_sql: str) -> None:
        assert "'INITIALIZING'" in migration_sql
        assert "'READY'" in migration_sql
        assert "'ACTIVE'" in migration_sql
        assert "'PAUSED'" in migration_sql

    def test_outbox_status_check(self, migration_sql: str) -> None:
        assert "'PROCESSING'" in migration_sql
        assert "'SENT'" in migration_sql
        assert "'DEAD_LETTER'" in migration_sql

    def test_foreign_key_references(self, migration_sql: str) -> None:
        assert "REFERENCES toji_active.execution_requests" in migration_sql
        assert "REFERENCES toji_active.order_intents" in migration_sql
        assert "REFERENCES toji_active.routing_decisions" in migration_sql
        assert "REFERENCES toji_active.orders" in migration_sql
        assert "REFERENCES toji_active.fills" in migration_sql
        assert "REFERENCES toji_active.positions" in migration_sql

    def test_unique_index_oms_active_account(self, migration_sql: str) -> None:
        assert re.search(
            r"CREATE\s+UNIQUE\s+INDEX\s+uq_oms_state_active_account",
            migration_sql,
            re.IGNORECASE,
        )

    def test_unique_index_positions_account_symbol(self, migration_sql: str) -> None:
        assert re.search(
            r"CREATE\s+UNIQUE\s+INDEX\s+uq_positions_account_symbol",
            migration_sql,
            re.IGNORECASE,
        )

    def test_unique_index_schema_version(self, migration_sql: str) -> None:
        assert re.search(
            r"CREATE\s+UNIQUE\s+INDEX\s+uq_schema_version_version",
            migration_sql,
            re.IGNORECASE,
        )


# ── Indexes ──────────────────────────────────────────────────────────────────


class TestIndexes:
    """Verify required indexes exist in the migration."""

    def test_index_count(self, migration_sql: str) -> None:
        """Expect a substantial number of indexes."""
        count = len(re.findall(r"CREATE\s+(?:UNIQUE\s+)?INDEX", migration_sql, re.IGNORECASE))
        # At minimum: each table needs at least one index
        assert count >= 16, f"Expected >= 16 indexes, got {count}"

    @pytest.mark.parametrize(
        "index_name",
        [
            "idx_execution_requests_account_id",
            "idx_execution_requests_symbol",
            "idx_orders_account_id",
            "idx_orders_status",
            "idx_orders_symbol",
            "idx_fills_order_id",
            "idx_fills_account_id",
            "idx_positions_account_id",
            "idx_positions_symbol",
            "idx_audit_records_account_id",
            "idx_audit_records_created_at",
            "idx_ledger_entries_account_id",
            "idx_outbox_messages_status",
            "idx_outbox_pending",
            "idx_portfolio_snapshots_account_id",
        ],
    )
    def test_index_exists(self, migration_sql: str, index_name: str) -> None:
        assert index_name in migration_sql.lower(), (
            f"Index '{index_name}' not found in migration SQL"
        )

    def test_partial_index_outbox_pending(self, migration_sql: str) -> None:
        """Outbox pending index should be a partial index."""
        assert re.search(
            r"idx_outbox_pending.*WHERE\s+status\s+IN",
            migration_sql,
            re.IGNORECASE | re.DOTALL,
        )


# ── Security Scans ───────────────────────────────────────────────────────────


class TestSecurityScans:
    """Verify migration SQL contains no secrets or unsafe patterns."""

    def test_no_secrets_in_migration(self, manifest: SchemaManifest) -> None:
        violations = manifest.validate_no_secrets()
        assert violations == [], f"Secret violations: {violations}"

    def test_no_password_literals(self, migration_sql: str) -> None:
        assert not re.search(
            r"password\s*=\s*['\"]", migration_sql, re.IGNORECASE
        )

    def test_no_aws_keys(self, migration_sql: str) -> None:
        assert not re.search(r"AKIA[0-9A-Z]{16}", migration_sql)
        assert "aws_access_key_id" not in migration_sql.lower()
        assert "aws_secret_access_key" not in migration_sql.lower()

    def test_no_database_urls(self, migration_sql: str) -> None:
        assert not re.search(
            r"(?:postgres|postgresql)://[^\s]+:[^\s]+@", migration_sql, re.IGNORECASE
        )

    def test_no_api_keys(self, migration_sql: str) -> None:
        assert not re.search(r"api_key\s*=", migration_sql, re.IGNORECASE)


# ── Research Table Isolation ─────────────────────────────────────────────────


class TestResearchTableIsolation:
    """Verify migration does not touch existing research-platform tables."""

    def test_no_research_tables_modified(self, manifest: SchemaManifest) -> None:
        violations = manifest.validate_no_research_tables()
        assert violations == [], f"Research table violations: {violations}"

    def test_no_alter_on_research_tables(self, migration_sql: str) -> None:
        research_tables = [
            "trade_ledger", "trade_journals", "daily_journals",
            "trade_statistics", "portfolios", "analytics",
            "strategies", "experiments",
        ]
        for table in research_tables:
            assert not re.search(
                rf"ALTER\s+TABLE\s+(?:public\.)?{re.escape(table)}\b",
                migration_sql,
                re.IGNORECASE,
            ), f"Migration ALTERs research table: {table}"

    def test_no_drop_on_research_tables(self, migration_sql: str) -> None:
        research_tables = [
            "trade_ledger", "trade_journals", "daily_journals",
            "trade_statistics", "portfolios", "analytics",
            "strategies", "experiments",
        ]
        for table in research_tables:
            assert not re.search(
                rf"DROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?(?:public\.)?{re.escape(table)}\b",
                migration_sql,
                re.IGNORECASE,
            ), f"Migration DROPs research table: {table}"


# ── No create_all() ─────────────────────────────────────────────────────────


class TestNoCreateAll:
    """Verify no create_all() usage in migrations."""

    def test_no_create_all_in_migration(self, manifest: SchemaManifest) -> None:
        violations = manifest.validate_no_create_all()
        assert violations == [], f"create_all violations: {violations}"

    def test_no_create_all_literal(self, migration_sql: str) -> None:
        assert "create_all" not in migration_sql.lower()


# ── Migration Structure ──────────────────────────────────────────────────────


class TestMigrationStructure:
    """Verify structural properties of the migration SQL."""

    def test_creates_schema(self, migration_sql: str) -> None:
        assert re.search(
            r"CREATE\s+SCHEMA\s+IF\s+NOT\s+EXISTS\s+toji_active",
            migration_sql,
            re.IGNORECASE,
        )

    def test_uses_transaction(self, migration_sql: str) -> None:
        assert "BEGIN;" in migration_sql
        assert "COMMIT;" in migration_sql

    def test_uses_uuid_primary_keys(self, migration_sql: str) -> None:
        """All tables should use UUID primary keys."""
        pk_matches = re.findall(
            r"(\w+)\s+UUID\s+PRIMARY\s+KEY", migration_sql, re.IGNORECASE
        )
        assert len(pk_matches) >= 16, (
            f"Expected >= 16 UUID PKs, found {len(pk_matches)}"
        )

    def test_uses_timestamptz(self, migration_sql: str) -> None:
        """All timestamp columns should be TIMESTAMPTZ, not TIMESTAMP."""
        # Strip SQL comments before checking
        sql_no_comments = "\n".join(
            line for line in migration_sql.splitlines()
            if not line.strip().startswith("--")
        )
        # Count bare TIMESTAMP (not TIMESTAMPTZ)
        bare = re.findall(r"\bTIMESTAMP\b(?!TZ)", sql_no_comments, re.IGNORECASE)
        assert len(bare) == 0, (
            f"Found {len(bare)} bare TIMESTAMP columns (should be TIMESTAMPTZ)"
        )

    def test_inserts_schema_version_record(self, migration_sql: str) -> None:
        assert re.search(
            r"INSERT\s+INTO\s+toji_active\.schema_version",
            migration_sql,
            re.IGNORECASE,
        )

    def test_no_drop_statements(self, migration_sql: str) -> None:
        """Foundation migration should not DROP anything."""
        drops = re.findall(
            r"DROP\s+(?:TABLE|SCHEMA|INDEX)", migration_sql, re.IGNORECASE
        )
        assert len(drops) == 0, f"Unexpected DROP statements: {drops}"

    def test_no_truncate_statements(self, migration_sql: str) -> None:
        assert "TRUNCATE" not in migration_sql.upper()

    def test_no_grant_statements(self, migration_sql: str) -> None:
        """No privilege grants in migration."""
        grants = re.findall(r"\bGRANT\b", migration_sql, re.IGNORECASE)
        assert len(grants) == 0, f"Unexpected GRANT statements found"

    def test_no_create_role(self, migration_sql: str) -> None:
        assert not re.search(
            r"CREATE\s+ROLE", migration_sql, re.IGNORECASE
        )
