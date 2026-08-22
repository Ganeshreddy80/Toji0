# SPRINT-002 DATABASE BASELINE
**Classification:** CTO Evidence Gate — Phase 1 Discovery  
**Date:** 2026-08-08  
**Sprint:** 002 — Persistence & Runtime Truth  
**Status:** DISCOVERY COMPLETE — pending CTO approval for Phase 2 implementation

---

## Audit Methodology

All findings trace to actual source code files. No inference from filenames.  
Every claim has a line-level file reference.

---

## 1. Database Configuration

### 1.1 Environment Variables

| Variable | Value in `.env` | Used By |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://toji:password@toji-postgres:5432/toji` | `configuration_boot.py` URL parser |
| `DATABASE_MODE` | `DEV` | Test/validate scripts only (not read by `connection.py`) |
| `TOJI_MODE` | `PAPER` | `connection.py` SQLite fallback / halt gate |
| `REDIS_URL` | `redis://redis:6379/0` | Redis cache (separate subsystem) |
| `FORCE_DB_FALLBACK_CHECK` | _(unset)_ | `connection.py` test override |

**Evidence:** `.env:58-68`

### 1.2 Configuration Loading Chain

```
scripts/run_paper_trading.py
  └─ bootstrap_platform()                         [platform/bootstrap.py:13]
       └─ PlatformApplication.boot()              [platform/application.py:17]
            └─ PlatformStartupCoordinator.boot_platform()  [platform/startup.py:29]
                 ├─ Step 1: ConfigurationBootloader.load_configuration()
                 │    ├─ Primary: R51 ConfigManager → CentralConfig pydantic model
                 │    └─ Fallback dict + DATABASE_URL env parse [configuration_boot.py:43-59]
                 │         └─ urlparse strips "postgresql+asyncpg://" → host/port/dbname/user/password
                 ├─ Step 2: DatabaseLifecycleManager(config["database"]).connect()
                 │    └─ DatabaseConnection.initialize()   [database_boot.py:26-31]
                 │         ├─ Builds pg_url f"postgresql://{user}:{password}@{host}:{port}/{dbname}"
                 │         ├─ create_engine() with pool params
                 │         └─ run_migrations(engine) → Base.metadata.create_all()
                 └─ Step 3: ServiceRegistry.register_service("Database", db_manager)
```

**Key finding:** The `DATABASE_URL` uses `postgresql+asyncpg://` scheme but this is **stripped before parsing** (`configuration_boot.py:47`). The active engine uses **synchronous `postgresql://` dialect** with `psycopg2-binary`. `asyncpg` is listed in `requirements.txt` but is **not used** by the active connection code path.

**Pytest override:** `configuration_boot.py:62-67` remaps host to `localhost` and forces `dbname=toji_v1` / `user=postgres`. This differs from the Docker Compose database (`toji` / `toji`).

---

## 2. Schema Definition

**Migration mechanism:** `Base.metadata.create_all(bind=engine)` — `run_migrations()` called at boot by `DatabaseLifecycleManager.connect()` line 30.

**No Alembic config exists in the repository.** The `alembic` package is installed in `.venv` only. There are no `alembic.ini`, `env.py`, `versions/` directory, or migration scripts anywhere in the source tree.

### 2.1 Defined Tables (17 total)

**Source:** `research_platform/persistence/postgres/migrations.py:17-173`

| Table | ORM Model | Primary Key | Financial? |
|---|---|---|---|
| `orders` | `OrderModel` | `order_id` (String) | No |
| `trades` | `TradeModel` | `trade_id` (String) | **Yes — fills** |
| `positions` | `PositionModel` | `position_id` (String) | **Yes — open positions** |
| `trade_journals` | `TradeJournalModel` | `journal_id` (String) | **Yes — per-trade record** |
| `daily_journals` | `DailyJournalModel` | `date` (String) | **Yes** |
| `trade_statistics` | `TradeStatisticsModel` | `stats_id` (String) | **Yes** |
| `trade_ledger` | `TradeLedgerModel` | `trade_id` (String) | **Yes — AUTHORITATIVE** |
| `portfolios` | `PortfolioModel` | `portfolio_id` (String) | No |
| `analytics` | `AnalyticsModel` | `analytics_id` (String) | No |
| `strategies` | `StrategyModel` | `strategy_id` (String) | No |
| `experiments` | `ExperimentModel` | `experiment_id` (String) | No |
| `monitoring_status` | `MonitoringStatusModel` | `service_name` (String) | No |
| `monitoring_alerts` | `MonitoringAlertModel` | `alert_id` (String) | No |
| `monitoring_metrics` | `MonitoringMetricModel` | `metric_name` (String) | No |
| `reports` | `ReportModel` | `report_id` (String) | No |
| `configurations` | `ConfigurationModel` | `key` (String) | No |
| `jobs` | `JobModel` | `job_id` (String) | No |

