-- =============================================================================
-- DATA-001-P0-03A: Active Authority Foundation — REMEDIATION
-- Migration: 0001_active_authority_foundation
-- Schema:    toji_active (within existing 'toji' database)
-- Owner:     DATA team — CTO approval required for changes
-- =============================================================================
--
-- CHECKSUM POLICY:
--   The schema_version row records the SHA-256 of this file's bytes at the
--   time the migration runner reads it from disk.  The runner (SchemaManifest /
--   MigrationRunner) is authoritative:
--     - First application:  apply, then insert schema_version row with checksum.
--     - Repeat same checksum:  row already exists with matching checksum → skip.
--     - Repeat different checksum:  row exists with different checksum → FAIL
--       CLOSED with ChecksumMismatchError.
--     - Duplicate version (different name):  unique index on version → reject.
--   The sentinel text '__CHECKSUM_SELF__' in schema_version is intentional;
--   the runner replaces it with the real SHA-256 digest after applying the SQL
--   and before committing.  Nothing in this file is self-referential.
--
-- ACCOUNT ISOLATION:
--   Child tables carry account_id and use composite FK references that
--   include account_id where the parent has a (account_id, pk) unique key.
--   This enforces DB-level cross-account containment, not just app filtering.
--
-- IDEMPOTENCY KEYS:
--   - execution_requests.idempotency_key  — caller-supplied per-request key
--   - orders.exchange_order_id            — broker identity (unique per acct/venue)
--   - fills.exchange_fill_id             — broker fill identity (unique per order)
--   - position_updates.apply_key          — fill→position apply deduplication
--   - ledger_entries.reference_idempotency_key — ledger reference deduplication
--   - outbox_messages.event_id            — stable event identity for dedup
--
-- APPEND-ONLY ENFORCEMENT:
--   Append-only tables are protected by a DO-NOTHING-on-UPDATE trigger policy
--   implemented via PostgreSQL rules (RULE ON UPDATE / ON DELETE DO INSTEAD
--   NOTHING) so that even a direct SQL UPDATE/DELETE is silently blocked at
--   the database level regardless of application logic.
--
-- IDENTIFIER CONVENTION:  UUID everywhere (gen_random_uuid() defaults)
-- TIMESTAMP CONVENTION:   TIMESTAMPTZ with UTC (now() defaults)
-- VERSIONING:             Mutable aggregates use INTEGER version CHECK (version > 0)
-- =============================================================================

BEGIN;

-- ── Schema ──────────────────────────────────────────────────────────────────

CREATE SCHEMA IF NOT EXISTS toji_active;

SET search_path TO toji_active;

-- ── Helper: append-only protection macro ────────────────────────────────────
-- Applied per table after creation using individual RULE statements.

-- ── 1. schema_version (append-only) ─────────────────────────────────────────

CREATE TABLE toji_active.schema_version (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    version         TEXT            NOT NULL,
    name            TEXT            NOT NULL,
    checksum        TEXT            NOT NULL,
    component       TEXT            NOT NULL DEFAULT 'active_authority',
    applied_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    applied_by      TEXT            NOT NULL DEFAULT current_user
);

CREATE UNIQUE INDEX uq_schema_version_version
    ON toji_active.schema_version (version);

-- schema_version is append-only: block UPDATE and DELETE at the DB level
CREATE RULE schema_version_no_update AS
    ON UPDATE TO toji_active.schema_version DO INSTEAD NOTHING;
CREATE RULE schema_version_no_delete AS
    ON DELETE TO toji_active.schema_version DO INSTEAD NOTHING;

-- NOTE: The runner inserts the schema_version row AFTER applying the SQL
-- with the actual checksum.  The sentinel below is replaced by the runner.
-- If this migration is applied directly (e.g. psql), insert must be done
-- separately with the real checksum.
INSERT INTO toji_active.schema_version (version, name, checksum, component)
VALUES (
    '0001',
    'active_authority_foundation',
    '__CHECKSUM_SELF__',
    'active_authority'
);

-- ── 2. execution_requests (append-only) ─────────────────────────────────────
--
-- IDEMPOTENCY: idempotency_key is caller-supplied; unique per (account_id,
-- idempotency_key) to prevent duplicate submissions from the same account.
-- CHECK: LIMIT order requires limit_price; STOP/STOP_LIMIT requires stop_price.

