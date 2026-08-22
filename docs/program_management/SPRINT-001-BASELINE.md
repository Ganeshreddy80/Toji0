# Sprint 001 -- Baseline Report

> **Document Type:** Sprint Execution Baseline
> **Sprint ID:** SPRINT-001
> **Sprint Name:** Runtime Stabilization
> **Date:** 2026-08-08
> **Status:** PHASE 1 COMPLETE
> **Evidence Policy:** All findings traced to specific files and line numbers.

---

## 1. Git / Version Control Status

```
fatal: not a git repository (or any of the parent directories): .git
```

This workspace is a zip extraction (toji-main 3). No git history available.
Rollback must use filesystem checksums.

---

## 2. Python Environment

- **Venv Python:** 3.14.5 (Clang 21.0.0)
- **Venv Pytest:** 8.3.4

### Critical Environment Blocker

The venv uses Python 3.14.5. The `langsmith` package (0.4.37) at the system level
(`/Library/Frameworks/Python.framework/Versions/3.13`) registers a `pytest11` entrypoint.
It imports `pydantic_core._pydantic_core` -- a C extension compiled for Python 3.13 that is
binary-incompatible with Python 3.14.

```
ModuleNotFoundError: No module named 'pydantic_core._pydantic_core'
```

**Pytest is completely broken when using `.venv/bin/python` (Python 3.14).**

**Workaround:** Use system-level `python3.13`:

```bash
APP_ENV=testing PYTHONPATH="<workspace>" python3.13 -m pytest tests/ -v --tb=short -q
```

---

## 3. Test Suite Baseline

### 3.1 Paper Trading Tests: 30/30 PASSED (3.08s)

All 30 tests in `tests/test_paper_trading.py` pass:
test_account_creation, test_cash_updates, test_position_updates, test_buy_orders,
test_sell_orders, test_market_orders, test_limit_orders, test_stop_orders, test_partial_fills,
test_full_fills, test_cancelled_orders, test_rejected_orders, test_session_lifecycle,
test_event_publishing, test_repository_persistence, test_thread_safety, test_determinism,
test_duplicate_order_protection, test_invalid_orders, test_large_order_volume,
test_portfolio_valuation, test_equity_updates, test_realized_pnl, test_unrealized_pnl,
test_buying_power, test_atomic_persistence, test_bounded_cache, test_regression,
test_architecture_boundaries, test_immutable_models

### 3.2 Full Test Suite: 1381/1391 PASSED

**Run 1 (pre-fix baseline):** `1381 passed, 10 failed in 158.78s`
**Run 2 (post-Phase 3 fixes):** `1381 passed, 10 failed in 196.87s` -- IDENTICAL, 0 regressions introduced

**10 pre-existing BASELINE FAILURES (not Sprint 001 regressions):**

| Test | File |
|---|---|
| test_sprint2_pipeline_authoritative_consistency | tests/e2e/test_end_to_end_trading_verification.py |
| test_supervisor_environment_validation | tests/e2e/test_runtime_resilience.py |
| test_end_to_end_pipeline_integration | tests/integration/test_end_to_end_pipeline.py |
| test_order_side_routing_correctness | tests/integration/test_production_readiness.py |
| test_report_create | tests/test_model_evaluation.py |
| test_event_generation_resource_threshold_exceeded | tests/test_monitoring.py |
| test_seed_reproducibility | tests/test_monte_carlo.py |
| test_deterministic_flag | tests/test_monte_carlo.py |
| test_pipeline_retry | tests/test_training_pipeline.py |
| test_long_running_simulation | tests/test_validation.py |

**BASELINE PASS RATE: 1381/1391 = 99.28%**

**INVARIANT:** Sprint 001 changes must not reduce this pass rate.

---

## 4. Runtime Entrypoint Verification

| Entry Point | File | Status |
|---|---|---|
| Primary Docker Paper Engine | scripts/run_paper_trading.py | VERIFIED -- canonical |
| Docker API | scripts/run_api.py | VERIFIED |
| Runtime Supervisor | scripts/runtime_supervisor.py | VERIFIED -- boot coordinator |
| toji_platform CLI | toji_platform/boot.py | VERIFIED -- alternate stack, NOT active |
| One-shot verification | run_paper_trade_verification.py | VERIFIED -- not production |

---

## 5. Paper Trading Execution Path Trace

Traced from `scripts/run_paper_trading.py:163-811`.

```
MARKET TICK (EventBus: "system.market_data_received")
  |
  |-- [Step 0] Price boundary validation (BTC: 1000-500000, ETH: 100-50000)
  |-- [Step 1] RuntimeStateManager.record_tick()
  |-- [Step 2] MarketDataNormalizer / OHLCV construction
  |-- [Step 3] PriceActionOrchestrator.process_tick(symbol, price, ts, vol)
  |-- [Step 4] FeaturePlatformOrchestrator.compute_and_store(features, symbol, df)
  |-- [Step 5] StrategyComposer.generate_decision()   HOLD -> return
  |-- [Step 6] AISignalGenerator.generate_signal()    WAIT -> return
  |-- [Step 7a] AIDecisionAuditor.audit()             REJECTED -> return
  |
  |-- [Step 7b] KillSwitchEngine.evaluate(daily_pnl=0.0, capital=100000.0, ...) <<< BUG-001
  |             HALTED -> return
  |
  |-- [Step 7c] RealTimeRiskMonitor.calculate_risk_score(capital=100000.0, ...) <<< BUG-002
  |             risk_score < 40.0 -> return
  |
  |-- [Step 7d] OmsCore.submit_order(strategy_id, symbol, qty, price, "MARKET", side)
  |               -> PaperExecutionRouter.route_order()
  |                   -> PaperTradingOrchestrator.submit_paper_order()
  |                       -> PaperBrokerAdapter -> PaperExchange (simulated fill)
  |                       -> Publishes PaperOrderFilled event
  |                           -> AccountingService.on_fill() [via EventBus]
  |                               -> PostgresTradeRepository.save_trade()
  |                               -> PostgresPositionRepository.save_position()
  |                               -> PostgresLedgerRepository.save_entry()
  |                               -> OMS order status -> FILLED
  |
  |-- [Step 7f] TradeMemoryEngine.save_trade(pnl=0.0) <<< BUG-003
  `-- [Step 7g] Telegram trade alert