### 2.2 Schema Gaps

| Gap | Impact |
|---|---|
| No `NOT NULL` constraints on financial columns | ORM can write null quantity/price to `trades`, `positions`, `trade_ledger` |
| Financial amounts stored as `Float` not `Decimal` | Floating-point rounding accumulates across fills (DB-007) |
| No foreign keys (`trades.order_id` → `orders.order_id`, etc.) | Referential integrity not enforced at DB layer |
| No indexes beyond primary key | Full-table scans on `symbol`, `status` queries |
| No timestamps on `orders`, `positions` tables | Cannot audit order lifecycle timing |
| Schema evolution requires drop-and-recreate (no Alembic) | Zero-downtime schema changes not possible |

---

## 3. Persistence Trace — One Complete Paper Trade

### 3.1 Write Path (fully source-traced)

```
run_paper_trading.py: OmsCore.submit_order()           [line 810]
  └─ PaperExecutionRouter._route()
       └─ PaperTradingOrchestrator.submit_paper_order()
            └─ PaperBrokerAdapter → PaperExchange.fill()
                 └─ EventBus.publish(PaperOrderFilled)
                      └─ AccountingService.on_fill()    [accounting_service.py:98]
                           │
                           ├─ [in-memory] PositionValuationEngine.on_fill/on_close()
                           ├─ [in-memory] PortfolioAccountingEngine.apply_fill()
                           ├─ [in-memory] LedgerRepository.append(entry)
                           │
                           └─ ServiceRegistry.get_service("Database")  [line 237]
                                IF db is not None:
                                  ├─ PostgresTradeRepository.save_trade()       → `trades`
                                  ├─ PostgresPositionRepository.save_position() → `positions`
                                  └─ PostgresLedgerRepository.save_entry()      → `trade_ledger`
```

**Evidence:** `research_platform/portfolio_accounting/accounting_service.py:236-290`

### 3.2 DB Write Conditionality

All three SQL writes are gated on `if db:` (line 238). If `ServiceRegistry.get_service("Database")` returns `None` (boot failure or missing registration), **all three writes are silently skipped with no WARNING log at trade time**. The trade proceeds in-memory only.

### 3.3 Three-Write Non-Atomicity — CRITICAL (DB-001)

```python
# accounting_service.py:239-290 (simplified)
try:
    trade_repo.save_trade(...)      # separate session_scope — commits independently
    pos_repo.save_position(...)     # separate session_scope — commits independently
    ledger_repo.save_entry(...)     # separate session_scope — commits independently
except Exception as db_err:
    logger.error(...)
```

Each write opens and commits its own `session_scope()`. If write 2 (`positions`) raises, write 1 (`trades`) is already committed. Write 3 (`trade_ledger`) then executes in an inconsistent state.

The `TransactionManager` class exists at `persistence/postgres/transaction_manager.py` and provides `transaction()` context manager — but it is **NOT used in the `on_fill()` critical path**.

### 3.4 OMS Order Status Persistence

`AccountingService.on_fill()` also transitions the OMS order to `FILLED` status in PostgreSQL (lines 187-234). This uses the OMS-internal repository (`oms.repository.save_order()`), which is separate from the `persistence/repositories/` layer.

### 3.5 Secondary Persistence (Non-Authoritative)

`TradeMemoryEngine` writes to `data/trade_memory.json` (local flat file). Called from `run_paper_trading.py:892-908`. Stores the entry leg with `pnl=0.0`. **Not the financial source of truth.**

---

## 4. Runtime State Map

| State Component | Storage | Written to DB? | Survives Restart? |
|---|---|---|---|
| Portfolio equity / cash | `PortfolioAccountingEngine` RAM | **No** | **No** |
| Open position valuations | `PositionValuationEngine` RAM dict | Written to `positions` on fill | **No — RAM only** |
| Trade fill history | `LedgerRepository._entries` RAM list + `trade_ledger` | Yes (if DB connected) | Yes (DB) |
| Raw fill records | None in-memory | Written to `trades` on fill | Yes (DB) |
| Order status | OMS internal repo + `orders` table | Yes | Yes (DB) |
| Trade journal records | `TradeJournal` RAM + `trade_journals` | Yes | Yes (DB) |
| Risk state (equity, drawdown) | `AccountingService` RAM | **No** | **No** |
| Pattern memory | `data/trade_memory.json` flat file | Always (local) | Yes (local disk) |

