# PAPER EXECUTION ROUTING — CTO AUDIT REPORT

**Date:** 2026-07-09  
**Author:** TOJI CTO Engineering  
**Status:** ✅ FIXED & VERIFIED

---

## 1. Problem Statement

TOJI ran for hours with thousands of `ROUTED` orders visible in the `orders` table,
yet no fills occurred and `orders = 0` appeared in the runtime status dashboard.

### Root Cause

`TradeManager.execute_signal_trade()` unconditionally called  
`ExecutionEngineOrchestrator.execute_order()`, which intentionally raises:

```python
raise PermissionError("Safety Breach: Real exchange orders are blocked when TRADING_MODE=paper!")
```

The `PaperExecutionRouter` and `PaperTradingOrchestrator` existed in the codebase but
were **never wired into the signal execution path**.

---

## 2. Architecture: Before vs After

### Before (BROKEN)

```
Signal → TradeManager.execute_signal_trade()
            ↓
         OMS.ingest_order()   ← works
            ↓
         ExecutionEngineOrchestrator.execute_order()
            ↓
         PermissionError: TRADING_MODE=paper  ← SILENTLY CAUGHT, returns False
```

### After (FIXED)

```
TRADING_MODE=paper:
  Signal → TradeManager.execute_signal_trade()
              ↓ TRADING_MODE check
           OMS.ingest_order()
              ↓
           PaperExecutionRouter.route_order()
              ↓
           PaperTradingOrchestrator.submit_paper_order()
              ↓
           PaperExchange (mock fill) → FILLED ✅

TRADING_MODE=live:
  Signal → TradeManager.execute_signal_trade()
              ↓ TRADING_MODE check
           OMS.ingest_order()
              ↓
           ExecutionEngineOrchestrator.execute_order()  (real exchange)
```

---

## 3. Files Modified

| File | Change |
|------|--------|
| `research_platform/live_trading/trade_manager.py` | Added `paper_router` optional arg; routes by `TRADING_MODE` env var |
| `research_platform/live_trading/orchestrator.py` | Added `paper_router: Optional[object]` constructor param; passes to TradeManager |
| `research_platform/live_trading/plugin.py` | Imports `PaperExecutionRouter`; creates & registers it; injects into orchestrator |
| `research_platform/paper_trading/plugin.py` | Registers `PaperTradingOrchestrator` under full string key; auto-starts default session |
| `tests/e2e/test_paper_execution_flow.py` | 7-test regression suite (NEW) |
| `docs/audit/PAPER_EXECUTION_ROUTING_REPORT.md` | This document (NEW) |

---

## 4. Safety Invariants Preserved

| Invariant | Status |
|-----------|--------|
| `ExecutionEngineOrchestrator` raises `PermissionError` for `TRADING_MODE=paper` | ✅ Untouched |
| Binance gateway is never called in paper mode | ✅ Paper router does not touch exchange |
| OMS ingestion still runs in both modes | ✅ Always first step |
| Live mode still routes to real EMS | ✅ `TRADING_MODE=live` branch intact |

---

## 5. DI Container Registration Chain

```
Boot sequence (plugin load order):
  1. PaperTradingPlugin.initialize()
     → registers PaperTradingOrchestrator (class key)
     → registers "research_platform.paper_trading.orchestrator.PaperTradingOrchestrator" (string key)
     → auto-starts "default_paper_account" session (balance: 100,000 USDT)

  2. LiveTradingEnginePlugin.initialize()
     → creates PaperExecutionRouter(container, mode="PAPER")
     → registers PaperExecutionRouter (class + string keys)
     → creates LiveTradingOrchestrator(event_bus, oms, ems, paper_router=paper_router)
       → TradeManager(oms, ems, paper_router=paper_router)
```

---

## 6. Regression Tests (7/7 PASS)

```
tests/e2e/test_paper_execution_flow.py::TestTradeManagerPaperRouting::test_paper_mode_calls_paper_router         PASSED
tests/e2e/test_paper_execution_flow.py::TestTradeManagerPaperRouting::test_paper_mode_no_router_returns_false    PASSED
tests/e2e/test_paper_execution_flow.py::TestTradeManagerPaperRouting::test_paper_mode_unfilled_order_returns_false PASSED
tests/e2e/test_paper_execution_flow.py::TestTradeManagerPaperRouting::test_live_mode_calls_ems_not_paper_router  PASSED
tests/e2e/test_paper_execution_flow.py::TestPaperExecutionRouter::test_paper_mode_routes_to_paper_orchestrator   PASSED
tests/e2e/test_paper_execution_flow.py::TestPaperExecutionRouter::test_paper_mode_raises_when_orchestrator_missing PASSED
tests/e2e/test_paper_execution_flow.py::TestPaperTradingPluginBoot::test_auto_starts_default_paper_session       PASSED
```

---

## 7. Verification After Deploy

```bash
# Restart containers
docker compose restart app

# After 60 seconds, check runtime status
curl -H "X-API-Key: toji_sec_admin_key_9931882c81a" http://localhost:8000/runtime/status

# Expected:
# {
#   "ticks_processed": <increasing>,
#   "features": <increasing>,
#   "orders": <increasing>,        ← was 0 before fix
#   "paper_fills": <increasing>    ← was 0 before fix
# }

# Confirm no PermissionError in logs
docker compose logs app --since 5m | grep PermissionError  # → should be empty
```
