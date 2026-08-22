# SPRINT 002 PHASE 3 — AUTHORITATIVE STATE REHYDRATION PLAN & AUDIT

**Author:** TOJI CTO / Lead Architect  
**Date:** 2026-08-09  
**Status:** PROPOSED (Awaiting CTO Implementation Approval)  
**Governance:** Master Architecture Governance — Sprint 002 Phase 3 Gate  

---

## EXECUTIVE SUMMARY

Sprint 002 Phase 3 establishes **Authoritative State Rehydration** for the TOJI trading platform. Following the successful completion and verification of atomic multi-table PostgreSQL transactions in Phase 2B (covering `trades`, `positions`, and `trade_ledger` on Neon PostgreSQL), Phase 3 guarantees that upon any process restart, crash recovery, or system boot, TOJI rehydrates its complete in-memory portfolio state from PostgreSQL before executing market ticks or risk checks.

This document serves as the mandatory Phase 3 Audit, State Contract, Rehydration Design, Fail-Closed Definition, and Test Plan. **No source code modifications will occur until this plan receives formal CTO approval.**

---

## 1. PHASE 3A — CURRENT STATE AUDIT

A rigorous audit of the current working tree (`main` / Sprint 002 Phase 2B baseline) was conducted. The table below details the initialization, call graph, line ranges, current behavior, and reachability for all 16 target lifecycle components.