**Critical gap (DB-002):** On process restart, `PortfolioAccountingEngine` initializes with `initial_balance=100_000.0`. It does **NOT** reload positions or ledger from PostgreSQL. The in-memory portfolio state is always reset to zero-position baseline — making "one complete paper trade" visible per session only, not across restarts.

---

## 5. SQLite Fallback Behavior

**Evidence:** `research_platform/persistence/postgres/connection.py:67-101`

| Condition | Behavior |
|---|---|
| `TOJI_MODE=DEV` | SQLite `:memory:` fallback permitted |
| Running under pytest, `FORCE_DB_FALLBACK_CHECK` not set | SQLite `:memory:` permitted |
| `TOJI_MODE=PAPER/PROD`, not pytest | `RuntimeError` raised → Telegram alert → process exits |
| `TOJI_MODE=PAPER/PROD`, `FORCE_DB_FALLBACK_CHECK=true` | Same — RuntimeError + Telegram + halt |

SQLite fallback uses `StaticPool` (single shared in-memory connection). All data lost on process exit.

**`DatabaseRecoveryManager` inconsistency (DB-003):**  
`database_recovery.py:27` returns `True` (success) when `Database` is not registered — treating "no database" as valid.  
`database_recovery.py:45` returns `True` after a PostgreSQL failure — masking connectivity degradation.  
Both failure modes return success to the caller.

---

## 6. Transaction Correctness

**Session lifecycle:**
- **Writes:** `session_scope()` context manager → auto-commit on exit, rollback on exception
- **Reads:** Direct `get_session()` → manual close in `finally` (NOT inside a `session_scope`)
- **Re-entrancy:** `session_scope()` re-enters without opening new session if `_local.active_session` is set

**Thread safety:** `BaseRepository._db_lock` is a **class-level `threading.RLock`** — serializes ALL repository I/O across ALL repository instances in the process.

**Known correctness risks:**

| Risk | Evidence | Impact |
|---|---|---|
| Three writes in `on_fill()` not wrapped in single transaction | `accounting_service.py:249-286` | Partial DB state on any individual write failure |
| `TransactionManager` unused in critical write path | `transaction_manager.py` exists but never called from `on_fill()` | Atomicity guarantee not applied |
| Reads not in `session_scope` — potential stale reads | `base_repository.py:34-41` | Read may miss uncommitted concurrent write |
| Re-entrant `session_scope` shares parent session | `session.py:37-38` | Nested write commits with the outer scope |

---

## 7. PostgreSQL Readiness

### 7.1 Connection Pool Parameters

**Evidence:** `connection.py:34-40`

```python
engine = create_engine(
    pg_url,
    pool_size=20,
    max_overflow=10,
    pool_timeout=5,
    connect_args={"connect_timeout": 2}
)
```

| Parameter | Value | Gap |
|---|---|---|
| `pool_size` | 20 | Adequate for paper trading |
| `max_overflow` | 10 | Max 30 simultaneous connections |
| `pool_timeout` | 5s | Wait time for pool connection |
| `connect_timeout` | 2s | TCP connection timeout |
| `pool_pre_ping` | **MISSING** | Dead connections not checked before use (DB-004) |
| `pool_recycle` | **MISSING** | Stale connections not recycled after network events |

### 7.2 Reconnection Behavior

`DatabaseRecoveryManager.recover_database()` calls `db.connect()` to reconnect (line 32). However, `DatabaseLifecycleManager.connect()` at line 25 is a no-op when `self._connection is None` is false (connection already initialized). **A dead engine is never disposed and recreated.** True reconnection is not implemented (DB-005).

### 7.3 Docker Compose vs Test Mismatch

| Context | Database | User |
|---|---|---|
| Docker Compose (`docker-compose.yml:10-12`) | `toji` | `toji` |
| pytest override (`configuration_boot.py:65-66`) | `toji_v1` | `postgres` |

Tests run against a different database than deployment. Persistence tests exercise SQLite not the Docker PostgreSQL database (DB-008).

---

## 8. S3 / External Object Storage Boundaries

**No S3 implementation exists in production code.**

Evidence searched:
- `boto3` appears only in test assertion lists as a **forbidden import** (`test_operations_platform.py:700`, `test_deployment_platform.py:621`)
- No `AWS_*`, `BUCKET_NAME`, or S3 credentials in `.env` or `.env.example`
- No `s3_client`, `S3Bucket`, `boto3.client` in any production Python file

