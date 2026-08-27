# DATA-001-P0-03A — Active Authority Schema Foundation

> **Status**: Remediated (P0-03A-REMEDIATION)
> **Owner**: DATA team
> **Approval**: CTO authorized
> **Schema**: `toji_active` within existing `toji` database
> **Migration**: `0001_active_authority_foundation`

---

## Summary

This document records the architecture and design decisions for the
`toji_active` PostgreSQL schema — the authority for active-runtime
persistence in the Toji trading platform.

The schema lives inside the existing `toji` PostgreSQL database as a
dedicated schema namespace.  It does **not** represent a second database
and does **not** share tables with the research-platform (`public` schema).

---

## Seventh-File Resolution

**Finding**: `tests/persistence/__init__.py` was created as a necessary
Python package init for pytest to discover tests inside `tests/persistence/`.
Without it, `pytest` cannot import `tests/persistence/test_active_schema_manifest.py`
as a Python module on Python 3.12+.

**Decision**: Retain.  The file contains one comment line and zero logic.
It is within the `tests/persistence/` path family (authorized scope).
Standard Python toolchain convention requires it.  This is documented here
for CTO-level awareness.  No separate scope exception is required as it
is a toolchain artifact, not a production module.

---

## Checksum Policy

The `SchemaManifest` computes a **deterministic SHA-256 digest** of each
migration file's bytes on disk.  The `MigrationRunner` is the sole
checksum authority.

| Scenario | Runner behaviour |
|---|---|
| First application | Apply SQL; insert `schema_version` row with real checksum (replacing `__CHECKSUM_SELF__` sentinel) |
| Repeat — same checksum | Skip (idempotent) |
| Repeat — different checksum | **Fail closed** — `ChecksumMismatchError` |
| Duplicate version (different name) | DB `UNIQUE` on `version` rejects INSERT → `DuplicateVersionError` |

**Sentinel**: `__CHECKSUM_SELF__` in the migration SQL is replaced by
the `MigrationRunner` at apply time with the actual file checksum.  This
avoids the impossible self-referential checksum problem: the file's
checksum is computed from bytes-on-disk before replacement.

### Why not a checksum of checksum?
A migration file that embeds its own SHA-256 cannot be its own pre-image.
The sentinel pattern decouples the migration SQL from the checksum value:
the runner inserts the digest into `schema_version` after applying the SQL,
within the same transaction.

---

## Repeat / Mismatch Policy

Implemented in `MigrationRunner._apply_one()`:

```python
if row is not None:
    if row["checksum"] == entry.checksum:
        return  # already applied — skip
    raise ChecksumMismatchError(...)
```

The database `UNIQUE INDEX uq_schema_version_version` provides a secondary
defence: if two concurrent runners attempt first application simultaneously,
only one INSERT succeeds; the other receives an `IntegrityError`.

---

## Account Isolation Design

All tables carry `account_id UUID NOT NULL`.  Beyond that, child tables
reference parent tables via **composite foreign keys** that include
`account_id`, enforcing cross-account containment at the database level,
not only in application query filters.

| Child table | Composite FK | References |
|---|---|---|
| `order_intents` | `(account_id, request_id)` | `execution_requests (account_id, request_id)` |
| `routing_decisions` | `(account_id, intent_id)` | `order_intents (account_id, intent_id)` |
| `orders` | `(account_id, intent_id)` | `order_intents (account_id, intent_id)` |
| `orders` | `(account_id, decision_id)` | `routing_decisions (account_id, decision_id)` |
| `fills` | `(account_id, order_id)` | `orders (account_id, order_id)` |
| `execution_results` | `(account_id, request_id)` | `execution_requests (account_id, request_id)` |
| `execution_metrics` | `(account_id, request_id)` | `execution_requests (account_id, request_id)` |
| `position_updates` | `(account_id, position_id)` | `positions (account_id, position_id)` |
| `position_updates` | `(account_id, fill_id)` | `fills (account_id, fill_id)` |

Each parent table exposes the required composite unique index (e.g.
`uq_execution_requests_account_request`) that the FK reference requires.