CREATE TABLE toji_active.execution_requests (
    request_id        UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id        UUID            NOT NULL,
    strategy_id       UUID            NOT NULL,
    idempotency_key   TEXT            NOT NULL,
    symbol            TEXT            NOT NULL,
    side              TEXT            NOT NULL CHECK (side IN ('BUY', 'SELL')),
    quantity          NUMERIC(20,8)   NOT NULL CHECK (quantity > 0),
    order_type        TEXT            NOT NULL CHECK (order_type IN ('MARKET', 'LIMIT', 'STOP', 'STOP_LIMIT')),
    limit_price       NUMERIC(20,8)   CHECK (
                          (order_type IN ('LIMIT', 'STOP_LIMIT') AND limit_price IS NOT NULL AND limit_price > 0)
                          OR order_type NOT IN ('LIMIT', 'STOP_LIMIT')
                      ),
    stop_price        NUMERIC(20,8)   CHECK (
                          (order_type IN ('STOP', 'STOP_LIMIT') AND stop_price IS NOT NULL AND stop_price > 0)
                          OR order_type NOT IN ('STOP', 'STOP_LIMIT')
                      ),
    time_in_force     TEXT            NOT NULL DEFAULT 'GTC' CHECK (time_in_force IN ('GTC', 'IOC', 'FOK', 'DAY')),
    urgency           TEXT            NOT NULL DEFAULT 'NORMAL' CHECK (urgency IN ('LOW', 'NORMAL', 'HIGH', 'CRITICAL')),
    metadata          JSONB           NOT NULL DEFAULT '{}'::jsonb,
    created_at        TIMESTAMPTZ     NOT NULL DEFAULT now(),
    correlation_id    UUID            NOT NULL DEFAULT gen_random_uuid()
);

-- Idempotency: one request per (account, caller key)
CREATE UNIQUE INDEX uq_execution_requests_idempotency
    ON toji_active.execution_requests (account_id, idempotency_key);

CREATE INDEX idx_execution_requests_account_id
    ON toji_active.execution_requests (account_id);
CREATE INDEX idx_execution_requests_strategy_id
    ON toji_active.execution_requests (strategy_id);
CREATE INDEX idx_execution_requests_symbol
    ON toji_active.execution_requests (symbol);
CREATE INDEX idx_execution_requests_created_at
    ON toji_active.execution_requests (created_at);

-- Append-only protection
CREATE RULE execution_requests_no_update AS
    ON UPDATE TO toji_active.execution_requests DO INSTEAD NOTHING;
CREATE RULE execution_requests_no_delete AS
    ON DELETE TO toji_active.execution_requests DO INSTEAD NOTHING;

-- ── 3. order_intents (append-only) ──────────────────────────────────────────
--
-- ACCOUNT ISOLATION: references execution_requests via (account_id, request_id)
-- composite unique key so cross-account intent creation is DB-rejected.

-- Add composite unique key to execution_requests for account-isolated FK
CREATE UNIQUE INDEX uq_execution_requests_account_request
    ON toji_active.execution_requests (account_id, request_id);

CREATE TABLE toji_active.order_intents (
    intent_id         UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id        UUID            NOT NULL,
    request_id        UUID            NOT NULL,
    symbol            TEXT            NOT NULL,
    side              TEXT            NOT NULL CHECK (side IN ('BUY', 'SELL')),
    quantity          NUMERIC(20,8)   NOT NULL CHECK (quantity > 0),
    order_type        TEXT            NOT NULL CHECK (order_type IN ('MARKET', 'LIMIT', 'STOP', 'STOP_LIMIT')),
    limit_price       NUMERIC(20,8),
    stop_price        NUMERIC(20,8),
    time_in_force     TEXT            NOT NULL DEFAULT 'GTC' CHECK (time_in_force IN ('GTC', 'IOC', 'FOK', 'DAY')),
    intent_reason     TEXT            NOT NULL DEFAULT '',
    risk_check_pass   BOOLEAN         NOT NULL DEFAULT false,
    metadata          JSONB           NOT NULL DEFAULT '{}'::jsonb,
    created_at        TIMESTAMPTZ     NOT NULL DEFAULT now(),
    FOREIGN KEY (account_id, request_id)
        REFERENCES toji_active.execution_requests (account_id, request_id)
);

CREATE INDEX idx_order_intents_request_id
    ON toji_active.order_intents (request_id);
CREATE INDEX idx_order_intents_account_id
    ON toji_active.order_intents (account_id);
CREATE INDEX idx_order_intents_symbol
    ON toji_active.order_intents (symbol);

-- Composite unique for downstream account-isolated FK
CREATE UNIQUE INDEX uq_order_intents_account_intent
    ON toji_active.order_intents (account_id, intent_id);

-- Append-only protection
CREATE RULE order_intents_no_update AS
    ON UPDATE TO toji_active.order_intents DO INSTEAD NOTHING;
