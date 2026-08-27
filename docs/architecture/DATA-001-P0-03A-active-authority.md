# DATA-001-P0-03A — Active Authority Schema Foundation

> **Status**: Implemented
> **Owner**: DATA team
> **Approval**: CTO authorized
> **Schema**: `toji_active` within existing `toji` database
> **Migration**: `0001_active_authority_foundation`

---

## 1. Decision Context

The Toji platform requires durable persistence for active-runtime state
(execution, orders, fills, positions, portfolio, ledger, audit) that is
**separate from the research-platform tables**.

### Why a Dedicated Schema?

| Concern | Decision |
|---------|----------|
| Research vs. active isolation | `toji_active` schema — no cross-contamination |
| Single database | Same `toji` PostgreSQL database — no second RDS |
| Migration strategy | Explicit versioned SQL — no `create_all()` |
| Identifier consistency | UUID everywhere — no mixed UUID/string/integer |
| Timestamp consistency | UTC `TIMESTAMPTZ` everywhere |

---

## 2. Schema Ownership & Compatibility

### Ownership

- **Schema `toji_active`** is owned by the DATA team.
- All migrations require **CTO approval** before application to production RDS.
- Migration files live in `toji_platform/persistence/schema/versions/`.

### Compatibility Rules

1. **No cross-schema foreign keys** to research-platform tables.
2. **No modification** of existing research tables, migrations, or ORM models.
3. **No `create_all()`** — all schema changes are explicit versioned SQL.
4. **No runtime DDL** — application code must never execute DDL statements.
5. **Forward-only migrations** — each migration is append-only to the version history.

### Migration Versioning

Migrations follow the naming convention:

```
NNNN_<descriptive_name>.sql
```

Each migration is tracked by the `SchemaManifest` with:
- **Version**: 4-digit zero-padded number (e.g., `0001`)
- **Name**: descriptive snake_case name
- **Checksum**: deterministic SHA-256 of file contents
- **Component**: logical component (`active_authority`)

---

## 3. Table Inventory

### 3.1 Schema Version Tracking

| Table | `schema_version` |
|-------|-------------------|
| **Purpose** | Track applied migrations |
| **Mutability** | Append-only |
| **PK** | `id` (UUID) |
| **Key columns** | `version`, `name`, `checksum`, `component`, `applied_at`, `applied_by` |

### 3.2 Execution Pipeline

| Table | Purpose | Mutability |
|-------|---------|------------|
| `execution_requests` | Inbound execution requests from strategies | Append-only |
| `order_intents` | Desired order actions before routing decisions | Append-only |
| `routing_decisions` | Why/how orders were routed to venues | Append-only |
| `orders` | Broker-facing orders with lifecycle state | Mutable-versioned |
| `fills` | Exchange fill reports | Append-only |
| `execution_results` | Final execution outcomes | Append-only |
| `execution_metrics` | Latency, slippage, cost measurements | Append-only |
| `execution_journal` | Human-readable narrative entries | Append-only |

### 3.3 Audit & Compliance

| Table | Purpose | Mutability |
|-------|---------|------------|
| `audit_records` | System-wide audit trail | Append-only |

### 3.4 OMS & Positions

| Table | Purpose | Mutability |
|-------|---------|------------|
| `oms_state` | OMS state machine (one active row per account) | Mutable-versioned |
| `positions` | Current positions per account/symbol | Mutable-versioned |
| `position_updates` | Position change events | Append-only |

### 3.5 Portfolio & Ledger

| Table | Purpose | Mutability |
|-------|---------|------------|
| `portfolio_snapshots` | Point-in-time portfolio state | Append-only |
| `ledger_entries` | Double-entry accounting | Append-only |

### 3.6 Messaging

| Table | Purpose | Mutability |
|-------|---------|------------|
| `outbox_messages` | Transactional outbox for reliable messaging | Mutable (status transitions) |

---

## 4. Design Conventions

### 4.1 Identifiers

All primary keys are **UUID** type with `gen_random_uuid()` defaults.
No table uses string or integer primary keys.

### 4.2 Timestamps

All timestamp columns use **`TIMESTAMPTZ`** (timestamp with time zone).
`now()` is used as the default, which records UTC on a properly configured
PostgreSQL instance.

### 4.3 Versioning (Mutable Aggregates)

Tables that support updates (`orders`, `oms_state`, `positions`) include:

```sql
version  INTEGER  NOT NULL DEFAULT 1 CHECK (version > 0)
```