| Component / Subsystem | File Path | Line Range | Class / Function | Current Behavior | Caller | Callee | Runtime Reachability | Evidence / Source |
|---|---|---|---|---|---|---|---|---|
| **1. AccountingService Lifecycle** | `research_platform/portfolio_accounting/accounting_service.py` | 32–52 | `AccountingService.__init__` | Instantiates clean in-memory engines (`PositionValuationEngine`, `PortfolioAccountingEngine(initial_balance)`, `PerformanceEngine`, `LedgerRepository`, `TradeJournal`, `PositionHistory`). **Does NOT load existing state from DB.** | `PortfolioAccountingPlugin.initialize()` | Engine constructors | Reached at platform boot (Priority 29.5) | `accounting_service.py:32-52` |
| **2. PositionValuationEngine Init** | `research_platform/portfolio_accounting/position_valuation_engine.py` | 33–37 | `PositionValuationEngine.__init__` | Initializes `self._positions = {}` and `self._history = []`. Starts with zero open positions regardless of DB contents. | `AccountingService.__init__` | `threading.RLock()` | Reached when `AccountingService` boots | `position_valuation_engine.py:33-37` |
| **3. PortfolioAccountingEngine Init** | `research_platform/portfolio_accounting/portfolio_accounting_engine.py` | 28–40 | `PortfolioAccountingEngine.__init__` | Initializes `_cash_balance = initial_balance` ($100,000 default), `_realized_pnl = 0.0`, `_fees = 0.0`, `_snapshot = None`. Starts clean. | `AccountingService.__init__` | `threading.RLock()` | Reached when `AccountingService` boots | `portfolio_accounting_engine.py:28-40` |
| **4. MetricsEngine Init** | `research_platform/portfolio_accounting/metrics_engine.py` | 27–34 | `MetricsEngine.__init__` | Initializes `_trades = []`, `_equity_curve = []`, `_peak_equity = 0.0`, `_max_drawdown = 0.0`. | `PerformanceEngine.__init__` | `threading.RLock()` | Reached when `AccountingService` boots | `metrics_engine.py:27-34` |
| **5. PerformanceEngine Init** | `research_platform/portfolio_accounting/performance_engine.py` | 16–17 | `PerformanceEngine` | Inherits from `MetricsEngine`. Adds Sortino, rolling volatility, and loss rate calculations. | `AccountingService.__init__` | `MetricsEngine.__init__` | Reached when `AccountingService` boots | `performance_engine.py:16-17` |
| **6. RuntimeStateManager Init** | `toji_platform/runtime/state.py` | 54–96, 306–342 | `RuntimeStateManager.load` | Manages process state. Lines 306–342 run a double-checked startup DB sync counting rows in `orders` and `trades` for telemetry counters (`self.orders_created`, `self.trades_filled`). **Does NOT rehydrate financial portfolio balance or positions into `AccountingService`.** | `runtime_supervisor.py` & `PaperRunner` | `PostgresOrderRepository`, `PostgresTradeRepository` | Reached at process start | `state.py:306-342` |
| **7. Trade Journal Init** | `research_platform/portfolio_accounting/trade_journal.py` | 23–26 | `TradeJournal.__init__` | Initializes `_records = []`. Starts empty in memory. | `AccountingService.__init__` | `threading.RLock()` | Reached when `AccountingService` boots | `trade_journal.py:23-26` |
| **8. OMS Core / Orchestrator Init** | `research_platform/oms/oms_core.py` | 31–39 | `OmsCore.__init__` | Initializes `OMSRepository` (in-memory order/fill dicts) and `OrderStateMachine`. OMS repository stores transient runtime order states. | `OmsPlugin.initialize()` | `OMSRepository`, `OrderStateMachine` | Reached at platform boot (Priority 13) | `oms_core.py:31-39` |
| **9. Risk State Init** | `research_platform/risk_management/orchestrator.py` | 53–70 | `RiskManagementOrchestrator.__init__` | Initializes `RiskRepository`, `KillSwitch`, and 11 risk sub-engines (`PositionRiskEvaluator`, `PortfolioRiskEvaluator`, `ComplianceEngine`, etc.). Risk checks evaluate compliance against dynamic parameters. | `RiskManagementPlugin.initialize()` | Sub-engine constructors | Reached at platform boot (Priority 11) | `orchestrator.py:53-70` |
| **10. Database Boot Sequence** | `research_platform/platform/database_boot.py` | 23–34 | `DatabaseLifecycleManager.connect` | Instantiates `DatabaseConnection(config)`, calls `initialize()` (SQLAlchemy engine & pool creation), and executes `run_migrations(engine)` (`CREATE TABLE IF NOT EXISTS`). | `PlatformStartupCoordinator.boot_platform()` | `DatabaseConnection`, `run_migrations` | Reached at Step 2 of platform boot sequence | `database_boot.py:23-34` |
| **11. PostgreSQL Repository Init** | `research_platform/persistence/repositories/*` | Entire dir | Repositories (`PostgresPositionRepository`, `PostgresTradeRepository`, `PostgresLedgerRepository`) | Inherit from `BaseRepository(session_manager, Model)`. Wraps SQLAlchemy session operations. | `AccountingService.on_fill` & API handlers | `DatabaseSessionManager` | Reached on demand during DB writes/reads | `position_repository.py:13-18`, `ledger_repository.py:12-16` |
| **12. Existing Repository Read Methods** | `position_repository.py:36-56`, `ledger_repository.py:50-85`, `trade_repository.py:121-125` | Various | `get_position`, `list_positions`, `get_entry`, `list_entries`, `list_trades` | `list_positions()` reads all rows from `positions` table. `list_entries()` reads all rows from `trade_ledger` table. `list_trades()` reads all rows from `trades` table. | Application code / Tests | `BaseRepository.list_all()` | Active in codebase | `position_repository.py:47-56`, `ledger_repository.py:68-85` |
| **13. Existing Repository Write Methods** | `position_repository.py:19-34`, `ledger_repository.py:18-48`, `trade_repository.py:96-119` | Various | `save_position`, `delete`, `save_entry`, `save_trade` | `save_position()` upserts row in `positions`. `delete()` removes row in `positions`. `save_entry()` upserts row in `trade_ledger`. Executed atomically inside `tx_mgr.transaction()` in `on_fill()`. | `AccountingService.on_fill()` | `BaseRepository.create/update` | Reached on every order fill event | `accounting_service.py:266-306` |
| **14. Existing Restart / Recovery Mechanisms** | `research_platform/recovery/database_recovery.py` | 19–64 | `DatabaseRecoveryManager.recover_database` | Tests DB connectivity (`SELECT 1`) via `reconnect()`. If connection fails, returns `False` (fail-closed guard added in Phase 2A/2B). **Does NOT rehydrate domain state.** | `RecoveryPlugin` | `DatabaseConnection.reconnect()` | Reached during platform recovery check | `database_recovery.py:19-64` |
| **15. DatabaseRecoveryManager Behavior** | `research_platform/recovery/database_recovery.py` | 24–64 | `recover_database` | Fails closed if DB service is absent or if `SELECT 1` fails. Returns `True` if healthy. | `RecoveryPlugin` | `DatabaseSession` | Reached at boot (Priority 30) | `database_recovery.py:29-64` |
| **16. Runtime Supervisor Restart Behavior** | `scripts/runtime_supervisor.py` | 181–297 | `main` process monitor loop | Monitors child processes (`run_paper_trading.py` & `run_api.py`). If process exits/crashes, restarts it and logs alert. On restart, child process re-runs boot sequence. | OS process launcher / CLI | `subprocess.Popen` | Active in production/paper deployment | `runtime_supervisor.py:181-297` |