---

## Idempotency Constraints

| Table | Constraint name | Key columns | Purpose |
|---|---|---|---|
| `execution_requests` | `uq_execution_requests_idempotency` | `(account_id, idempotency_key)` | Prevent duplicate submissions from the same caller |
| `orders` | `uq_orders_exchange_id_account_venue` | `(account_id, venue, exchange_order_id)` WHERE NOT NULL | Broker order identity — deduplicate exchange acks |
| `fills` | `uq_fills_exchange_fill_id` | `(account_id, order_id, exchange_fill_id)` WHERE NOT NULL | Broker fill identity — prevents double-booking |
| `position_updates` | `uq_position_updates_apply_key` | `(account_id, apply_key)` | Prevents double-application of fill→position |
| `ledger_entries` | `uq_ledger_entries_ref_idempotency` | `(account_id, reference_idempotency_key)` WHERE NOT NULL | Prevents duplicate ledger postings |
| `outbox_messages` | `uq_outbox_messages_event_id` | `(account_id, event_id)` | Stable event identity for at-least-once dedup |
| `schema_version` | `uq_schema_version_version` | `(version)` | Prevent duplicate migration versions |
| `oms_state` | `uq_oms_state_active_account` | `(account_id)` WHERE active | One active OMS per account |
| `positions` | `uq_positions_account_symbol` | `(account_id, symbol)` | One position record per (account, symbol) |

---

## Append-Only Enforcement

Append-only tables are protected at the **database level** using
PostgreSQL `RULE` statements with `DO INSTEAD NOTHING`.  This means
any `UPDATE` or `DELETE` issued by the runtime role — even directly
via `psql` — silently affects zero rows, regardless of application logic.

### Append-only tables

`schema_version`, `execution_requests`, `order_intents`,
`routing_decisions`, `fills`, `execution_results`, `execution_metrics`,
`execution_journal`, `audit_records`, `position_updates`,
`portfolio_snapshots`, `ledger_entries`.

### Mutable tables

`orders`, `oms_state`, `positions`, `outbox_messages` — these use
integer `version` columns for optimistic concurrency.

### Why RULE and not triggers?

PostgreSQL `BEFORE UPDATE` triggers fire after parsing, enabling
creative workarounds by sufficiently privileged roles.  `RULE ON UPDATE
DO INSTEAD NOTHING` rewrites the query at the parser/rewriter level,
making it impossible to `UPDATE` the table via normal DML regardless of
privilege level (short of `SUPERUSER` `ALTER RULE`).  This is the
strongest available enforcement short of column-level DDL or privilege
revocation, both of which require IAM changes outside this ticket's scope.

---

## Outbox Design

The `outbox_messages` table implements reliable at-least-once event
dispatch with worker-safe claim semantics.

### State transitions

```
PENDING ──► PROCESSING ──► SENT
                │
                ▼
             FAILED ──────► DEAD_LETTER
                │
                └──► PROCESSING  (retry if retry_count < max_retries)
```

### Key fields

| Field | Purpose |
|---|---|
| `event_id` | Stable caller-supplied UUID; deduplication identity per account |
| `aggregate_type` / `aggregate_id` | Domain aggregate identity for routing |
| `available_at` | Scheduling — worker ignores rows where `available_at > now()` |
| `lease_expires_at` / `leased_by` | Worker-safe claim; expired leases are reclaimable |
| `version` | Compare-and-set for concurrent worker races |
| `retry_count` / `max_retries` | Retry budget |

### Distinction: broker dispatch vs. domain event

- **Broker-dispatch command** (`topic` prefix `broker.*`): instructs the
  execution layer to submit an order to a venue.  One per intent/routing decision.
- **Post-commit domain event** (`topic` prefix `event.*`): announces what
  happened for downstream consumers (risk, reporting, audit).  Multiple per
  order lifecycle.

Both share the same outbox table and dispatch infrastructure.  The
`aggregate_type` field distinguishes them for routing.

---