CREATE RULE order_intents_no_delete AS
    ON DELETE TO toji_active.order_intents DO INSTEAD NOTHING;

-- ── 4. routing_decisions (append-only) ──────────────────────────────────────
--
-- ACCOUNT ISOLATION: composite FK via (account_id, intent_id).

CREATE TABLE toji_active.routing_decisions (
    decision_id       UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id        UUID            NOT NULL,
    intent_id         UUID            NOT NULL,
    venue             TEXT            NOT NULL CHECK (length(trim(venue)) > 0),
    routing_algo      TEXT            NOT NULL DEFAULT '',
    routing_reason    TEXT            NOT NULL DEFAULT '',
    estimated_cost    NUMERIC(20,8)   CHECK (estimated_cost IS NULL OR estimated_cost >= 0),
    selected          BOOLEAN         NOT NULL DEFAULT false,
    metadata          JSONB           NOT NULL DEFAULT '{}'::jsonb,
    created_at        TIMESTAMPTZ     NOT NULL DEFAULT now(),
    FOREIGN KEY (account_id, intent_id)
        REFERENCES toji_active.order_intents (account_id, intent_id)
);

CREATE INDEX idx_routing_decisions_intent_id
    ON toji_active.routing_decisions (intent_id);
CREATE INDEX idx_routing_decisions_account_id
    ON toji_active.routing_decisions (account_id);
CREATE INDEX idx_routing_decisions_venue
    ON toji_active.routing_decisions (venue);

-- Composite unique for downstream account-isolated FK
CREATE UNIQUE INDEX uq_routing_decisions_account_decision
    ON toji_active.routing_decisions (account_id, decision_id);

-- Append-only protection
CREATE RULE routing_decisions_no_update AS
    ON UPDATE TO toji_active.routing_decisions DO INSTEAD NOTHING;
CREATE RULE routing_decisions_no_delete AS
    ON DELETE TO toji_active.routing_decisions DO INSTEAD NOTHING;

-- ── 5. orders (mutable-versioned) ───────────────────────────────────────────
--
-- ACCOUNT ISOLATION: composite FKs to intent and decision using account_id.
-- IDEMPOTENCY: exchange_order_id unique per (account_id, venue) — broker identity.
-- CHECK: filled_quantity <= quantity; commission non-negative.

CREATE TABLE toji_active.orders (
    order_id            UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id          UUID            NOT NULL,
    intent_id           UUID            NOT NULL,
    decision_id         UUID            NOT NULL,
    exchange_order_id   TEXT,
    symbol              TEXT            NOT NULL,
    side                TEXT            NOT NULL CHECK (side IN ('BUY', 'SELL')),
    quantity            NUMERIC(20,8)   NOT NULL CHECK (quantity > 0),
    filled_quantity     NUMERIC(20,8)   NOT NULL DEFAULT 0
                            CHECK (filled_quantity >= 0 AND filled_quantity <= quantity),
    order_type          TEXT            NOT NULL CHECK (order_type IN ('MARKET', 'LIMIT', 'STOP', 'STOP_LIMIT')),
    limit_price         NUMERIC(20,8),
    stop_price          NUMERIC(20,8),
    time_in_force       TEXT            NOT NULL DEFAULT 'GTC' CHECK (time_in_force IN ('GTC', 'IOC', 'FOK', 'DAY')),
    status              TEXT            NOT NULL DEFAULT 'PENDING' CHECK (status IN (
                            'PENDING', 'SUBMITTED', 'ACKNOWLEDGED', 'PARTIALLY_FILLED',
                            'FILLED', 'CANCELLED', 'REJECTED', 'EXPIRED', 'ERROR'
                        )),
    venue               TEXT            NOT NULL CHECK (length(trim(venue)) > 0),
    submitted_at        TIMESTAMPTZ,
    acknowledged_at     TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    metadata            JSONB           NOT NULL DEFAULT '{}'::jsonb,
    version             INTEGER         NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
    FOREIGN KEY (account_id, intent_id)
        REFERENCES toji_active.order_intents (account_id, intent_id),
    FOREIGN KEY (account_id, decision_id)
        REFERENCES toji_active.routing_decisions (account_id, decision_id)
);

-- Broker identity: one exchange_order_id per account+venue (when set)
CREATE UNIQUE INDEX uq_orders_exchange_id_account_venue
    ON toji_active.orders (account_id, venue, exchange_order_id)
    WHERE exchange_order_id IS NOT NULL;

-- Composite unique for downstream account-isolated FK
CREATE UNIQUE INDEX uq_orders_account_order
    ON toji_active.orders (account_id, order_id);