```

---

## 6. Confirmed Production Bugs

### BUG-001: KillSwitchEngine receives hardcoded values (CRITICAL)

**File:** scripts/run_paper_trading.py, Lines 568-575

```python
ks_state = kill_switch.evaluate(
    daily_pnl=0.0,            # HARDCODED
    current_capital=100000.0, # HARDCODED
    peak_capital=100000.0,    # HARDCODED
    consecutive_losses=0,     # HARDCODED
    avg_execution_quality=95.0,
    exchange_connected=True
)
```

Impact: KillSwitch will NEVER trigger on daily loss limit, drawdown, or consecutive losses.

### BUG-002: RealTimeRiskMonitor receives hardcoded values (CRITICAL)

**File:** scripts/run_paper_trading.py, Lines 597-603

```python
risk_snap = risk_monitor.calculate_risk_score(
    capital=100000.0,      # HARDCODED
    open_positions=[],     # HARDCODED -- exposure always 0
    peak_capital=100000.0, # HARDCODED
    leverage=1.0,
    consecutive_losses=0,  # HARDCODED
    daily_pnl=0.0          # HARDCODED
)
```

Impact: Risk score always computes ~100.0 (full green). Risk gate effectively bypassed.

### BUG-003: TradeMemoryEngine.save_trade with hardcoded pnl=0.0

**File:** scripts/run_paper_trading.py, Line ~728
Impact: Trade memory pattern analysis receives P&L=0 for every trade.

### BUG-004: Plugin initialize() failures crash entire boot (no try/except)

**File:** research_platform/platform/startup.py, Lines 117-120

```python
for p in sorted_plugins:
    p.initialize()  # NO try/except -- any failure aborts ALL subsequent plugins
```

Impact: A single plugin boot failure aborts the entire platform startup.

### BUG-005: PluginLoader import errors silently swallowed

**File:** research_platform/platform/plugin_loader.py, Lines 40-41

```python
except Exception as e:
    logger.error("Failed to load plugin from %s: %s", import_path, e)
# Failed plugin omitted from list with no count tracking
```

Impact: Startup coordinator has no visibility into which plugins failed to load.

---

## 7. Authoritative State Sources

| Value Needed | Source | Container Key | Accessor |
|---|---|---|---|
| current_capital | AccountingService._accounting_engine | "AccountingService" | get_portfolio_summary()["equity"] |
| peak_capital | PerformanceEngine._peak_equity | "PerformanceEngine" | _peak_equity attribute |
| daily_pnl | AccountingService._accounting_engine | "AccountingService" | get_portfolio_summary()["daily_pnl"] |
| open_positions | PositionValuationEngine._positions | Via AccountingService.valuation_engine | get_all_positions() |
| consecutive_losses | MetricsEngine._trades | Via AccountingService.metrics_engine | Must be derived from trades list |
| initial_balance | PortfolioAccountingEngine | Via AccountingService | initial_balance property |

Note: `consecutive_losses` has no direct accessor. Data exists; computed field is missing.

---

## 8. OMS Dual Implementation Summary

| Property | research_platform/oms/oms_core.py | execution_engine/oms/oms_core.py |
|---|---|---|
| Constructor | (event_bus, container=None) | (config, broker_router, validator, ...) |
| Order Unit | Order (Pydantic) | OrderIntent (Pydantic) |
| Entry Method | submit_order(strategy_id, symbol, ...) | submit_intent(intent) |
| Active | YES -- paper runner line 648 | NO -- not used in paper trading |

Neither implementation shall be deleted or merged per Sprint 001 scope.

---

## 9. Risk Summary

| ID | Risk | Severity |
|---|---|---|
| R1 | Pytest broken with venv Python 3.14 (langsmith incompatibility) | HIGH |
| R2 | KillSwitch and RiskMonitor receive hardcoded phantom values | CRITICAL |
| R3 | Plugin initialize() failures crash entire boot | HIGH |
| R4 | Plugin discovery failures silently dropped | MEDIUM |
| R5 | TradeMemoryEngine.save_trade always receives pnl=0.0 | MEDIUM |
| R6 | Event string mismatch between PaperOrderFilled class and subscriber | HIGH |
| R7 | No consecutive_losses accessor on MetricsEngine | MEDIUM |
| R8 | AccountingService not resolved in tick loop -- hardcodes used | CRITICAL |

---

*Baseline captured: 2026-08-08*
*Sprint 001 Phase 1 -- COMPLETE*
*Full suite: 1381/1391 passed (99.28%)*