---

## 2. PHASE 3B — AUTHORITATIVE STATE CONTRACT

The table below defines the authoritative source of truth, persistence target, repository ownership, read API status, and deterministic reconstruction formula for every portfolio state field.

| Field / Attribute | Persisted? | Storage Location | Owning Repository | Existing Read API? | Deterministically Reconstructible? | Gap / Action Required |
|---|---|---|---|---|---|---|
| **cash / balance** | YES (Derived) | Calculated from `trade_ledger` & `positions` tables | `PostgresLedgerRepository` & `PostgresPositionRepository` | YES (`list_entries()`, `list_positions()`) | YES | Formula: `initial_balance + sum(ledger.realized_pnl) - sum(ledger.commission + ledger.slippage) - sum(pos.quantity * pos.entry_price for open positions)` |
| **equity** | YES (Derived) | Calculated from `cash` + open position market values | `PostgresPositionRepository` | YES (`list_positions()`) | YES | Formula: `cash_balance + sum(pos.quantity * pos.current_price)`. On boot before first tick, `current_price = entry_price`. |
| **positions** | YES | Table: `positions` (`position_id`, `symbol`, `quantity`, `average_price`) | `PostgresPositionRepository` | YES (`list_positions()`) | YES | **Bug Fix Required in API:** `list_positions()` passes `average_price=m.average_price` to `PaperPosition` instead of `entry_price` and `current_price`. Must fix keyword args. |
| **realized PnL** | YES | Table: `trade_ledger` (`realized_pnl` column) | `PostgresLedgerRepository` | YES (`list_entries()`) | YES | Formula: `sum(entry.realized_pnl for entry in ledger_entries)` |
| **unrealized PnL** | NO (Dynamic) | Computed dynamically per tick | N/A (Valuation Engine) | YES (`on_tick()`) | YES | Restored to 0.0 at boot; immediately updated when first market tick arrives. |
| **daily PnL** | NO (Dynamic) | Computed relative to day start | N/A (Accounting Engine) | YES (`recalculate()`) | YES | Initialized to 0.0 relative to boot equity; resets at UTC midnight. |
| **trades** | YES | Table: `trades` & `trade_ledger` | `PostgresTradeRepository` & `PostgresLedgerRepository` | YES (`list_trades()`, `list_entries()`) | YES | Rehydrated from `trade_ledger` / `trades` rows into `TradeJournal` and `MetricsEngine._trades`. |
| **orders** | YES | Table: `orders` | `PostgresOrderRepository` | YES (`list_orders()`) | YES | Loaded during `RuntimeStateManager` startup sync. |
| **ledger** | YES | Table: `trade_ledger` | `PostgresLedgerRepository` | YES (`list_entries()`) | YES | Loaded into `AccountingService._ledger_repository`. |
| **peak equity** | NO (Calculated) | Computed from historical equity curve | `MetricsEngine` | YES (`_peak_equity`) | YES | Reconstructed by building equity curve step-by-step from trade ledger history, capped at `max(initial_balance, current_equity)`. |
| **consecutive losses**| NO (Calculated) | Computed from trade ledger sequence | `MetricsEngine` / `TradeJournal` | YES (`get_all()`) | YES | Calculated by scanning trade records sorted by timestamp descending. |
| **open exposure** | YES (Derived) | Calculated from open positions | `PostgresPositionRepository` | YES (`list_positions()`) | YES | Formula: `sum(pos.quantity * pos.current_price)` |
| **risk state** | NO (Derived) | Evaluated dynamically against portfolio state | `RiskManagementOrchestrator` | YES (`validate_order()`) | YES | Automatically matches rehydrated portfolio state as soon as `AccountingService` rehydration completes. |
| **portfolio state** | YES (Derived) | Aggregate of cash, equity, positions, metrics | `AccountingService` | YES (`get_portfolio_summary()`) | YES | Rehydrated state published via `PortfolioUpdated` event immediately post-rehydration. |

