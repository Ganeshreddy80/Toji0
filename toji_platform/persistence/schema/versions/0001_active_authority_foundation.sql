-- =============================================================================
-- DATA-001-P0-03A: Active Authority Foundation
-- Migration: 0001_active_authority_foundation
-- Schema:    toji_active (within existing 'toji' database)
-- Owner:     DATA team — CTO approval required for changes
-- =============================================================================
--
-- This migration creates the toji_active schema and all 16 foundation tables
-- required for active-runtime persistence. It is designed to be applied to
-- a PostgreSQL database that already contains research-platform tables in
-- the public schema. This migration does NOT modify any existing tables.
--
-- Identifier convention:  UUID everywhere (gen_random_uuid() defaults)
-- Timestamp convention:   TIMESTAMPTZ with UTC (now() defaults)
-- Versioning:             Mutable aggregates use INTEGER version columns
-- Append-only:            Immutable entities have no UPDATE path
-- Account scoping:        Multi-account via account_id UUID columns
-- =============================================================================

BEGIN;

-- ── Schema ──────────────────────────────────────────────────────────────────

CREATE SCHEMA IF NOT EXISTS toji_active;

SET search_path TO toji_active, public;

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

-- Record this migration
INSERT INTO toji_active.schema_version (version, name, checksum, component)
VALUES (
    '0001',
    'active_authority_foundation',
    '__CHECKSUM_PLACEHOLDER__',
    'active_authority'
);

-- ── 2. execution_requests (append-only) ─────────────────────────────────────

CREATE TABLE toji_active.execution_requests (
    request_id      UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id      UUID            NOT NULL,
    strategy_id     UUID            NOT NULL,
    symbol          TEXT            NOT NULL,
    side            TEXT            NOT NULL CHECK (side IN ('BUY', 'SELL')),
    quantity         NUMERIC(20,8)   NOT NULL CHECK (quantity > 0),
    order_type      TEXT            NOT NULL CHECK (order_type IN ('MARKET', 'LIMIT', 'STOP', 'STOP_LIMIT')),
    limit_price     NUMERIC(20,8),
    stop_price      NUMERIC(20,8),
    time_in_force   TEXT            NOT NULL DEFAULT 'GTC' CHECK (time_in_force IN ('GTC', 'IOC', 'FOK', 'DAY')),
    urgency         TEXT            NOT NULL DEFAULT 'NORMAL' CHECK (urgency IN ('LOW', 'NORMAL', 'HIGH', 'CRITICAL')),
    metadata        JSONB           NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    correlation_id  UUID            NOT NULL DEFAULT gen_random_uuid()
);

CREATE INDEX idx_execution_requests_account_id
    ON toji_active.execution_requests (account_id);
CREATE INDEX idx_execution_requests_strategy_id
    ON toji_active.execution_requests (strategy_id);
CREATE INDEX idx_execution_requests_symbol
    ON toji_active.execution_requests (symbol);
CREATE INDEX idx_execution_requests_created_at
    ON toji_active.execution_requests (created_at);

-- ── 3. order_intents (append-only) ──────────────────────────────────────────