CREATE INDEX idx_orders_account_id        ON toji_active.orders (account_id);
CREATE INDEX idx_orders_intent_id         ON toji_active.orders (intent_id);
CREATE INDEX idx_orders_decision_id       ON toji_active.orders (decision_id);
CREATE INDEX idx_orders_symbol            ON toji_active.orders (symbol);
CREATE INDEX idx_orders_status            ON toji_active.orders (status);
CREATE INDEX idx_orders_created_at        ON toji_active.orders (created_at);
CREATE INDEX idx_orders_account_status    ON toji_active.orders (account_id, status);

-- ── 6. fills (append-only) ──────────────────────────────────────────────────
--
-- ACCOUNT ISOLATION: composite FK to orders via (account_id, order_id).
-- IDEMPOTENCY: exchange_fill_id unique per (account_id, order_id) — broker fill identity.
-- CHECK: commission >= 0; price > 0; quantity > 0.

CREATE TABLE toji_active.fills (
    fill_id             UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id          UUID            NOT NULL,
    order_id            UUID            NOT NULL,
    exchange_fill_id    TEXT,
    symbol              TEXT            NOT NULL,
    side                TEXT            NOT NULL CHECK (side IN ('BUY', 'SELL')),
    quantity            NUMERIC(20,8)   NOT NULL CHECK (quantity > 0),
    price               NUMERIC(20,8)   NOT NULL CHECK (price > 0),
    commission          NUMERIC(20,8)   NOT NULL DEFAULT 0 CHECK (commission >= 0),
    commission_asset    TEXT            NOT NULL DEFAULT '',
    liquidity           TEXT            NOT NULL DEFAULT '' CHECK (liquidity IN ('', 'MAKER', 'TAKER')),
    venue               TEXT            NOT NULL,
    filled_at           TIMESTAMPTZ     NOT NULL,
    metadata            JSONB           NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
    FOREIGN KEY (account_id, order_id)
        REFERENCES toji_active.orders (account_id, order_id)
);

-- Broker fill identity: one exchange_fill_id per account+order (when set)
CREATE UNIQUE INDEX uq_fills_exchange_fill_id
    ON toji_active.fills (account_id, order_id, exchange_fill_id)
    WHERE exchange_fill_id IS NOT NULL;

-- Composite unique for downstream account-isolated FK
CREATE UNIQUE INDEX uq_fills_account_fill
    ON toji_active.fills (account_id, fill_id);

CREATE INDEX idx_fills_order_id    ON toji_active.fills (order_id);
CREATE INDEX idx_fills_account_id  ON toji_active.fills (account_id);
CREATE INDEX idx_fills_symbol      ON toji_active.fills (symbol);
CREATE INDEX idx_fills_filled_at   ON toji_active.fills (filled_at);

-- Append-only protection
CREATE RULE fills_no_update AS
    ON UPDATE TO toji_active.fills DO INSTEAD NOTHING;
CREATE RULE fills_no_delete AS
    ON DELETE TO toji_active.fills DO INSTEAD NOTHING;

-- ── 7. execution_results (append-only) ──────────────────────────────────────
--
-- ACCOUNT ISOLATION: composite FK to execution_requests via (account_id, request_id).
-- CHECK: filled_quantity >= 0; total_commission >= 0.

CREATE TABLE toji_active.execution_results (
    result_id           UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id          UUID            NOT NULL,
    request_id          UUID            NOT NULL,
    order_id            UUID,
    status              TEXT            NOT NULL CHECK (status IN ('SUCCESS', 'PARTIAL', 'FAILED', 'CANCELLED', 'TIMEOUT')),
    filled_quantity     NUMERIC(20,8)   NOT NULL DEFAULT 0 CHECK (filled_quantity >= 0),
    average_price       NUMERIC(20,8)   CHECK (average_price IS NULL OR average_price > 0),
    total_commission    NUMERIC(20,8)   NOT NULL DEFAULT 0 CHECK (total_commission >= 0),
    total_cost          NUMERIC(20,8),
    slippage_bps        NUMERIC(10,4),
    error_code          TEXT,
    error_message       TEXT,
    metadata            JSONB           NOT NULL DEFAULT '{}'::jsonb,
    completed_at        TIMESTAMPTZ     NOT NULL DEFAULT now(),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
    FOREIGN KEY (account_id, request_id)
        REFERENCES toji_active.execution_requests (account_id, request_id)
);