---

## 3. PHASE 3C — REHYDRATION DESIGN

### Data Flow Architecture
```
┌──────────────────────────┐
│ PostgreSQL / Neon DB     │
│ (positions, trade_ledger)│
└────────────┬─────────────┘
             │ SQL SELECT queries
             ▼
┌──────────────────────────┐
│ Repositories             │
│ (PostgresPositionRepo,   │
│  PostgresLedgerRepo)     │
└────────────┬─────────────┘
             │ Domain Models (PaperPosition, TradeLedgerEntry)
             ▼
┌──────────────────────────┐
│ AccountingService        │
│ .rehydrate_from_db()     │
└────────────┬─────────────┘
             │ Instantiates & populates engines
             ▼
┌─────────────────────────────────────────────────────────┐
│ In-Memory Subsystem State                               │
│  ├── PositionValuationEngine._positions                 │
│  ├── PortfolioAccountingEngine._cash_balance / realized │
│  ├── MetricsEngine._trades & _peak_equity               │
│  └── TradeJournal._records                              │
└────────────┬────────────────────────────────────────────┘
             │ Event: PortfolioUpdated, PnLUpdated
             ▼
┌──────────────────────────┐
│ Risk & OMS Subsystems    │
│ (Evaluates against state)│
└──────────────────────────┘
```

### Detailed Rehydration Load Order & Dependencies

1. **Phase 1: DB Connection Verification**
   - **Dependency:** `DatabaseLifecycleManager` connected & migrations executed.
   - **Action:** Obtain `DatabaseSessionManager` from platform `Database` service.

2. **Phase 2: Position Rehydration**
   - **Dependency:** `PostgresPositionRepository`.
   - **Action:** Call `pos_repo.list_positions()`.
   - **Populates:** For each position, instantiate `ValuatedPosition` in `PositionValuationEngine._positions[symbol]`.

3. **Phase 3: Ledger & Trade Journal Rehydration**
   - **Dependency:** `PostgresLedgerRepository`.
   - **Action:** Call `ledger_repo.list_entries()`.
   - **Populates:**
     - `AccountingService._ledger_repository` (in-memory entries list).
     - Calculate cumulative `realized_pnl = sum(e.realized_pnl)`, `commission = sum(e.commission)`, `slippage = sum(e.slippage)`, `fees = sum(e.commission + e.slippage)`.
     - Build `TradeRecord` items for closed trades and ingest into `TradeJournal` and `MetricsEngine._trades`.

