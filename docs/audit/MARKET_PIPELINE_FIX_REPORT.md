# TOJI Market Pipeline Fix Report

**Date**: 2026-07-09  
**Sprint**: Market Data Pipeline Fix  
**Status**: ✅ COMPLETE

## Problem Statement

After 12-hour production stability test, TOJI infrastructure was healthy (Docker stable, RestartCount=0, Postgres/Redis healthy, all plugins loaded), but the **trading simulation was not receiving market events**.

## Root Cause

`research_platform/live_trading/plugin.py` (line 106) incorrectly coupled market data subscription with `TRADING_MODE`:

```python
# THE BUG — market tick listener gated behind live mode only
if trading_mode.lower() == "live":
    event_bus.subscribe("system.market_tick_received", self._handle_market_tick)
else:
    logger.info("Live tick listener disabled.")  # ← This killed the pipeline in paper mode
```

This blocked the entire `MarketTick → Feature Engine → Strategy → AI Signal` pipeline when `TRADING_MODE=paper`.

### Architectural Root Cause

Conflation of two independent concerns:

| Concern | Should Be Controlled By |
|---|---|
| **Data source** (what feeds ticks) | `MARKET_PROVIDER` (`binance_live`, `binance_testnet`, `demo`) |
| **Order execution** (how to act on signals) | `TRADING_MODE` (`paper` → simulator, `live` → exchange) |

## Fix Applied

### 1. `plugin.py` — Unconditional Market Tick Subscription

**Before:**
```python
if trading_mode.lower() == "live":
    event_bus.subscribe("system.market_tick_received", self._handle_market_tick)
else:
    logger.info("Live tick listener disabled.")
```

**After:**
```python
# TRADING_MODE controls execution safety only, NOT data flow.
event_bus.subscribe("system.market_tick_received", self._handle_market_tick)
logger.info("Market tick listener ACTIVE (provider=%s, execution=%s).",
            market_provider, trading_mode.upper())
```

### 2. Structured Startup Fingerprint

```
======== TOJI RUNTIME MODE ========
Market Provider: binance_live
Market Data: ENABLED
Tick Listener: ACTIVE
Execution: PAPER
Real Orders: DISABLED
===================================
```

### 3. Runtime Health Endpoint Enhanced

`/api/v1/runtime/status` now exposes:
- `market_provider` — active data source
- `trading_mode` — execution mode
- `ticks_processed` — tick counter
- `paper_orders` — paper trade count
- `real_orders_enabled` — boolean safety flag

### 4. Execution Safety (Unchanged — Already Correct)

Two-layer protection remains in place:
1. `ExecutionEngineOrchestrator.execute_order()` — raises `PermissionError` when `TRADING_MODE=paper`
2. `BinanceGatewayProvider.place_market_order()` / `place_limit_order()` — raises `PermissionError` in paper mode

## Files Modified

| File | Change |
|---|---|
| `research_platform/live_trading/plugin.py` | Removed `TRADING_MODE` guard on tick subscription; added startup fingerprint |
| `backend/main.py` | Added `market_provider`, `trading_mode`, `paper_orders`, `real_orders_enabled` to `/api/v1/runtime/status` |
| `tests/e2e/test_market_wiring.py` | Updated `test_no_duplicate_order_execution` — tick listener must be active in paper mode |
| `tests/e2e/test_market_to_strategy_pipeline.py` | **NEW** — 5 regression tests for pipeline wiring |

## Files NOT Modified (Certified Clean)

- Kernel / Singleton boot
- Database / Redis
- Supervisor
- Binance URL config
- Strategy / AI / Risk engine logic
- Market Gateway providers

## Test Results

### New Pipeline Regression Tests (5/5 passed)
- `test_paper_mode_receives_live_ticks` ✅
- `test_paper_mode_blocks_real_orders` ✅
- `test_no_strategy_without_market_ticks` ✅
- `test_tick_listener_active_in_both_modes` ✅
- `test_startup_fingerprint_printed` ✅

### Full E2E Suite — All passed
### Full Unit Suite — 746 passed

## Expected Runtime Behavior After Fix

```
BTCUSDT tick received
Feature calculated
Strategy input generated
AI signal evaluated
Paper execution decision
```

Pipeline flows in **both** paper and live modes. Real exchange orders remain blocked by the execution engine safety gate.