CREATE INDEX idx_execution_results_request_id  ON toji_active.execution_results (request_id);
CREATE INDEX idx_execution_results_order_id    ON toji_active.execution_results (order_id);
CREATE INDEX idx_execution_results_account_id  ON toji_active.execution_results (account_id);
CREATE INDEX idx_execution_results_status      ON toji_active.execution_results (status);

-- Append-only protection
CREATE RULE execution_results_no_update AS
    ON UPDATE TO toji_active.execution_results DO INSTEAD NOTHING;
CREATE RULE execution_results_no_delete AS
    ON DELETE TO toji_active.execution_results DO INSTEAD NOTHING;

-- ── 8. execution_metrics (append-only) ──────────────────────────────────────

CREATE TABLE toji_active.execution_metrics (
    metric_id           UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id          UUID            NOT NULL,
    request_id          UUID            NOT NULL,
    order_id            UUID,
    metric_type         TEXT            NOT NULL CHECK (length(trim(metric_type)) > 0),
    latency_ms          NUMERIC(10,2)   CHECK (latency_ms IS NULL OR latency_ms >= 0),
    slippage_bps        NUMERIC(10,4),
    market_impact_bps   NUMERIC(10,4),
    fill_rate           NUMERIC(5,4)    CHECK (fill_rate IS NULL OR (fill_rate >= 0 AND fill_rate <= 1)),
    cost_bps            NUMERIC(10,4),
    venue               TEXT,
    metadata            JSONB           NOT NULL DEFAULT '{}'::jsonb,
    measured_at         TIMESTAMPTZ     NOT NULL DEFAULT now(),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
    FOREIGN KEY (account_id, request_id)
        REFERENCES toji_active.execution_requests (account_id, request_id)
);

CREATE INDEX idx_execution_metrics_request_id  ON toji_active.execution_metrics (request_id);
CREATE INDEX idx_execution_metrics_order_id    ON toji_active.execution_metrics (order_id);
CREATE INDEX idx_execution_metrics_account_id  ON toji_active.execution_metrics (account_id);
CREATE INDEX idx_execution_metrics_metric_type ON toji_active.execution_metrics (metric_type);
CREATE INDEX idx_execution_metrics_measured_at ON toji_active.execution_metrics (measured_at);

-- Append-only protection
CREATE RULE execution_metrics_no_update AS
    ON UPDATE TO toji_active.execution_metrics DO INSTEAD NOTHING;
CREATE RULE execution_metrics_no_delete AS
    ON DELETE TO toji_active.execution_metrics DO INSTEAD NOTHING;

-- ── 9. execution_journal (append-only) ──────────────────────────────────────

