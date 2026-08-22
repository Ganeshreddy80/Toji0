# PORTFOLIO GOVERNOR — Architecture Audit Report
## TOJI Autonomous Trading Platform — Phase 12

**Date:** 2026-07-10
**Author:** CTO Engineering Audit
**Status:** IMPLEMENTED ✅

---

## 1. Problem Statement

After Phase 11 (Paper Execution Routing), TOJI was generating and filling paper orders correctly.
However, the system lacked **position-level governance**: there was no layer preventing:

- Duplicate positions on the same symbol (e.g., buying BTCUSDT when already long BTCUSDT)
- Runaway trading within a short time window (no rate limiting per symbol)
- Portfolio overexposure (no limit on open positions or total capital deployed)

**Observed symptom:** Hundreds of paper fills in seconds on the same symbol, all BTCUSDT LONG.

---

## 2. Before vs After

### Before
```
Binance WS Tick
  ↓
FeatureEngine → Strategy → AISignal
  ↓
LiveTradingOrchestrator.ingest_market_signal()
  ↓
TradeManager (no position check)
  ↓
PaperExecutionRouter → PaperTradingOrchestrator → FILLED
```

### After
```
Binance WS Tick
  ↓
FeatureEngine → Strategy → AISignal
  ↓
LiveTradingOrchestrator.ingest_market_signal()
  ↓
PortfolioGovernor.evaluate(signal)         ← NEW GATE
  ├─ CooldownEngine.check(symbol)          → COOLDOWN_ACTIVE?
  ├─ ExposureManager.check()               → DUPLICATE_POSITION | MAX_POSITIONS | EXPOSURE_LIMIT?
  └─ APPROVED
       ↓
     TradeManager
       ↓
     PaperExecutionRouter → FILLED
       ↓
     PortfolioGovernor.record_fill()       ← NEW: updates position registry + starts cooldown
```

---

## 3. New Module: `research_platform/portfolio_governor/`

| File | Responsibility |
|------|---------------|
| `models.py` | `GovernedPosition`, `PortfolioDecision`, `GovernorConfig` — Pydantic models |
| `interfaces.py` | `IPortfolioGovernor` abstract contract |
| `events.py` | `PortfolioDecisionCreated`, `GovernorPositionOpened/Updated/Closed` events |
| `position_manager.py` | Thread-safe registry — open/reduce/price-update |
| `exposure_manager.py` | Duplicate position + max-positions + exposure ratio checks |
| `cooldown_engine.py` | Per-symbol trade cooldown enforcement with RLock |
| `governor.py` | `PortfolioGovernor` — orchestrates all three engines |
| `plugin.py` | DI plugin: reads env vars, creates governor, registers in container |

---

## 4. Configuration (Zero-Code Tuning)

All limits are read from environment variables at boot:

| Env Var | Default | Description |
|---------|---------|-------------|
| `PG_MAX_POSITIONS` | `5` | Maximum simultaneous open positions |
| `PG_MAX_EXPOSURE_PCT` | `0.80` | Maximum portfolio exposure (0.0–1.0) |
| `PG_MAX_SYMBOL_PCT` | `0.25` | Maximum per-symbol allocation |
| `PG_COOLDOWN_SECONDS` | `300` | Default per-symbol trade cooldown |
| `PG_ALLOW_OPPOSITE_SIDE` | `false` | Allow same-symbol opposite direction |

Per-symbol cooldown overrides can be set in `GovernorConfig.symbol_cooldowns`.

---

## 5. Decision Logic

### Gate 1 — Cooldown
```
CooldownEngine.check(symbol)
  → elapsed < cooldown_seconds? BLOCK (COOLDOWN_ACTIVE)
  → else: PASS
```

### Gate 2 — Exposure / Duplicate / Max Positions
```
ExposureManager.check(symbol, direction, open_positions)
  → same symbol AND same side already open? BLOCK (DUPLICATE_POSITION)
  → same symbol, opposite side?            ALLOW (closing trade)
  → open_count >= max_open_positions?      BLOCK (MAX_POSITIONS)
  → (open_count+1)/max_positions > 80%?   BLOCK (EXPOSURE_LIMIT)
  → else: APPROVED
```