4. **Phase 4: Accounting Engine Cash & Equity Reconstruction**
   - **Dependency:** Rehydrated positions & ledger totals.
   - **Action:**
     - Compute open positions cash outlay: `open_cash_outlay = sum(p.quantity * p.average_entry for p in positions if p.side == 'LONG')`.
     - Compute net cash balance: `cash_balance = initial_balance + realized_pnl - fees - open_cash_outlay`.
     - Set `PortfolioAccountingEngine._cash_balance = cash_balance`, `_realized_pnl = realized_pnl`, `_fees = fees`, `_commission = commission`, `_slippage = slippage`.
     - Recalculate portfolio snapshot: `recalculate(positions)`.

5. **Phase 5: Consistency Validation & Event Notification**
   - **Action:**
     - Assert `cash_balance >= 0` (or report inconsistency if negative).
     - Assert `equity > 0`.
     - Publish `PortfolioUpdated`, `PnLUpdated`, and `PerformanceUpdated` events so RiskEngine and OMS operate on authoritative state before the first market tick arrives.

---

## 4. PHASE 3D — FAIL-CLOSED REQUIREMENTS

State rehydration is a primary safety boundary for TOJI PAPER and PROD modes.

### Strict Fail-Closed Rules:

1. **DB Unavailability in PAPER / PROD Mode:**
   - If `DATABASE_MODE == "PAPER"` (or `TOJI_MODE == "PAPER"`), TOJI **MUST NOT** silently create an empty default portfolio ($100,000 cash, 0 positions) if PostgreSQL is unreachable or fails to connect.
   - **Action:** `AccountingService.rehydrate_from_db()` raises `RuntimeError("FAIL-CLOSED: Database unavailable for state rehydration in PAPER mode.")`. Platform boot sets `TradingHalted = True` and halts.

2. **Malformed or Contradictory Persisted Records:**
   - If position quantity is negative or NaN, or if ledger entries contain invalid numbers.
   - **Action:** Rehydration aborts, logs `CRITICAL` error, and raises `RuntimeError`. Trading is halted.

3. **Inconsistent Rehydrated Cash / Equity:**
   - If calculated `equity <= 0` or `cash_balance < 0` without an explicit credit facility.
   - **Action:** Abort startup, mark trading halted.

4. **Idempotency Requirement:**
   - Calling `rehydrate_from_db()` multiple times must yield identical in-memory state without duplicating ledger entries or cash balance changes.

---

## 5. PHASE 3E — RESTART TEST DESIGN

A dedicated test suite `research_platform/tests/test_sprint002_phase3.py` will be created to verify all 15 required scenarios:

1. **Fresh Account With No Trades:** Rehydrate empty DB → verify `cash_balance == 100000.0`, `open_positions == 0`, `realized_pnl == 0.0`.
2. **One Open Position:** Insert 1 position row (1.5 BTC @ $60,000) → restart → verify `PositionValuationEngine` has 1 position, quantity 1.5, entry price $60,000, cash balance $10,000.
3. **Multiple Open Positions:** Insert BTC and ETH positions → restart → verify both positions accurately restored.
4. **Realized PnL:** Insert closed trade ledger entry with +$500 PnL → restart → verify `realized_pnl == 500.0`, `cash_balance == 100500.0`.
5. **Unrealized PnL:** Restore open position → send market tick ($62,000) → verify unrealized PnL is computed correctly (+$3,000).
6. **Multiple Trades:** Insert sequence of fills and closes → restart → verify cumulative cash, realized PnL, and fees match exact mathematical expectations.
7. **Closed Position:** Open position -> full close -> position row deleted -> restart -> verify 0 open positions, cash reflects closed PnL.
8. **Restart After Successful Fill:** Execute fill via `on_fill()` (committing to DB) -> stop process -> start process -> rehydrate -> verify exact match.
9. **Restart After Partial Persistence Failure:** Trigger transaction rollback -> stop -> start -> rehydrate -> verify uncommitted data is absent and state is clean.
10. **Database Unavailable:** Disconnect DB in PAPER mode -> attempt rehydration -> verify `RuntimeError` raised, `TradingHalted` set, zero fabricated state.
11. **Corrupt / Inconsistent Persisted State:** Insert corrupted row -> attempt rehydration -> verify fail-closed exception.
12. **Duplicate Rehydration:** Call `rehydrate_from_db()` twice -> verify state is identical and not duplicated.
13. **Rehydration Idempotency:** Execute multiple rehydration calls -> verify snapshot equality.
14. **Risk State After Restart:** Rehydrate position -> submit new order violating max exposure -> verify `RiskManagementOrchestrator` blocks order based on rehydrated state.
15. **Paper Trade After Restart:** Rehydrate -> process market tick -> execute new trade -> verify new trade is atomically persisted and appended to rehydrated state.