Application code must implement optimistic concurrency:
```sql
UPDATE toji_active.orders
SET status = 'FILLED', version = version + 1, updated_at = now()
WHERE order_id = $1 AND version = $2
```

### 4.4 Append-Only Policy

Tables marked "Append-only" (e.g., `fills`, `audit_records`, `execution_journal`)
are never updated or deleted at the application level. The schema does not
enforce this with triggers in the foundation migration, but application-level
repositories must enforce immutability.

### 4.5 Account Scoping

All domain tables include an `account_id UUID NOT NULL` column to support
multi-account isolation. Queries should always scope by `account_id`.

### 4.6 JSONB Metadata

Most tables include a `metadata JSONB NOT NULL DEFAULT '{}'::jsonb` column
for extensibility without schema changes.

---

## 5. Foreign Key Relationships

```
execution_requests
    └── order_intents (request_id)
            └── routing_decisions (intent_id)
                    └── orders (intent_id, decision_id)
                            └── fills (order_id)
    └── execution_results (request_id, order_id)
    └── execution_metrics (request_id, order_id)
    └── execution_journal (request_id, order_id)

positions
    └── position_updates (position_id)
            └── fills (fill_id)
```

---

## 6. Index Strategy

- **B-tree indexes** on all foreign key columns for join performance.
- **Status indexes** on tables with lifecycle states (`orders`, `oms_state`, `outbox_messages`).
- **Timestamp indexes** on `created_at` / `measured_at` for range queries.
- **Symbol indexes** on all tables containing `symbol` for market-data correlation.
- **Composite indexes** for common query patterns (e.g., `account_id + snapshot_at`).
- **Partial indexes** for business invariants:
  - `uq_oms_state_active_account`: one non-terminal OMS state per account
  - `idx_outbox_pending`: only pending/failed messages for outbox processing

---

## 7. Constraints Summary

| Constraint Type | Examples |
|----------------|----------|
| `CHECK (side IN ('BUY', 'SELL'))` | execution_requests, order_intents, orders, fills |
| `CHECK (side IN ('LONG', 'SHORT', 'FLAT'))` | positions |
| `CHECK (quantity > 0)` | execution_requests, order_intents, orders, fills |
| `CHECK (version > 0)` | orders, oms_state, positions |
| `CHECK (status IN (...))` | orders, oms_state, execution_results, outbox_messages |
| `CHECK (ledger_type IN ('DEBIT', 'CREDIT'))` | ledger_entries |
| `CHECK (entry_type IN (...))` | ledger_entries |
| `CHECK (severity IN (...))` | execution_journal |
| `UNIQUE (account_id, symbol)` | positions |
| `UNIQUE (account_id) WHERE status NOT IN (...)` | oms_state (partial) |
| `UNIQUE (version)` | schema_version |

---

## 8. Migration Safety

The foundation migration is designed to be safe:

- **Idempotent schema creation**: `CREATE SCHEMA IF NOT EXISTS`
- **Transactional**: wrapped in `BEGIN`/`COMMIT`
- **No destructive operations**: no `DROP`, `TRUNCATE`, `ALTER` on existing objects
- **No privilege changes**: no `GRANT`, `REVOKE`, `CREATE ROLE`
- **No secrets**: no passwords, database URLs, AWS credentials, or API keys
- **Scoped search path**: `SET search_path` restored with `RESET search_path`

---

## 9. Testing Strategy

### Offline Contract Tests

`tests/persistence/test_active_schema_manifest.py` — Pure Python tests that:
- Validate schema identity and component
- Verify migration discovery and checksum determinism
- Assert all 16 required tables in SQL
- Check required columns, constraints, indexes
- Scan for secrets
- Verify research-table isolation
- Verify no `create_all()` usage

### Integration Tests

`tests/integration/test_active_schema_postgres.py` — Against disposable PostgreSQL:
- Apply migration
- Introspect schema, tables, columns, PKs, FKs, unique constraints, indexes, CHECKs
- Verify schema_version record
- Verify research schema not modified
- Verify clean teardown

---

## 10. What This Task Does NOT Do

- Does **not** modify `boot.py` or `kernel.py`
- Does **not** connect active runtime to PostgreSQL
- Does **not** modify OMS behavior
- Does **not** apply migration to production RDS
- Does **not** create repositories or data access code
- Does **not** modify research-platform tables or migrations
- Does **not** certify PostgreSQL as the authority

These are deferred to subsequent tasks (P0-03B and beyond).
