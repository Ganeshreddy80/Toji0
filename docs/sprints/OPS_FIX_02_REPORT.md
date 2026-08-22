# OPS-FIX-02 Sprint Report

**Sprint**: OPS-FIX-02 — Production Runtime Fixes + Trading Intelligence Alerts  
**Date**: 2026-07-06  
**Status**: ✅ COMPLETE

---

## Summary

Six targeted production fixes applied to the TOJI paper trading runtime. No trading engines, OMS, safety gateway, or strategy code was modified.

---

## Changes Made

### TASK 1 — Redis Docker Service ✅

**File**: [`docker-compose.yml`](../../docker-compose.yml)

- Added `redis:7-alpine` service (`toji-redis`) with healthcheck on port 6379
- Updated `app.depends_on` to include `redis: condition: service_healthy`
- Injected `REDIS_URL=redis://toji-redis:6379/0` into app environment

**Verification**: `docker exec toji-app env | grep REDIS` → `REDIS_URL=redis://toji-redis:6379/0`

---

### TASK 2 — API Key Configuration ✅

**Files**: [`.env.example`](../../.env.example), [`docker-compose.yml`](../../docker-compose.yml)

- Documented `TOJI_ADMIN_API_KEY` and `TOJI_ANALYST_API_KEY` in `.env.example`
- Updated `REDIS_URL` in `.env.example` to use Docker hostname `toji-redis`
- Added `BINANCE_SYMBOLS=BTCUSDT,ETHUSDT` to trading universe section

**Usage**:
```bash
curl -H "X-API-KEY: change_me_admin_key" http://localhost:8000/api/v1/overview
```

---

### TASK 3 — Heartbeat Spam Fix ✅

**Files**: [`scripts/run_paper_trading.py`](../../scripts/run_paper_trading.py), [`toji_platform/runtime/heartbeat.py`](../../toji_platform/runtime/heartbeat.py)

Mode-aware heartbeat intervals:

| Mode | Interval |
|------|----------|
| DEV  | 60 seconds |
| PAPER | 30 minutes (1800s) |
| PROD | 1 hour (3600s) |

- Added `_MODE_INTERVALS` dict in runner, resolved from `TOJI_MODE` env var at boot
- Heartbeat loop now uses `stop_event.wait(float(_HEARTBEAT_INTERVAL))` instead of hardcoded 60s
- Heartbeat message now includes `Watching:` section listing active symbols

---

### TASK 4 — Trading Intelligence Telegram Alerts ✅

**Files**: [`research_platform/alerting/trade_formatter.py`](../../research_platform/alerting/trade_formatter.py) (NEW), [`scripts/run_paper_trading.py`](../../scripts/run_paper_trading.py)

New module `trade_formatter.py` provides:

- `format_signal_alert()` → `🧠 TOJI SIGNAL` message with symbol, decision, price, confidence, reasoning, RSI/volume/trend, and risk sizing
- `format_trade_alert()` → `📈 TOJI PAPER TRADE EXECUTED` message with symbol, side, entry, quantity, reason, OMS/Safety status

Both are invoked in `run_paper_trading.py`:
- Signal alert fires when AI signal is BUY or SELL (before OMS submission)
- Trade alert fires after OMS confirms order as VALIDATED/QUEUED/ROUTED/FILLED

---

### TASK 5 — Symbol Tracking ✅

**Files**: [`backend/main.py`](../../backend/main.py), [`toji_platform/runtime/heartbeat.py`](../../toji_platform/runtime/heartbeat.py)

- `GET /api/v1/overview` now includes `active_symbols: ["BTCUSDT", "ETHUSDT"]` in response
- Heartbeat status message now shows `Watching:\nBTCUSDT\nETHUSDT`
- Both read from `BINANCE_SYMBOLS` env var (default: `BTCUSDT,ETHUSDT`)

---

### TASK 6 — Runner Startup Banner ✅

**File**: [`scripts/run_paper_trading.py`](../../scripts/run_paper_trading.py)

Added prominent ASCII banner at engine startup:

```
╔══════════════════════════════════════════════════╗
║       TOJI PAPER ENGINE STARTED                 ║
╠══════════════════════════════════════════════════╣
║  Loaded:                                        ║
║    Database       ✓                             ║
║    Redis          ✓                             ║
║    Market Gateway ✓                             ║
║    Feature Engine ✓                             ║
║    Price Action   ✓                             ║
║    Strategy       ✓                             ║
║    AI Signal      ✓                             ║
║    OMS            ✓                             ║
║    Safety         ✓                             ║
║    Telegram       ✓                             ║
╚══════════════════════════════════════════════════╝
```

---

## Test Results

**New Tests**: [`tests/unit/ops/test_ops_fix_02.py`](../../tests/unit/ops/test_ops_fix_02.py)

| Test | Status |
|------|--------|
| `test_redis_health_ok` | ✅ PASSED |
| `test_api_key_valid` | ✅ PASSED |
| `test_heartbeat_interval_paper_mode` | ✅ PASSED |
| `test_heartbeat_interval_dev_mode` | ✅ PASSED |
| `test_heartbeat_interval_prod_mode` | ✅ PASSED |
| `test_signal_alert_contains_symbol` | ✅ PASSED |
| `test_trade_alert_contains_reason` | ✅ PASSED |
| `test_paper_trade_never_bypasses_oms` | ✅ PASSED |

**Full Suite**: **913 / 913 passed** (8 new + 905 existing — zero regressions)

---

## Docker Verification

```bash
# Containers after rebuild:
# - toji-redis   ✅ healthy
# - toji-postgres ✅ healthy
# - toji-app      ✅ running

curl http://localhost:8000/
# → {"name":"TOJI Trading Platform","status":"running","docs":"/docs"}

curl http://localhost:8000/health
# → {"status":"healthy","service":"toji-api"}

curl -H "X-API-KEY: change_me_admin_key" http://localhost:8000/api/v1/overview
# → {..., "active_symbols": ["BTCUSDT", "ETHUSDT"], ...}
```