---

## 6. PHASE 3F — RESOURCE & PERFORMANCE CHECK

- **Startup DB Queries:** Maximum **2 to 3 SELECT queries** during platform boot (`SELECT * FROM positions`, `SELECT * FROM trade_ledger`, `SELECT * FROM trades`).
- **Rows Loaded:** $O(\text{open positions}) + O(\text{trade ledger entries})$. For standard operations, open positions $< 50$, trade ledger $< 10,000$ rows.
- **Memory Overhead:** $< 2 \text{ MB}$ total memory footprint for rehydrated objects.
- **Bounding Unbounded Structures:** `PositionValuationEngine._history` remains bounded at 10,000 entries max.
- **Latency / Startup Duration:** Estimated $< 50\text{ ms}$ for complete state rehydration on Neon PostgreSQL.

---

## 7. PHASE 3G — IMPLEMENTATION GATE & REPOSITORY SCOPE

### 7.1 Scope of File Modifications

#### Exact Files Requiring Modification (Minimal Set):
1. `research_platform/persistence/repositories/position_repository.py`:
   - Fix keyword arguments in `list_positions()`: map `entry_price=m.average_price` and `current_price=m.average_price` for `PaperPosition` initialization.
2. `research_platform/portfolio_accounting/accounting_service.py`:
   - Add `rehydrate_from_db(db_service=None)` method.
   - Reconstructs in-memory valuation, accounting, metrics, and journal engines from DB repositories.
3. `research_platform/portfolio_accounting/plugin.py`:
   - In `PortfolioAccountingPlugin.initialize()`, resolve Database service and invoke `rehydrate_from_db()`.
   - Enforce fail-closed check in `PAPER` mode if rehydration fails.
4. `research_platform/tests/test_sprint002_phase3.py` **[NEW]**:
   - Comprehensive test suite for all 15 restart and rehydration scenarios.

#### Exact Files That Must NOT Be Modified:
- `research_platform/persistence/postgres/session.py`
- `research_platform/persistence/postgres/transaction_manager.py`
- `research_platform/persistence/postgres/base_repository.py`
- `research_platform/persistence/postgres/connection.py`
- `research_platform/persistence/postgres/migrations.py`
- `research_platform/platform/database_boot.py`
- `research_platform/recovery/database_recovery.py`
- `research_platform/platform/eventbus_boot.py`
- `research_platform/oms/*` (both OMS implementations)
- `toji_platform/*` (core kernel architecture)
- All strategy files (`strategy/`, `strategy_router.py`)
- Database Schema / SQL tables (No schema changes required)

---

## 8. CTO ACCEPTANCE CRITERIA

Phase 3 implementation will be considered complete **ONLY** when:

- [x] Every persisted state source is identified
- [x] Every runtime state consumer is identified
- [x] Existing repository read APIs are verified
- [x] Missing functionality & repository bugs documented
- [x] No second source of truth is introduced
- [x] Fail-closed behavior is defined
- [x] Restart test scenarios are defined
- [x] Sprint 001 invariants are preserved
- [x] Sprint 002 Phase 2 invariants are preserved
- [x] No architecture consolidation is introduced
- [x] No live trading capability is introduced
- [ ] Comprehensive test `PERSIST → STOP → START → REHYDRATE → VERIFY` passes cleanly against local test DB and Neon PostgreSQL.

---

**STOP. AWAITING CTO REVIEW & APPROVAL BEFORE COMMENCING SOURCE CODE EDITS.**
