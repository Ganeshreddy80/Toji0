"""Offline contract tests for the toji_active schema manifest.

These tests validate migration file structure, checksums, constraints,
indexes, security, research-table isolation, idempotency identities,
account-isolation design, append-only declarations, outbox semantics,
and CHECK constraints — all without a database connection.

Skill applied: specification-first development; security review.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from toji_platform.persistence.schema import (
    CHECKSUM_SENTINEL,
    COMPONENT,
    REQUIRED_TABLES,
    SCHEMA_NAME,
    ChecksumMismatchError,
    DuplicateVersionError,
    MigrationEntry,
    SchemaManifest,
)

# ── Helpers ───────────────────────────────────────────────────────────────────


def strip_comments(sql: str) -> str:
    return "\n".join(
        line for line in sql.splitlines()
        if not line.strip().startswith("--")
    )


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def manifest() -> SchemaManifest:
    m = SchemaManifest()
    # trigger load
    _ = m.entries
    return m


@pytest.fixture(scope="session")
def migration_entry(manifest: SchemaManifest) -> MigrationEntry:
    entry = manifest.get_version("0001")
    assert entry is not None, "Migration 0001 must exist"
    return entry


@pytest.fixture(scope="session")
def migration_sql(migration_entry: MigrationEntry) -> str:
    return migration_entry.sql_text


@pytest.fixture(scope="session")
def migration_sql_no_comments(migration_sql: str) -> str:
    return strip_comments(migration_sql)


# ── 1. Manifest identity ──────────────────────────────────────────────────────


class TestManifestIdentity:
    def test_schema_name(self, manifest: SchemaManifest) -> None:
        assert manifest.schema_name == "toji_active"

    def test_component(self, manifest: SchemaManifest) -> None:
        assert manifest.component == COMPONENT

    def test_schema_name_constant(self) -> None:
        assert SCHEMA_NAME == "toji_active"

    def test_at_least_one_migration(self, manifest: SchemaManifest) -> None:
        assert len(manifest.entries) >= 1

    def test_version_0001_exists(self, manifest: SchemaManifest) -> None:
        assert manifest.get_version("0001") is not None

    def test_migration_name(self, migration_entry: MigrationEntry) -> None:
        assert "foundation" in migration_entry.name.lower()

    def test_checksum_is_sha256_hex(self, migration_entry: MigrationEntry) -> None:
        checksum = migration_entry.checksum
        assert len(checksum) == 64
        assert re.fullmatch(r"[0-9a-f]{64}", checksum), "Must be lowercase hex SHA-256"

    def test_checksum_is_deterministic(self, migration_entry: MigrationEntry) -> None:
        """Loading the same file twice yields the same checksum."""
        m2 = SchemaManifest()
        entry2 = m2.get_version("0001")
        assert entry2 is not None
        assert entry2.checksum == migration_entry.checksum

    def test_no_duplicate_versions(self, manifest: SchemaManifest) -> None:
        violations = manifest.validate_no_duplicate_versions()
        assert violations == [], f"Duplicate versions: {violations}"

    def test_sql_path_exists(self, migration_entry: MigrationEntry) -> None:
        assert migration_entry.sql_path.exists()


# ── 2. Checksum policy ────────────────────────────────────────────────────────


class TestChecksumPolicy:
    def test_no_old_placeholder(self, manifest: SchemaManifest) -> None:
        """The old __CHECKSUM_PLACEHOLDER__ must not appear."""
        violations = manifest.validate_no_placeholder_checksum()
        assert violations == [], f"Old placeholder found: {violations}"

    def test_sentinel_in_sql(self, migration_sql: str) -> None:
        """__CHECKSUM_SELF__ sentinel must be present for runner to replace."""
        assert CHECKSUM_SENTINEL in migration_sql, (
            f"Migration SQL must contain {CHECKSUM_SENTINEL!r} for runner to "
            "insert the real checksum into schema_version"
        )

    def test_sql_for_apply_replaces_sentinel(
        self, migration_entry: MigrationEntry
    ) -> None:
        applied = migration_entry.sql_for_apply()
        assert CHECKSUM_SENTINEL not in applied
        assert migration_entry.checksum in applied

    def test_checksum_mismatch_error_attributes(self) -> None:
        err = ChecksumMismatchError(
            version="0001", expected="aabbcc", found="112233"
        )
        assert err.version == "0001"
        assert err.expected == "aabbcc"
        assert err.found == "112233"
        assert "0001" in str(err)
        assert "aabbcc" in str(err)
        assert "112233" in str(err)

    def test_duplicate_version_error_attributes(self) -> None:
        err = DuplicateVersionError("0001")
        assert err.version == "0001"
        assert "0001" in str(err)

    def test_checksum_mismatch_error_is_migration_error(self) -> None:
        from toji_platform.persistence.schema import MigrationError
        err = ChecksumMismatchError("0001", "a", "b")
        assert isinstance(err, MigrationError)

    def test_duplicate_version_is_migration_error(self) -> None:
        from toji_platform.persistence.schema import MigrationError
        err = DuplicateVersionError("0001")
        assert isinstance(err, MigrationError)


# ── 3. Required tables ────────────────────────────────────────────────────────


class TestRequiredTables:
    def test_table_count(self) -> None:
        assert len(REQUIRED_TABLES) == 16

    @pytest.mark.parametrize("table", REQUIRED_TABLES)
    def test_table_in_migration(
        self, table: str, migration_sql: str
    ) -> None:
        assert f"toji_active.{table}" in migration_sql, (
            f"Expected table toji_active.{table} not found in migration SQL"
        )


# ── 4. Required columns ───────────────────────────────────────────────────────


class TestRequiredColumns:
    @pytest.mark.parametrize("col", [
        "request_id", "account_id", "strategy_id", "idempotency_key",
        "symbol", "side", "quantity", "order_type", "created_at",
    ])
    def test_execution_requests_columns(
        self, col: str, migration_sql: str
    ) -> None:
        assert col in migration_sql

    @pytest.mark.parametrize("col", [
        "intent_id", "account_id", "request_id", "symbol", "side", "quantity",
    ])
    def test_order_intents_columns(
        self, col: str, migration_sql: str
    ) -> None:
        assert col in migration_sql

    @pytest.mark.parametrize("col", [
        "order_id", "account_id", "intent_id", "decision_id",
        "filled_quantity", "status", "version",
    ])
    def test_orders_columns(self, col: str, migration_sql: str) -> None:
        assert col in migration_sql

    @pytest.mark.parametrize("col", [
        "fill_id", "account_id", "order_id", "exchange_fill_id",
        "quantity", "price", "commission", "filled_at",
    ])
    def test_fills_columns(self, col: str, migration_sql: str) -> None:
        assert col in migration_sql

    @pytest.mark.parametrize("col", [
        "position_id", "account_id", "symbol", "side", "quantity",
        "average_entry_price", "version", "updated_at",
    ])
    def test_positions_columns(self, col: str, migration_sql: str) -> None:
        assert col in migration_sql

    @pytest.mark.parametrize("col", [
        "entry_id", "account_id", "ledger_type", "amount",
        "balance_after", "reference_idempotency_key",
    ])
    def test_ledger_entries_columns(
        self, col: str, migration_sql: str
    ) -> None:
        assert col in migration_sql

    @pytest.mark.parametrize("col", [
        "message_id", "account_id", "event_id", "aggregate_type",
        "aggregate_id", "topic", "event_type", "payload", "status",
        "retry_count", "max_retries", "available_at", "lease_expires_at",
        "leased_by", "version",
    ])
    def test_outbox_messages_columns(
        self, col: str, migration_sql: str
    ) -> None:
        assert col in migration_sql

    @pytest.mark.parametrize("col", [
        "snapshot_id", "total_equity", "cash_balance",
        "total_market_value", "positions_data", "position_count",
    ])
    def test_portfolio_snapshots_columns(
        self, col: str, migration_sql: str
    ) -> None:
        assert col in migration_sql

    @pytest.mark.parametrize("col", [
        "update_id", "position_id", "fill_id", "apply_key",
        "update_type", "quantity_change", "price",
    ])
    def test_position_updates_columns(
        self, col: str, migration_sql: str
    ) -> None:
        assert col in migration_sql


# ── 5. CHECK constraints ──────────────────────────────────────────────────────


class TestConstraints:
    def test_side_check_buy_sell(self, migration_sql: str) -> None:
        assert "side IN ('BUY', 'SELL')" in migration_sql

    def test_order_status_check(self, migration_sql: str) -> None:
        for status in ("PENDING", "SUBMITTED", "FILLED", "CANCELLED", "REJECTED"):
            assert status in migration_sql

    def test_version_check_positive(self, migration_sql: str) -> None:
        assert "version > 0" in migration_sql

    def test_quantity_check_positive(self, migration_sql: str) -> None:
        assert "quantity > 0" in migration_sql

    def test_filled_quantity_lte_quantity(self, migration_sql: str) -> None:
        """filled_quantity <= quantity constraint."""
        assert "filled_quantity <= quantity" in migration_sql

    def test_commission_nonneg(self, migration_sql: str) -> None:
        assert "commission >= 0" in migration_sql

    def test_ledger_type_check(self, migration_sql: str) -> None:
        assert "ledger_type IN ('DEBIT', 'CREDIT')" in migration_sql

    def test_ledger_amount_nonzero(self, migration_sql: str) -> None:
        assert "amount != 0" in migration_sql

    def test_severity_check(self, migration_sql: str) -> None:
        assert "INFO" in migration_sql and "ERROR" in migration_sql

    def test_oms_status_check(self, migration_sql: str) -> None:
        for s in ("INITIALIZING", "READY", "ACTIVE", "PAUSED", "DRAINING"):
            assert s in migration_sql

    def test_outbox_status_check(self, migration_sql: str) -> None:
        assert "'PENDING', 'PROCESSING', 'SENT', 'FAILED', 'DEAD_LETTER'" in migration_sql

    def test_max_retries_nonneg(self, migration_sql: str) -> None:
        assert "max_retries >= 0" in migration_sql

    def test_retry_count_nonneg(self, migration_sql: str) -> None:
        assert "retry_count >= 0" in migration_sql

    def test_position_count_nonneg(self, migration_sql: str) -> None:
        assert "position_count >= 0" in migration_sql

    def test_open_order_count_nonneg(self, migration_sql: str) -> None:
        assert "open_order_count >= 0" in migration_sql

    def test_position_quantity_nonneg(self, migration_sql: str) -> None:
        # positions.quantity >= 0
        assert "quantity >= 0" in migration_sql

    def test_time_in_force_check(self, migration_sql: str) -> None:
        assert "time_in_force IN ('GTC', 'IOC', 'FOK', 'DAY')" in migration_sql

    def test_order_type_check(self, migration_sql: str) -> None:
        assert "order_type IN ('MARKET', 'LIMIT', 'STOP', 'STOP_LIMIT')" in migration_sql

    def test_conditional_limit_price_check(self, migration_sql: str) -> None:
        """LIMIT/STOP_LIMIT orders require limit_price."""
        assert "order_type IN ('LIMIT', 'STOP_LIMIT') AND limit_price IS NOT NULL" in migration_sql

    def test_conditional_stop_price_check(self, migration_sql: str) -> None:
        """STOP/STOP_LIMIT orders require stop_price."""
        assert "order_type IN ('STOP', 'STOP_LIMIT') AND stop_price IS NOT NULL" in migration_sql

    def test_price_positive_in_fills(self, migration_sql: str) -> None:
        assert "price > 0" in migration_sql


# ── 6. Unique constraints (idempotency) ───────────────────────────────────────


class TestUniqueConstraints:
    def test_schema_version_unique(self, migration_sql: str) -> None:
        assert "uq_schema_version_version" in migration_sql

    def test_oms_state_active_account_unique(self, migration_sql: str) -> None:
        assert "uq_oms_state_active_account" in migration_sql

    def test_positions_account_symbol_unique(self, migration_sql: str) -> None:
        assert "uq_positions_account_symbol" in migration_sql

    def test_execution_requests_idempotency_key(self, migration_sql: str) -> None:
        assert "uq_execution_requests_idempotency" in migration_sql

    def test_orders_exchange_order_id_unique(self, migration_sql: str) -> None:
        assert "uq_orders_exchange_id_account_venue" in migration_sql

    def test_fills_exchange_fill_id_unique(self, migration_sql: str) -> None:
        assert "uq_fills_exchange_fill_id" in migration_sql

    def test_position_updates_apply_key_unique(self, migration_sql: str) -> None:
        assert "uq_position_updates_apply_key" in migration_sql

    def test_ledger_ref_idempotency_unique(self, migration_sql: str) -> None:
        assert "uq_ledger_entries_ref_idempotency" in migration_sql

    def test_outbox_event_id_unique(self, migration_sql: str) -> None:
        assert "uq_outbox_messages_event_id" in migration_sql


# ── 7. Account isolation — composite FK keys ──────────────────────────────────


class TestAccountIsolation:
    def test_composite_fk_execution_requests(self, migration_sql: str) -> None:
        """order_intents references execution_requests via (account_id, request_id)."""
        assert "uq_execution_requests_account_request" in migration_sql

    def test_composite_fk_order_intents(self, migration_sql: str) -> None:
        """routing_decisions references order_intents via (account_id, intent_id)."""
        assert "uq_order_intents_account_intent" in migration_sql

    def test_composite_fk_routing_decisions(self, migration_sql: str) -> None:
        """orders references routing_decisions via (account_id, decision_id)."""
        assert "uq_routing_decisions_account_decision" in migration_sql

    def test_composite_fk_orders(self, migration_sql: str) -> None:
        """fills references orders via (account_id, order_id)."""
        assert "uq_orders_account_order" in migration_sql

    def test_composite_fk_fills(self, migration_sql: str) -> None:
        """position_updates references fills via (account_id, fill_id)."""
        assert "uq_fills_account_fill" in migration_sql

    def test_composite_fk_positions(self, migration_sql: str) -> None:
        """position_updates references positions via (account_id, position_id)."""
        assert "uq_positions_account_position" in migration_sql

    def test_composite_fk_syntax_intent(self, migration_sql: str) -> None:
        """Composite FK declaration present for order_intents → exec_requests."""
        assert "FOREIGN KEY (account_id, request_id)" in migration_sql

    def test_composite_fk_syntax_routing(self, migration_sql: str) -> None:
        """Composite FK declaration for routing_decisions → order_intents."""
        assert "FOREIGN KEY (account_id, intent_id)" in migration_sql

    def test_composite_fk_syntax_orders(self, migration_sql: str) -> None:
        """Composite FK declarations for orders → intents and decisions."""
        count = migration_sql.count("FOREIGN KEY (account_id, intent_id)")
        assert count >= 1

    def test_composite_fk_syntax_fills(self, migration_sql: str) -> None:
        assert "FOREIGN KEY (account_id, order_id)" in migration_sql

    def test_composite_fk_syntax_position_updates(self, migration_sql: str) -> None:
        assert "FOREIGN KEY (account_id, position_id)" in migration_sql

    def test_composite_fk_fills_for_position_updates(self, migration_sql: str) -> None:
        assert "FOREIGN KEY (account_id, fill_id)" in migration_sql


# ── 8. Append-only protection ─────────────────────────────────────────────────


APPEND_ONLY_TABLES = (
    "schema_version",
    "execution_requests",
    "order_intents",
    "routing_decisions",
    "fills",
    "execution_results",
    "execution_metrics",
    "execution_journal",
    "audit_records",
    "position_updates",
    "portfolio_snapshots",
    "ledger_entries",
)


class TestAppendOnly:
    @pytest.mark.parametrize("table", APPEND_ONLY_TABLES)
    def test_no_update_rule(self, table: str, migration_sql: str) -> None:
        assert f"{table}_no_update" in migration_sql, (
            f"Table {table} must have a no_update RULE for append-only protection"
        )

    @pytest.mark.parametrize("table", APPEND_ONLY_TABLES)
    def test_no_delete_rule(self, table: str, migration_sql: str) -> None:
        assert f"{table}_no_delete" in migration_sql, (
            f"Table {table} must have a no_delete RULE for append-only protection"
        )

    def test_rule_syntax_instead_nothing(self, migration_sql: str) -> None:
        """Rules must use DO INSTEAD NOTHING pattern."""
        assert "DO INSTEAD NOTHING" in migration_sql


# ── 9. Outbox semantics ───────────────────────────────────────────────────────


class TestOutboxSemantics:
    def test_event_id_column(self, migration_sql: str) -> None:
        assert "event_id" in migration_sql

    def test_aggregate_type_column(self, migration_sql: str) -> None:
        assert "aggregate_type" in migration_sql

    def test_aggregate_id_column(self, migration_sql: str) -> None:
        assert "aggregate_id" in migration_sql

    def test_available_at_column(self, migration_sql: str) -> None:
        assert "available_at" in migration_sql

    def test_lease_expires_at_column(self, migration_sql: str) -> None:
        assert "lease_expires_at" in migration_sql

    def test_leased_by_column(self, migration_sql: str) -> None:
        assert "leased_by" in migration_sql

    def test_version_column_for_cas(self, migration_sql: str) -> None:
        """Outbox has version column for compare-and-set."""
        assert "version" in migration_sql

    def test_worker_dispatch_index(self, migration_sql: str) -> None:
        assert "idx_outbox_pending" in migration_sql

    def test_lease_expiry_index(self, migration_sql: str) -> None:
        assert "idx_outbox_lease_expires" in migration_sql

    def test_event_dedup_unique(self, migration_sql: str) -> None:
        assert "uq_outbox_messages_event_id" in migration_sql

    def test_dead_letter_status(self, migration_sql: str) -> None:
        assert "DEAD_LETTER" in migration_sql

    def test_aggregate_index(self, migration_sql: str) -> None:
        assert "idx_outbox_messages_aggregate" in migration_sql


# ── 10. Indexes ───────────────────────────────────────────────────────────────


EXPECTED_INDEXES = [
    "idx_execution_requests_account_id",
    "idx_execution_requests_symbol",
    "idx_execution_requests_created_at",
    "idx_order_intents_account_id",
    "idx_routing_decisions_account_id",
    "idx_orders_account_id",
    "idx_orders_status",
    "idx_orders_symbol",
    "idx_orders_account_status",
    "idx_fills_order_id",
    "idx_fills_account_id",
    "idx_execution_results_account_id",
    "idx_execution_metrics_account_id",
    "idx_execution_journal_account_id",
    "idx_audit_records_account_id",
    "idx_audit_records_created_at",
    "idx_positions_account_id",
    "idx_positions_symbol",
    "idx_position_updates_account_id",
    "idx_position_updates_fill_id",
    "idx_portfolio_snapshots_account_id",
    "idx_ledger_entries_account_id",
    "idx_outbox_messages_status",
    "idx_outbox_pending",
    "idx_outbox_lease_expires",
]


class TestIndexes:
    @pytest.mark.parametrize("index", EXPECTED_INDEXES)
    def test_index_exists(self, index: str, migration_sql: str) -> None:
        assert index in migration_sql, f"Expected index {index!r} not found"

    def test_partial_index_outbox_pending(self, migration_sql: str) -> None:
        assert "WHERE status IN ('PENDING', 'FAILED')" in migration_sql

    def test_oms_state_partial_index(self, migration_sql: str) -> None:
        assert "WHERE status NOT IN ('STOPPED', 'ERROR')" in migration_sql


# ── 11. Security scans ────────────────────────────────────────────────────────


class TestSecurityScans:
    def test_no_secrets_violations(self, manifest: SchemaManifest) -> None:
        violations = manifest.validate_no_secrets()
        assert violations == [], f"Secret violations: {violations}"

    def test_no_aws_keys(self, migration_sql: str) -> None:
        assert not re.search(r"AKIA[0-9A-Z]{16}", migration_sql)

    def test_no_database_urls_with_credentials(self, migration_sql: str) -> None:
        sql = strip_comments(migration_sql)
        assert not re.search(
            r"(?:postgres|postgresql)://[^\s]+:[^\s]+@", sql, re.IGNORECASE
        )

    def test_no_hardcoded_password(self, migration_sql: str) -> None:
        sql = strip_comments(migration_sql)
        assert not re.search(r"password\s*=\s*['\"]", sql, re.IGNORECASE)


# ── 12. Research table isolation ──────────────────────────────────────────────


class TestResearchTableIsolation:
    def test_no_research_tables_violations(self, manifest: SchemaManifest) -> None:
        violations = manifest.validate_no_research_tables()
        assert violations == [], f"Research table violations: {violations}"

    def test_no_alter_on_research_tables(self, migration_sql: str) -> None:
        research_names = [
            "trade_ledger", "trade_journals", "portfolios",
            "strategies", "experiments",
        ]
        for tbl in research_names:
            assert not re.search(
                rf"ALTER\s+TABLE\s+(?:public\.)?{re.escape(tbl)}\b",
                migration_sql, re.IGNORECASE
            ), f"Must not ALTER research table: {tbl}"

    def test_no_drop_on_research_tables(self, migration_sql: str) -> None:
        research_names = [
            "trade_ledger", "trade_journals", "portfolios",
            "strategies", "experiments",
        ]
        for tbl in research_names:
            assert not re.search(
                rf"DROP\s+TABLE\s+(?:(?:IF\s+EXISTS)\s+)?(?:public\.)?{re.escape(tbl)}\b",
                migration_sql, re.IGNORECASE
            ), f"Must not DROP research table: {tbl}"


# ── 13. Migration structure ───────────────────────────────────────────────────


class TestMigrationStructure:
    def test_creates_schema(self, migration_sql: str) -> None:
        assert "CREATE SCHEMA IF NOT EXISTS toji_active" in migration_sql

    def test_uses_transaction(self, migration_sql: str) -> None:
        assert "BEGIN;" in migration_sql
        assert "COMMIT;" in migration_sql

    def test_uses_uuid_primary_keys(self, migration_sql: str) -> None:
        assert "UUID" in migration_sql
        assert "gen_random_uuid()" in migration_sql

    def test_uses_timestamptz(self, migration_sql_no_comments: str) -> None:
        bare = re.findall(r"\bTIMESTAMP\b(?!TZ)", migration_sql_no_comments, re.IGNORECASE)
        assert bare == [], (
            f"Found bare TIMESTAMP (should be TIMESTAMPTZ): {bare}"
        )

    def test_schema_version_sentinel(self, migration_sql: str) -> None:
        """Sentinel must be present (not old __CHECKSUM_PLACEHOLDER__)."""
        assert "__CHECKSUM_SELF__" in migration_sql
        assert "__CHECKSUM_PLACEHOLDER__" not in migration_sql

    def test_no_create_all(self, manifest: SchemaManifest) -> None:
        violations = manifest.validate_no_create_all()
        assert violations == []

    def test_no_drop_statements(self, migration_sql: str) -> None:
        sql = strip_comments(migration_sql)
        assert not re.search(r"\bDROP\s+TABLE\b", sql, re.IGNORECASE)

    def test_no_truncate_statements(self, migration_sql: str) -> None:
        assert not re.search(r"\bTRUNCATE\b", migration_sql, re.IGNORECASE)

    def test_no_grant_statements(self, migration_sql: str) -> None:
        assert not re.search(r"\bGRANT\b", migration_sql, re.IGNORECASE)

    def test_no_create_role(self, migration_sql: str) -> None:
        assert not re.search(r"\bCREATE\s+ROLE\b", migration_sql, re.IGNORECASE)

    def test_reset_search_path(self, migration_sql: str) -> None:
        assert "RESET search_path" in migration_sql