**Single file-system persistence:** `data/trade_memory.json` (TradeMemoryEngine, local disk, non-authoritative).

Sprint 002 Phase 2 must define S3 boundary explicitly if cloud-based archival is intended.

---

## 9. Resource Impact

| Resource | Details |
|---|---|
| Max PostgreSQL connections | 30 (pool_size=20 + max_overflow=10) per process |
| `LedgerRepository._entries` | Unbounded list — grows for full process lifetime |
| `PerformanceEngine._trades` | Unbounded list — all trade records in RAM |
| Thread contention | Single class-level RLock serializes ALL repository I/O |

---

## 10. Security

| Area | Finding | Risk |
|---|---|---|
| SQL injection | All queries use SQLAlchemy ORM parameterized methods — no raw SQL string interpolation found | **Low** |
| Credential storage | `docker-compose.yml:61-66` contains DB password in plaintext env section | **Medium** |
| `.env` git exclusion | Confirmed excluded by `.gitignore` | **Low** |
| Connection string | Password interpolated from config dict — not hardcoded in source | **Low** |
| Exposed API keys in `.env` | Binance demo keys, OpenRouter key, Telegram token present | **Medium (demo keys)** |

---

## 11. Failure Behavior

| Scenario | Actual Behavior |
|---|---|
| PostgreSQL down at boot, PAPER mode | RuntimeError → Telegram alert → process exit |
| PostgreSQL down at boot, DEV/pytest | SQLite :memory: fallback → platform boots, no persistence |
| DB write fails during `on_fill()` | Exception caught + logged; trade proceeds in-memory; partial DB state possible |
| `ServiceRegistry` has no "Database" | All three SQL writes silently skipped; no ERROR log at trade time |
| `DatabaseRecoveryManager` called with failing DB | Returns `True` — failure masked |
| Process restart with open positions | `PortfolioAccountingEngine` resets to `initial_balance=100_000.0`; existing DB positions not reloaded |

---

## 12. Testing Coverage

| File | Coverage | DB Backend |
|---|---|---|
| `research_platform/tests/test_persistence.py` | CRUD all 10 repos; transaction commit/rollback; concurrency | SQLite :memory: (PostgreSQL fallback) |
| `research_platform/tests/test_sprint2_consistency.py` | LedgerRepository, OrderStateMachine, PositionManager | SQLite :memory: |

### Testing Gaps

| Gap | Risk |
|---|---|
| Three-write atomicity in `on_fill()` — no test for partial failure scenario | **CRITICAL** |
| Process restart + state rehydration from `positions` / `trade_ledger` tables | **HIGH** |
| PostgreSQL-specific JSON type behavior differs from SQLite JSON | **MEDIUM** |
| `DatabaseRecoveryManager` failure masking — no test for `return True` on failure | **MEDIUM** |
| `pool_pre_ping` / stale connection detection | **MEDIUM** |
| DB writes silently skipped when `ServiceRegistry` has no "Database" | **MEDIUM** |

---

## Summary: Critical Findings for Phase 2

| ID | Finding | Severity | Required Action |
|---|---|---|---|
| DB-001 | Three writes in `on_fill()` NOT atomic — partial DB state on failure | **CRITICAL** | Wrap in single `TransactionManager.transaction()` |
| DB-002 | Portfolio state NOT rehydrated from DB on restart | **HIGH** | Implement startup bootstrap: reload `positions` + `trade_ledger` |
| DB-003 | `DatabaseRecoveryManager` returns `True` on all failure modes | **HIGH** | Return `False` on failure; propagate to caller |
| DB-004 | Missing `pool_pre_ping` / `pool_recycle` | **MEDIUM** | Add to `create_engine()` |
| DB-005 | Reconnection no-op when `_connection` already initialized | **MEDIUM** | Dispose + recreate engine on recovery |
| DB-006 | No Alembic — schema is `create_all` only | **MEDIUM** | Initialize Alembic for versioned migrations |
| DB-007 | Financial columns are `Float` not `Decimal` | **MEDIUM** | Document or fix before live trading |
| DB-008 | pytest dbname `toji_v1` != Docker dbname `toji` | **MEDIUM** | Align test and production DB names |
| DB-009 | Silent skip of DB writes when "Database" not in registry | **MEDIUM** | Add explicit ERROR log at write gate |
| DB-010 | `LedgerRepository._entries` grows unbounded in RAM | **LOW** | Define eviction or size cap |

---

*SPRINT-002-DATABASE-BASELINE.md — Phase 1 Discovery Complete*  
*Produced by: Implementation Engineer under TOJI CTO Architecture*  
*All findings source-code verified — no inference from filenames*