## CHECK Constraints Added in Remediation

| Table | Constraint | Invariant |
|---|---|---|
| `orders` | `filled_quantity <= quantity` | Cannot over-fill an order |
| `fills` | `commission >= 0` | Non-negative commission |
| `execution_results` | `filled_quantity >= 0`, `total_commission >= 0` | Non-negative result fields |
| `ledger_entries` | `amount != 0` | No zero-value ledger lines |
| `portfolio_snapshots` | `position_count >= 0` | Non-negative position count |
| `positions` | `quantity >= 0`, `average_entry_price >= 0`, `cost_basis >= 0` | Non-negative position fields |
| `execution_requests` | Conditional `limit_price` check | LIMIT/STOP_LIMIT requires limit_price > 0 |
| `execution_requests` | Conditional `stop_price` check | STOP/STOP_LIMIT requires stop_price > 0 |
| `execution_metrics` | `fill_rate` in [0,1] | Valid fill rate range |
| `outbox_messages` | `max_retries >= 0` | Non-negative retry budget |

---

## Table Inventory

| # | Table | Pattern | Key fields |
|---|---|---|---|
| 1 | `schema_version` | Append-only | `version`, `checksum`, `component` |
| 2 | `execution_requests` | Append-only | `request_id`, `account_id`, `idempotency_key` |
| 3 | `order_intents` | Append-only | `intent_id`, `account_id`, `request_id` |
| 4 | `routing_decisions` | Append-only | `decision_id`, `account_id`, `intent_id` |
| 5 | `orders` | Mutable-versioned | `order_id`, `status`, `filled_quantity`, `version` |
| 6 | `fills` | Append-only | `fill_id`, `exchange_fill_id` |
| 7 | `execution_results` | Append-only | `result_id`, `status`, `filled_quantity` |
| 8 | `execution_metrics` | Append-only | `metric_id`, `metric_type`, `latency_ms` |
| 9 | `execution_journal` | Append-only | `entry_id`, `event_type`, `severity` |
| 10 | `audit_records` | Append-only | `audit_id`, `actor`, `action`, `resource_type` |
| 11 | `oms_state` | Mutable-versioned | `oms_state_id`, `status`, `version` |
| 12 | `positions` | Mutable-versioned | `position_id`, `symbol`, `quantity`, `version` |
| 13 | `position_updates` | Append-only | `update_id`, `apply_key`, `update_type` |
| 14 | `portfolio_snapshots` | Append-only | `snapshot_id`, `total_equity`, `position_count` |
| 15 | `ledger_entries` | Append-only | `entry_id`, `ledger_type`, `amount`, `reference_idempotency_key` |
| 16 | `outbox_messages` | Mutable (status) | `message_id`, `event_id`, `aggregate_type`, `available_at`, `lease_expires_at` |

---

## Compatibility Rules

1. **No migration may be modified after application** — `ChecksumMismatchError` enforces this.
2. **No table in `toji_active` may reference tables in `public`** — isolation boundary.
3. **No active-schema migration may ALTER, DROP, or TRUNCATE research-platform tables** — enforced by offline test.
4. **All new columns must have NOT NULL with a default or be explicitly nullable** — schema evolves forward.
5. **All timestamps must be `TIMESTAMPTZ`** — UTC convention, enforced by offline test.
6. **All primary keys must be UUID** — no SERIAL or BIGSERIAL.

---

## Risks and Remaining Work

| Risk | Severity | Status |
|---|---|---|
| Append-only RULE requires `SUPERUSER` to bypass | Low | Acceptable; documented |
| `position_updates.fill_id` FK is DEFERRABLE — deferred constraint not exercised in unit tests | Low | Integration test covers structural presence; deferred FK test is future scope |
| `execution_journal` has no FK to `execution_requests` (optional request_id) | Low | Intentional — journal entries can be cross-cutting |
| Privilege separation (toji_app role vs toji_readonly) not in scope for P0-03A | Medium | P0-03B / IAM scope |
| Migration not applied to production RDS | N/A | Out of scope for this ticket |