CREATE TABLE toji_active.order_intents (
    intent_id       UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id      UUID            NOT NULL REFERENCES toji_active.execution_requests(request_id),
    account_id      UUID            NOT NULL,
    symbol          TEXT            NOT NULL,
    side            TEXT            NOT NULL CHECK (side IN ('BUY', 'SELL')),
    quantity         NUMERIC(20,8)   NOT NULL CHECK (quantity > 0),
    order_type      TEXT            NOT NULL CHECK (order_type IN ('MARKET', 'LIMIT', 'STOP', 'STOP_LIMIT')),
    limit_price     NUMERIC(20,8),
    stop_price      NUMERIC(20,8),
    time_in_force   TEXT            NOT NULL DEFAULT 'GTC',
    intent_reason   TEXT            NOT NULL DEFAULT '',
    risk_check_pass BOOLEAN         NOT NULL DEFAULT false,
    metadata        JSONB           NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE INDEX idx_order_intents_request_id
    ON toji_active.order_intents (request_id);
CREATE INDEX idx_order_intents_account_id
    ON toji_active.order_intents (account_id);
CREATE INDEX idx_order_intents_symbol
    ON toji_active.order_intents (symbol);

-- ── 4. routing_decisions (append-only) ──────────────────────────────────────

CREATE TABLE toji_active.routing_decisions (
    decision_id     UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    intent_id       UUID            NOT NULL REFERENCES toji_active.order_intents(intent_id),
    account_id      UUID            NOT NULL,
    venue           TEXT            NOT NULL,
    routing_algo    TEXT            NOT NULL DEFAULT '',
    routing_reason  TEXT            NOT NULL DEFAULT '',
    estimated_cost  NUMERIC(20,8),
    selected        BOOLEAN         NOT NULL DEFAULT false,
    metadata        JSONB           NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE INDEX idx_routing_decisions_intent_id
    ON toji_active.routing_decisions (intent_id);
CREATE INDEX idx_routing_decisions_account_id
    ON toji_active.routing_decisions (account_id);
CREATE INDEX idx_routing_decisions_venue
    ON toji_active.routing_decisions (venue);

-- ── 5. orders (mutable-versioned) ───────────────────────────────────────────

CREATE TABLE toji_active.orders (
    order_id        UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    intent_id       UUID            NOT NULL REFERENCES toji_active.order_intents(intent_id),
    decision_id     UUID            NOT NULL REFERENCES toji_active.routing_decisions(decision_id),
    account_id      UUID            NOT NULL,
    exchange_order_id TEXT,
    symbol          TEXT            NOT NULL,
    side            TEXT            NOT NULL CHECK (side IN ('BUY', 'SELL')),
    quantity         NUMERIC(20,8)   NOT NULL CHECK (quantity > 0),
    filled_quantity  NUMERIC(20,8)   NOT NULL DEFAULT 0 CHECK (filled_quantity >= 0),
    order_type      TEXT            NOT NULL CHECK (order_type IN ('MARKET', 'LIMIT', 'STOP', 'STOP_LIMIT')),
    limit_price     NUMERIC(20,8),
    stop_price      NUMERIC(20,8),
    time_in_force   TEXT            NOT NULL DEFAULT 'GTC',
    status          TEXT            NOT NULL DEFAULT 'PENDING' CHECK (status IN (
                        'PENDING', 'SUBMITTED', 'ACKNOWLEDGED', 'PARTIALLY_FILLED',
                        'FILLED', 'CANCELLED', 'REJECTED', 'EXPIRED', 'ERROR'
                    )),
    venue           TEXT            NOT NULL,
    submitted_at    TIMESTAMPTZ,
    acknowledged_at TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    metadata        JSONB           NOT NULL DEFAULT '{}'::jsonb,
    version         INTEGER         NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE INDEX idx_orders_account_id ON toji_active.orders (account_id);
CREATE INDEX idx_orders_intent_id ON toji_active.orders (intent_id);
CREATE INDEX idx_orders_decision_id ON toji_active.orders (decision_id);
CREATE INDEX idx_orders_symbol ON toji_active.orders (symbol);
CREATE INDEX idx_orders_status ON toji_active.orders (status);
CREATE INDEX idx_orders_created_at ON toji_active.orders (created_at);
CREATE INDEX idx_orders_exchange_order_id ON toji_active.orders (exchange_order_id);

-- ── 6. fills (append-only) ──────────────────────────────────────────────────

CREATE TABLE toji_active.fills (
    fill_id         UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id        UUID            NOT NULL REFERENCES toji_active.orders(order_id),
    account_id      UUID            NOT NULL,
    exchange_fill_id TEXT,
    symbol          TEXT            NOT NULL,
    side            TEXT            NOT NULL CHECK (side IN ('BUY', 'SELL')),
    quantity         NUMERIC(20,8)   NOT NULL CHECK (quantity > 0),
    price           NUMERIC(20,8)   NOT NULL CHECK (price > 0),
    commission      NUMERIC(20,8)   NOT NULL DEFAULT 0,
    commission_asset TEXT           NOT NULL DEFAULT '',
    liquidity       TEXT            NOT NULL DEFAULT '' CHECK (liquidity IN ('', 'MAKER', 'TAKER')),
    venue           TEXT            NOT NULL,
    filled_at       TIMESTAMPTZ     NOT NULL,
    metadata        JSONB           NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE INDEX idx_fills_order_id ON toji_active.fills (order_id);
CREATE INDEX idx_fills_account_id ON toji_active.fills (account_id);
CREATE INDEX idx_fills_symbol ON toji_active.fills (symbol);
CREATE INDEX idx_fills_filled_at ON toji_active.fills (filled_at);

-- ── 7. execution_results (append-only) ──────────────────────────────────────

CREATE TABLE toji_active.execution_results (
    result_id       UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id      UUID            NOT NULL REFERENCES toji_active.execution_requests(request_id),
    order_id        UUID            REFERENCES toji_active.orders(order_id),
    account_id      UUID            NOT NULL,
    status          TEXT            NOT NULL CHECK (status IN ('SUCCESS', 'PARTIAL', 'FAILED', 'CANCELLED', 'TIMEOUT')),
    filled_quantity  NUMERIC(20,8)   NOT NULL DEFAULT 0,
    average_price   NUMERIC(20,8),
    total_commission NUMERIC(20,8)  NOT NULL DEFAULT 0,
    total_cost      NUMERIC(20,8),
    slippage_bps    NUMERIC(10,4),
    error_code      TEXT,
    error_message   TEXT,
    metadata        JSONB           NOT NULL DEFAULT '{}'::jsonb,
    completed_at    TIMESTAMPTZ     NOT NULL DEFAULT now(),
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE INDEX idx_execution_results_request_id
    ON toji_active.execution_results (request_id);
CREATE INDEX idx_execution_results_order_id
    ON toji_active.execution_results (order_id);
CREATE INDEX idx_execution_results_account_id
    ON toji_active.execution_results (account_id);
CREATE INDEX idx_execution_results_status
    ON toji_active.execution_results (status);

-- ── 8. execution_metrics (append-only) ──────────────────────────────────────

CREATE TABLE toji_active.execution_metrics (
    metric_id       UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id      UUID            NOT NULL REFERENCES toji_active.execution_requests(request_id),
    order_id        UUID            REFERENCES toji_active.orders(order_id),
    account_id      UUID            NOT NULL,
    metric_type     TEXT            NOT NULL,
    latency_ms      NUMERIC(10,2),
    slippage_bps    NUMERIC(10,4),
    market_impact_bps NUMERIC(10,4),
    fill_rate       NUMERIC(5,4),
    cost_bps        NUMERIC(10,4),
    venue           TEXT,
    metadata        JSONB           NOT NULL DEFAULT '{}'::jsonb,
    measured_at     TIMESTAMPTZ     NOT NULL DEFAULT now(),
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE INDEX idx_execution_metrics_request_id
    ON toji_active.execution_metrics (request_id);
CREATE INDEX idx_execution_metrics_order_id
    ON toji_active.execution_metrics (order_id);
CREATE INDEX idx_execution_metrics_account_id
    ON toji_active.execution_metrics (account_id);
CREATE INDEX idx_execution_metrics_metric_type
    ON toji_active.execution_metrics (metric_type);
CREATE INDEX idx_execution_metrics_measured_at
    ON toji_active.execution_metrics (measured_at);

-- ── 9. execution_journal (append-only) ──────────────────────────────────────

CREATE TABLE toji_active.execution_journal (
    entry_id        UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id      UUID            REFERENCES toji_active.execution_requests(request_id),
    order_id        UUID            REFERENCES toji_active.orders(order_id),
    account_id      UUID            NOT NULL,
    event_type      TEXT            NOT NULL,
    severity        TEXT            NOT NULL DEFAULT 'INFO' CHECK (severity IN ('DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL')),
    message         TEXT            NOT NULL,
    details         JSONB           NOT NULL DEFAULT '{}'::jsonb,
    correlation_id  UUID,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE INDEX idx_execution_journal_request_id
    ON toji_active.execution_journal (request_id);
CREATE INDEX idx_execution_journal_order_id
    ON toji_active.execution_journal (order_id);
CREATE INDEX idx_execution_journal_account_id
    ON toji_active.execution_journal (account_id);
CREATE INDEX idx_execution_journal_event_type
    ON toji_active.execution_journal (event_type);
CREATE INDEX idx_execution_journal_created_at
    ON toji_active.execution_journal (created_at);

-- ── 10. audit_records (append-only) ─────────────────────────────────────────

CREATE TABLE toji_active.audit_records (
    audit_id        UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id      UUID            NOT NULL,
    actor           TEXT            NOT NULL,
    action          TEXT            NOT NULL,
    resource_type   TEXT            NOT NULL,
    resource_id     UUID            NOT NULL,
    old_state       JSONB,
    new_state       JSONB,
    reason          TEXT            NOT NULL DEFAULT '',
    correlation_id  UUID,
    ip_address      TEXT,
    metadata        JSONB           NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE INDEX idx_audit_records_account_id
    ON toji_active.audit_records (account_id);
CREATE INDEX idx_audit_records_resource_type_id
    ON toji_active.audit_records (resource_type, resource_id);
CREATE INDEX idx_audit_records_actor
    ON toji_active.audit_records (actor);
CREATE INDEX idx_audit_records_action
    ON toji_active.audit_records (action);
CREATE INDEX idx_audit_records_created_at
    ON toji_active.audit_records (created_at);
CREATE INDEX idx_audit_records_correlation_id
    ON toji_active.audit_records (correlation_id);

-- ── 11. oms_state (mutable-versioned, one active row per account) ───────────

CREATE TABLE toji_active.oms_state (
    oms_state_id    UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id      UUID            NOT NULL,
    status          TEXT            NOT NULL DEFAULT 'INITIALIZING' CHECK (status IN (
                        'INITIALIZING', 'READY', 'ACTIVE', 'PAUSED',
                        'DRAINING', 'STOPPED', 'ERROR'
                    )),
    open_order_count INTEGER        NOT NULL DEFAULT 0 CHECK (open_order_count >= 0),
    pending_fills   INTEGER         NOT NULL DEFAULT 0 CHECK (pending_fills >= 0),
    last_heartbeat  TIMESTAMPTZ     NOT NULL DEFAULT now(),
    state_data      JSONB           NOT NULL DEFAULT '{}'::jsonb,
    version         INTEGER         NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX uq_oms_state_active_account
    ON toji_active.oms_state (account_id)
    WHERE status NOT IN ('STOPPED', 'ERROR');

CREATE INDEX idx_oms_state_status ON toji_active.oms_state (status);

-- ── 12. positions (mutable-versioned) ───────────────────────────────────────

CREATE TABLE toji_active.positions (
    position_id     UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id      UUID            NOT NULL,
    symbol          TEXT            NOT NULL,
    side            TEXT            NOT NULL CHECK (side IN ('LONG', 'SHORT', 'FLAT')),
    quantity         NUMERIC(20,8)   NOT NULL DEFAULT 0,
    average_entry_price NUMERIC(20,8) NOT NULL DEFAULT 0,
    realized_pnl    NUMERIC(20,8)   NOT NULL DEFAULT 0,
    unrealized_pnl  NUMERIC(20,8)   NOT NULL DEFAULT 0,
    cost_basis      NUMERIC(20,8)   NOT NULL DEFAULT 0,
    market_value    NUMERIC(20,8)   NOT NULL DEFAULT 0,
    metadata        JSONB           NOT NULL DEFAULT '{}'::jsonb,
    version         INTEGER         NOT NULL DEFAULT 1 CHECK (version > 0),
    opened_at       TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX uq_positions_account_symbol
    ON toji_active.positions (account_id, symbol);

CREATE INDEX idx_positions_account_id ON toji_active.positions (account_id);
CREATE INDEX idx_positions_symbol ON toji_active.positions (symbol);
CREATE INDEX idx_positions_side ON toji_active.positions (side);

-- ── 13. position_updates (append-only) ──────────────────────────────────────

CREATE TABLE toji_active.position_updates (
    update_id       UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    position_id     UUID            NOT NULL REFERENCES toji_active.positions(position_id),
    account_id      UUID            NOT NULL,
    fill_id         UUID            REFERENCES toji_active.fills(fill_id),
    symbol          TEXT            NOT NULL,
    update_type     TEXT            NOT NULL CHECK (update_type IN ('OPEN', 'INCREASE', 'DECREASE', 'CLOSE', 'ADJUSTMENT')),
    quantity_change  NUMERIC(20,8)   NOT NULL,
    price           NUMERIC(20,8)   NOT NULL,
    realized_pnl    NUMERIC(20,8)   NOT NULL DEFAULT 0,
    position_after  JSONB           NOT NULL DEFAULT '{}'::jsonb,
    metadata        JSONB           NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE INDEX idx_position_updates_position_id
    ON toji_active.position_updates (position_id);
CREATE INDEX idx_position_updates_account_id
    ON toji_active.position_updates (account_id);
CREATE INDEX idx_position_updates_fill_id
    ON toji_active.position_updates (fill_id);
CREATE INDEX idx_position_updates_symbol
    ON toji_active.position_updates (symbol);
CREATE INDEX idx_position_updates_created_at
    ON toji_active.position_updates (created_at);

-- ── 14. portfolio_snapshots (append-only) ───────────────────────────────────

CREATE TABLE toji_active.portfolio_snapshots (
    snapshot_id     UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id      UUID            NOT NULL,
    total_equity    NUMERIC(20,8)   NOT NULL,
    cash_balance    NUMERIC(20,8)   NOT NULL,
    total_market_value NUMERIC(20,8) NOT NULL,
    total_unrealized_pnl NUMERIC(20,8) NOT NULL DEFAULT 0,
    total_realized_pnl NUMERIC(20,8) NOT NULL DEFAULT 0,
    position_count  INTEGER         NOT NULL DEFAULT 0,
    positions_data  JSONB           NOT NULL DEFAULT '[]'::jsonb,
    risk_metrics    JSONB           NOT NULL DEFAULT '{}'::jsonb,
    metadata        JSONB           NOT NULL DEFAULT '{}'::jsonb,
    snapshot_at     TIMESTAMPTZ     NOT NULL DEFAULT now(),
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE INDEX idx_portfolio_snapshots_account_id
    ON toji_active.portfolio_snapshots (account_id);
CREATE INDEX idx_portfolio_snapshots_snapshot_at
    ON toji_active.portfolio_snapshots (snapshot_at);
CREATE INDEX idx_portfolio_snapshots_account_snapshot
    ON toji_active.portfolio_snapshots (account_id, snapshot_at);

-- ── 15. ledger_entries (append-only, double-entry) ──────────────────────────

CREATE TABLE toji_active.ledger_entries (
    entry_id        UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id      UUID            NOT NULL,
    ledger_type     TEXT            NOT NULL CHECK (ledger_type IN ('DEBIT', 'CREDIT')),
    entry_type      TEXT            NOT NULL CHECK (entry_type IN (
                        'TRADE', 'COMMISSION', 'FUNDING', 'WITHDRAWAL',
                        'DEPOSIT', 'ADJUSTMENT', 'FEE', 'DIVIDEND', 'INTEREST'
                    )),
    amount          NUMERIC(20,8)   NOT NULL,
    currency        TEXT            NOT NULL DEFAULT 'USD',
    balance_after   NUMERIC(20,8)   NOT NULL,
    reference_type  TEXT,
    reference_id    UUID,
    description     TEXT            NOT NULL DEFAULT '',
    metadata        JSONB           NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE INDEX idx_ledger_entries_account_id
    ON toji_active.ledger_entries (account_id);
CREATE INDEX idx_ledger_entries_entry_type
    ON toji_active.ledger_entries (entry_type);
CREATE INDEX idx_ledger_entries_reference
    ON toji_active.ledger_entries (reference_type, reference_id);
CREATE INDEX idx_ledger_entries_created_at
    ON toji_active.ledger_entries (created_at);

-- ── 16. outbox_messages (mutable — status transitions only) ─────────────────

CREATE TABLE toji_active.outbox_messages (
    message_id      UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id      UUID            NOT NULL,
    topic           TEXT            NOT NULL,
    event_type      TEXT            NOT NULL,
    payload         JSONB           NOT NULL,
    status          TEXT            NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'PROCESSING', 'SENT', 'FAILED', 'DEAD_LETTER')),
    retry_count     INTEGER         NOT NULL DEFAULT 0 CHECK (retry_count >= 0),
    max_retries     INTEGER         NOT NULL DEFAULT 3,
    last_error      TEXT,
    correlation_id  UUID,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    sent_at         TIMESTAMPTZ
);

CREATE INDEX idx_outbox_messages_status
    ON toji_active.outbox_messages (status);
CREATE INDEX idx_outbox_messages_account_id
    ON toji_active.outbox_messages (account_id);
CREATE INDEX idx_outbox_messages_topic
    ON toji_active.outbox_messages (topic);
CREATE INDEX idx_outbox_messages_created_at
    ON toji_active.outbox_messages (created_at);
CREATE INDEX idx_outbox_pending
    ON toji_active.outbox_messages (status, created_at)
    WHERE status IN ('PENDING', 'FAILED');

-- ── Restore search_path ─────────────────────────────────────────────────────

RESET search_path;

COMMIT;