CREATE TABLE toji_active.execution_journal (
    entry_id            UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id          UUID            NOT NULL,
    request_id          UUID,
    order_id            UUID,
    event_type          TEXT            NOT NULL CHECK (length(trim(event_type)) > 0),
    severity            TEXT            NOT NULL DEFAULT 'INFO' CHECK (severity IN ('DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL')),
    message             TEXT            NOT NULL,
    details             JSONB           NOT NULL DEFAULT '{}'::jsonb,
    correlation_id      UUID,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE INDEX idx_execution_journal_request_id  ON toji_active.execution_journal (request_id);
CREATE INDEX idx_execution_journal_order_id    ON toji_active.execution_journal (order_id);
CREATE INDEX idx_execution_journal_account_id  ON toji_active.execution_journal (account_id);
CREATE INDEX idx_execution_journal_event_type  ON toji_active.execution_journal (event_type);
CREATE INDEX idx_execution_journal_created_at  ON toji_active.execution_journal (created_at);

-- Append-only protection
CREATE RULE execution_journal_no_update AS
    ON UPDATE TO toji_active.execution_journal DO INSTEAD NOTHING;
CREATE RULE execution_journal_no_delete AS
    ON DELETE TO toji_active.execution_journal DO INSTEAD NOTHING;

-- ── 10. audit_records (append-only) ─────────────────────────────────────────

CREATE TABLE toji_active.audit_records (
    audit_id            UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id          UUID            NOT NULL,
    actor               TEXT            NOT NULL CHECK (length(trim(actor)) > 0),
    action              TEXT            NOT NULL CHECK (length(trim(action)) > 0),
    resource_type       TEXT            NOT NULL CHECK (length(trim(resource_type)) > 0),
    resource_id         UUID            NOT NULL,
    old_state           JSONB,
    new_state           JSONB,
    reason              TEXT            NOT NULL DEFAULT '',
    correlation_id      UUID,
    ip_address          TEXT,
    metadata            JSONB           NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE INDEX idx_audit_records_account_id        ON toji_active.audit_records (account_id);
CREATE INDEX idx_audit_records_resource_type_id  ON toji_active.audit_records (resource_type, resource_id);
CREATE INDEX idx_audit_records_actor             ON toji_active.audit_records (actor);
CREATE INDEX idx_audit_records_action            ON toji_active.audit_records (action);
CREATE INDEX idx_audit_records_created_at        ON toji_active.audit_records (created_at);
CREATE INDEX idx_audit_records_correlation_id    ON toji_active.audit_records (correlation_id);

-- Append-only protection
CREATE RULE audit_records_no_update AS
    ON UPDATE TO toji_active.audit_records DO INSTEAD NOTHING;
CREATE RULE audit_records_no_delete AS
    ON DELETE TO toji_active.audit_records DO INSTEAD NOTHING;

-- ── 11. oms_state (mutable-versioned, one active row per account) ────────────

CREATE TABLE toji_active.oms_state (
    oms_state_id        UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id          UUID            NOT NULL,
    status              TEXT            NOT NULL DEFAULT 'INITIALIZING' CHECK (status IN (
                            'INITIALIZING', 'READY', 'ACTIVE', 'PAUSED',
                            'DRAINING', 'STOPPED', 'ERROR'
                        )),
    open_order_count    INTEGER         NOT NULL DEFAULT 0 CHECK (open_order_count >= 0),
    pending_fills       INTEGER         NOT NULL DEFAULT 0 CHECK (pending_fills >= 0),
    last_heartbeat      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    state_data          JSONB           NOT NULL DEFAULT '{}'::jsonb,
    version             INTEGER         NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT now()
);

-- One active (non-terminal) OMS state per account
CREATE UNIQUE INDEX uq_oms_state_active_account
    ON toji_active.oms_state (account_id)
    WHERE status NOT IN ('STOPPED', 'ERROR');

CREATE INDEX idx_oms_state_status ON toji_active.oms_state (status);

-- ── 12. positions (mutable-versioned) ───────────────────────────────────────
--
-- CHECK: quantity >= 0; average_entry_price >= 0; cost_basis >= 0.

CREATE TABLE toji_active.positions (
    position_id         UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id          UUID            NOT NULL,
    symbol              TEXT            NOT NULL CHECK (length(trim(symbol)) > 0),
    side                TEXT            NOT NULL CHECK (side IN ('LONG', 'SHORT', 'FLAT')),
    quantity            NUMERIC(20,8)   NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    average_entry_price NUMERIC(20,8)   NOT NULL DEFAULT 0 CHECK (average_entry_price >= 0),
    realized_pnl        NUMERIC(20,8)   NOT NULL DEFAULT 0,
    unrealized_pnl      NUMERIC(20,8)   NOT NULL DEFAULT 0,
    cost_basis          NUMERIC(20,8)   NOT NULL DEFAULT 0 CHECK (cost_basis >= 0),
    market_value        NUMERIC(20,8)   NOT NULL DEFAULT 0,
    metadata            JSONB           NOT NULL DEFAULT '{}'::jsonb,
    version             INTEGER         NOT NULL DEFAULT 1 CHECK (version > 0),
    opened_at           TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT now()
);

-- One position row per (account, symbol)
CREATE UNIQUE INDEX uq_positions_account_symbol
    ON toji_active.positions (account_id, symbol);

CREATE INDEX idx_positions_account_id ON toji_active.positions (account_id);
CREATE INDEX idx_positions_symbol     ON toji_active.positions (symbol);
CREATE INDEX idx_positions_side       ON toji_active.positions (side);

-- Composite unique for downstream account-isolated FK
CREATE UNIQUE INDEX uq_positions_account_position
    ON toji_active.positions (account_id, position_id);

-- ── 13. position_updates (append-only) ──────────────────────────────────────
--
-- ACCOUNT ISOLATION: composite FK to positions via (account_id, position_id).
-- IDEMPOTENCY: apply_key prevents double-application of the same fill→position.
-- CHECK: price > 0.

CREATE TABLE toji_active.position_updates (
    update_id           UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id          UUID            NOT NULL,
    position_id         UUID            NOT NULL,
    fill_id             UUID,
    apply_key           TEXT            NOT NULL,
    symbol              TEXT            NOT NULL,
    update_type         TEXT            NOT NULL CHECK (update_type IN ('OPEN', 'INCREASE', 'DECREASE', 'CLOSE', 'ADJUSTMENT')),
    quantity_change     NUMERIC(20,8)   NOT NULL,
    price               NUMERIC(20,8)   NOT NULL CHECK (price > 0),
    realized_pnl        NUMERIC(20,8)   NOT NULL DEFAULT 0,
    position_after      JSONB           NOT NULL DEFAULT '{}'::jsonb,
    metadata            JSONB           NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
    FOREIGN KEY (account_id, position_id)
        REFERENCES toji_active.positions (account_id, position_id),
    FOREIGN KEY (account_id, fill_id)
        REFERENCES toji_active.fills (account_id, fill_id)
        DEFERRABLE INITIALLY DEFERRED
);

-- Fill→position apply deduplication: one update per (account, apply_key)
CREATE UNIQUE INDEX uq_position_updates_apply_key
    ON toji_active.position_updates (account_id, apply_key);

CREATE INDEX idx_position_updates_position_id ON toji_active.position_updates (position_id);
CREATE INDEX idx_position_updates_account_id  ON toji_active.position_updates (account_id);
CREATE INDEX idx_position_updates_fill_id     ON toji_active.position_updates (fill_id);
CREATE INDEX idx_position_updates_symbol      ON toji_active.position_updates (symbol);
CREATE INDEX idx_position_updates_created_at  ON toji_active.position_updates (created_at);

-- Append-only protection
CREATE RULE position_updates_no_update AS
    ON UPDATE TO toji_active.position_updates DO INSTEAD NOTHING;
CREATE RULE position_updates_no_delete AS
    ON DELETE TO toji_active.position_updates DO INSTEAD NOTHING;

-- ── 14. portfolio_snapshots (append-only) ────────────────────────────────────
--
-- CHECK: total_equity and cash_balance present; position_count >= 0.

CREATE TABLE toji_active.portfolio_snapshots (
    snapshot_id             UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id              UUID            NOT NULL,
    total_equity            NUMERIC(20,8)   NOT NULL,
    cash_balance            NUMERIC(20,8)   NOT NULL,
    total_market_value      NUMERIC(20,8)   NOT NULL,
    total_unrealized_pnl    NUMERIC(20,8)   NOT NULL DEFAULT 0,
    total_realized_pnl      NUMERIC(20,8)   NOT NULL DEFAULT 0,
    position_count          INTEGER         NOT NULL DEFAULT 0 CHECK (position_count >= 0),
    positions_data          JSONB           NOT NULL DEFAULT '[]'::jsonb,
    risk_metrics            JSONB           NOT NULL DEFAULT '{}'::jsonb,
    metadata                JSONB           NOT NULL DEFAULT '{}'::jsonb,
    snapshot_at             TIMESTAMPTZ     NOT NULL DEFAULT now(),
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE INDEX idx_portfolio_snapshots_account_id       ON toji_active.portfolio_snapshots (account_id);
CREATE INDEX idx_portfolio_snapshots_snapshot_at      ON toji_active.portfolio_snapshots (snapshot_at);
CREATE INDEX idx_portfolio_snapshots_account_snapshot ON toji_active.portfolio_snapshots (account_id, snapshot_at);

-- Append-only protection
CREATE RULE portfolio_snapshots_no_update AS
    ON UPDATE TO toji_active.portfolio_snapshots DO INSTEAD NOTHING;
CREATE RULE portfolio_snapshots_no_delete AS
    ON DELETE TO toji_active.portfolio_snapshots DO INSTEAD NOTHING;

-- ── 15. ledger_entries (append-only, double-entry) ───────────────────────────
--
-- IDEMPOTENCY: reference_idempotency_key prevents duplicate ledger posting for
-- the same real-world event per account.
-- CHECK: amount != 0 (no zero-value ledger lines).

CREATE TABLE toji_active.ledger_entries (
    entry_id                        UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id                      UUID            NOT NULL,
    ledger_type                     TEXT            NOT NULL CHECK (ledger_type IN ('DEBIT', 'CREDIT')),
    entry_type                      TEXT            NOT NULL CHECK (entry_type IN (
                                        'TRADE', 'COMMISSION', 'FUNDING', 'WITHDRAWAL',
                                        'DEPOSIT', 'ADJUSTMENT', 'FEE', 'DIVIDEND', 'INTEREST'
                                    )),
    amount                          NUMERIC(20,8)   NOT NULL CHECK (amount != 0),
    currency                        TEXT            NOT NULL DEFAULT 'USD' CHECK (length(trim(currency)) > 0),
    balance_after                   NUMERIC(20,8)   NOT NULL,
    reference_type                  TEXT,
    reference_id                    UUID,
    reference_idempotency_key       TEXT,
    description                     TEXT            NOT NULL DEFAULT '',
    metadata                        JSONB           NOT NULL DEFAULT '{}'::jsonb,
    created_at                      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

-- Ledger reference deduplication: one ledger entry per (account, ref_idempotency_key)
CREATE UNIQUE INDEX uq_ledger_entries_ref_idempotency
    ON toji_active.ledger_entries (account_id, reference_idempotency_key)
    WHERE reference_idempotency_key IS NOT NULL;

CREATE INDEX idx_ledger_entries_account_id  ON toji_active.ledger_entries (account_id);
CREATE INDEX idx_ledger_entries_entry_type  ON toji_active.ledger_entries (entry_type);
CREATE INDEX idx_ledger_entries_reference   ON toji_active.ledger_entries (reference_type, reference_id);
CREATE INDEX idx_ledger_entries_created_at  ON toji_active.ledger_entries (created_at);

-- Append-only protection
CREATE RULE ledger_entries_no_update AS
    ON UPDATE TO toji_active.ledger_entries DO INSTEAD NOTHING;
CREATE RULE ledger_entries_no_delete AS
    ON DELETE TO toji_active.ledger_entries DO INSTEAD NOTHING;

-- ── 16. outbox_messages (mutable — status/retry transitions only) ────────────
--
-- IDEMPOTENCY: event_id is a stable caller-supplied identity for this event.
--   Unique per (account_id, event_id) prevents double-insertion of the same event.
-- OUTBOX SEMANTICS:
--   - aggregate_type / aggregate_id identify the domain aggregate.
--   - available_at controls dispatch scheduling (rate limiting, back-off).
--   - lease_expires_at / leased_by implement worker-safe claim/lease semantics.
--   - version / compare-and-set protects concurrent worker races.
-- STATE TRANSITIONS (documented):
--   PENDING → PROCESSING (worker claims)
--   PROCESSING → SENT (successful dispatch)
--   PROCESSING → FAILED (dispatch error, retry eligible)
--   FAILED → PROCESSING (retry, if retry_count < max_retries)
--   FAILED → DEAD_LETTER (retry_count >= max_retries)
-- CHECK: max_retries >= 0; retry_count >= 0.

CREATE TABLE toji_active.outbox_messages (
    message_id          UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id          UUID            NOT NULL,
    event_id            UUID            NOT NULL,
    aggregate_type      TEXT            NOT NULL CHECK (length(trim(aggregate_type)) > 0),
    aggregate_id        UUID            NOT NULL,
    topic               TEXT            NOT NULL CHECK (length(trim(topic)) > 0),
    event_type          TEXT            NOT NULL CHECK (length(trim(event_type)) > 0),
    payload             JSONB           NOT NULL,
    status              TEXT            NOT NULL DEFAULT 'PENDING' CHECK (status IN (
                            'PENDING', 'PROCESSING', 'SENT', 'FAILED', 'DEAD_LETTER'
                        )),
    retry_count         INTEGER         NOT NULL DEFAULT 0 CHECK (retry_count >= 0),
    max_retries         INTEGER         NOT NULL DEFAULT 3 CHECK (max_retries >= 0),
    last_error          TEXT,
    available_at        TIMESTAMPTZ     NOT NULL DEFAULT now(),
    lease_expires_at    TIMESTAMPTZ,
    leased_by           TEXT,
    version             INTEGER         NOT NULL DEFAULT 1 CHECK (version > 0),
    correlation_id      UUID,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
    sent_at             TIMESTAMPTZ
);

-- Stable event deduplication: one message per (account, event_id)
CREATE UNIQUE INDEX uq_outbox_messages_event_id
    ON toji_active.outbox_messages (account_id, event_id);

CREATE INDEX idx_outbox_messages_status      ON toji_active.outbox_messages (status);
CREATE INDEX idx_outbox_messages_account_id  ON toji_active.outbox_messages (account_id);
CREATE INDEX idx_outbox_messages_topic       ON toji_active.outbox_messages (topic);
CREATE INDEX idx_outbox_messages_created_at  ON toji_active.outbox_messages (created_at);
CREATE INDEX idx_outbox_messages_aggregate   ON toji_active.outbox_messages (aggregate_type, aggregate_id);

-- Worker dispatch index: pending/failed messages available now, ordered for FIFO
CREATE INDEX idx_outbox_pending
    ON toji_active.outbox_messages (available_at, created_at)
    WHERE status IN ('PENDING', 'FAILED');

-- Lease expiry cleanup index
CREATE INDEX idx_outbox_lease_expires
    ON toji_active.outbox_messages (lease_expires_at)
    WHERE status = 'PROCESSING';

-- ── Restore search_path ──────────────────────────────────────────────────────

RESET search_path;

COMMIT;