---

## 6. Files Modified (Existing)

| File | Change |
|------|--------|
| `research_platform/live_trading/orchestrator.py` | Accept `governor` param; gate `ingest_market_signal()` pre-TradeManager; call `record_fill()` post-success |
| `research_platform/live_trading/plugin.py` | Resolve `PortfolioGovernor` from DI container; inject into orchestrator |
| `toji_platform/runtime/state.py` | Added `governor_blocked_*` + `governor_approved` counters with persist/load |
| `backend/main.py` | Added `portfolio` key to `/api/v1/runtime/status`; added `_get_portfolio_summary()` helper |

---

## 7. Safety Invariants — All Preserved

| Invariant | Status |
|-----------|--------|
| `ExecutionEngineOrchestrator` `PermissionError` for paper mode | ✅ Untouched |
| OMS ingestion always runs first (before EMS/Paper) | ✅ Confirmed |
| Binance exchange never reached in paper mode | ✅ Confirmed |
| Governor is **optional** (None = no governance, signals pass through) | ✅ Graceful degradation |
| Governor block does NOT prevent OMS recording — only execution | ✅ By design |

---

## 8. Runtime Status API — New `portfolio` Key

```json
GET /api/v1/runtime/status

{
  "portfolio": {
    "open_positions": 2,
    "exposure": 0.4,
    "unrealized_pnl": 120.50,
    "realized_pnl": 42.20,
    "approved_trades": 15,
    "blocked_trades": {
      "cooldown": 10,
      "duplicate": 5,
      "exposure": 2,
      "max_positions": 0
    },
    "positions": [
      {
        "symbol": "BTCUSDT",
        "side": "LONG",
        "quantity": 1.0,
        "avg_entry": 50000.0,
        "current_price": 50200.0,
        "unrealized_pnl": 200.0,
        "realized_pnl": 0.0,
        "opened_at": "2026-07-10T16:00:00+00:00"
      }
    ]
  }
}
```

---

## 9. Test Results

```
tests/e2e/test_portfolio_governor.py — 17/17 PASSED ✅

Scenario 1 — First BUY BTC → APPROVED                                    PASS
Scenario 2 — Second BUY BTC (duplicate) → BLOCKED (DUPLICATE_POSITION)   PASS
Scenario 2 — SELL to close LONG → ALLOWED                                 PASS
Scenario 3 — Trade within cooldown window → BLOCKED (COOLDOWN_ACTIVE)     PASS
Scenario 3 — Trade after cooldown expires → APPROVED                      PASS
Scenario 4 — Max positions exceeded → BLOCKED (MAX_POSITIONS)             PASS
Scenario 4 — Exposure limit triggered → BLOCKED (EXPOSURE_LIMIT)          PASS
Scenario 5 — Different symbol while BTC open → APPROVED                   PASS
Scenario 6 — Rejected signals never reach TradeManager (mock assert)      PASS
Scenario 7 — Paper execution imports cleanly (backward compat)            PASS
Scenario 7 — portfolio_summary() returns required keys                    PASS
PositionManager — open_and_get                                            PASS
PositionManager — reduce_to_zero_removes                                  PASS
PositionManager — weighted_average_entry                                  PASS
CooldownEngine  — no_cooldown_initially                                   PASS
CooldownEngine  — active_immediately_after_trade                          PASS
CooldownEngine  — per_symbol_override                                     PASS

Full Unit + Integration suite: 946 passed, 0 new failures ✅
Pre-existing failures (unrelated): 1 failed + 3 errors (backend kernel guard)
```

---

## 10. Post-Deploy Verification

```bash
docker compose restart app

# After 60 seconds:
curl -H "X-API-Key: toji_sec_admin_key_9931882c81a" \
     http://localhost:8000/api/v1/runtime/status | python3 -m json.tool

# Expect:
# portfolio.open_positions → incrementing
# portfolio.blocked_trades.duplicate → incrementing (duplicate BTC signals blocked)
# portfolio.blocked_trades.cooldown → incrementing after first fill
# paper_orders → incrementing (but much slower than before)

# Confirm no duplicate fills flooding:
docker compose logs app --since 5m | grep "BLOCKED by PortfolioGovernor"
```
