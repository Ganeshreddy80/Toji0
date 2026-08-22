# SPRINT-004 FP-4 DISCOVERY GATE
## ATR Canonical Source Migration — Architecture Audit

**Author:** TOJI Senior Staff Engineer / Implementation Architect  
**Date:** 2026-08-14  
**Governance:** TOJI CTO Architecture Governance — Sprint 004 / FP-4 Discovery  
**Predecessor Gate:** `SPRINT-004-FP3D-IMPLEMENTATION-GATE.md` — **CERTIFIED PASS**  
**Stage:** DISCOVERY / ARCHITECTURE AUDIT ONLY — Zero production code changes  
**Sprint Context:** Sprint 004 FP-4 per `SPRINT-004-FP0-CONTRACT-GATE.md` Section 10.1

---

## 1. EXECUTIVE SUMMARY

FP-4 resolves **ADR-001**, the ATR Canonical Source Decision, which was formally recorded in `SPRINT-004-FP0-CONTRACT-GATE.md` Section 4 and deferred until FP-4.

**ADR-001 Decision (already made in FP-0, immutable):**

> `pa_orch.get_atr(symbol)` is the canonical ATR for all strategy and risk decisions.  
> `FeaturePipeline.AtrTransformer` output remains **internal** to the DAG — authorised as input to `normalized_atr → risk_score` only.  
> External callers may NOT query the Feature Store for `"atr"` as a canonical risk value.

**Current violation:**  
`exit_engine/orchestrator.py` queries `fp_orch.query_realtime(["atr", ...])` to obtain an ATR value it uses to set an ATR stop-loss level. This is a boundary violation of ADR-001.

**Trade Journal secondary finding:**  
`trade_journal/orchestrator.py` queries `fp_orch.query_realtime(["atr", ...])` and stores the resulting ATR in the trade memory snapshot. This ATR is used post-trade for mistake detection, not for live risk decisions. Its migration class is different.

**FP-4 objective:**  
Migrate `exit_engine` to obtain ATR from `pa_orch.get_atr(symbol)`. Document whether `trade_journal` also requires migration. Preserve the FP-ATR internal DAG path (`atr → normalized_atr → risk_score`) as-is. Eliminate the external boundary violation. Write gate tests proving the canonical path is in place.

---

## 2. FP-4 OBJECTIVE

**Formal objective (from FP-0, Section 10.1, FP-4 block):**

> ATR CANONICAL SOURCE MIGRATION  
> • Update `exit_engine` and `trade_journal` to use `pa_orch.get_atr()` instead of `store.query_latest(["atr"])`  
> • FP-ATR remains internal to pipeline DAG (feeds `normalized_atr`)  
> • Gate: no external consumer queries Feature Store for `"atr"` as canonical

---

## 3. SCOPE / NON-SCOPE

### 3.1 In Scope

| # | Item |
|---|---|
| S-1 | `exit_engine/orchestrator.py` — migrate `atr_val` acquisition from `query_realtime(["atr"])` to `pa_orch.get_atr(symbol)` |
| S-2 | `trade_journal/orchestrator.py` — migrate `atr` acquisition in `features_dict` to `pa_orch.get_atr(symbol)` |
| S-3 | Preserve `query_realtime(["normalized_atr", "risk_score"])` in `exit_engine` — these are Feature Platform values with no PA equivalent; they remain via `query_realtime` |
| S-4 | Gate test: prove `exit_engine` uses PA-ATR for ATR stop, not FP-ATR |
| S-5 | Gate test: prove no external consumer issues `query_realtime(["atr"])` or `store.query_latest(["atr"])` for canonical external value |
| S-6 | Architecture boundary documentation |

### 3.2 Out of Scope

| # | Item | Reason |
|---|---|---|
| NS-1 | `feature_platform/transformers.py` `AtrTransformer` — do NOT modify | FP-ATR is authorised as internal DAG input to `normalized_atr` |
| NS-2 | `feature_platform/feature_pipeline.py` `"atr"` registration — do NOT remove | `normalized_atr` depends on it as a DAG input |
| NS-3 | `feature_platform/orchestrator.py` `FeatureRecord(name="atr")` — do NOT remove | Part of the 21-feature canonical registry |
| NS-4 | `normalized_atr`, `risk_score` — do NOT touch | Certified FP-3D dependencies |
| NS-5 | `annualized_vol` or any FP-3D artifact — do NOT touch | FP-3D is CLOSED |
| NS-6 | `run_paper_trading.py` line 350 `indicators["atr"] = pa_orch.get_atr(symbol)` — already correct | This already uses PA-ATR for strategy input; no change needed |
| NS-7 | `ai_signal/signal_generator.py` line 26 `pa_orch.get_atr(symbol)` — already correct | Already uses PA-ATR |
| NS-8 | `confluence/scoring_engine.py` `pa_orch.get_atr(symbol)` — already correct | Already uses PA-ATR |
| NS-9 | `strategy_framework/composer.py` `indicators.get("atr")` — already receives PA-ATR from caller | Already correct |
| NS-10 | FP-5 (determinism), FP-6 (performance baseline) — do NOT start | Out of FP-4 scope |
| NS-11 | EventBus subscriber wiring — do NOT add | ADR-003 defers to post-Sprint-004 |
| NS-12 | FeatureStore eviction policy — do NOT implement | ADR-006 defers to FP-5 |

---

## 4. ARCHITECTURE CONTEXT

### 4.1 Certified Contracts Preserved in FP-4

| Contract | Source | Status |
|---|---|---|
| Feature registration once at startup (not per-tick) | ADR-004, FP-1 | CERTIFIED |
| Downstream consumers use `query_realtime()` public API | ADR-005, FP-2 | CERTIFIED |
| Direct `store.query_latest()` from external callers is prohibited | ADR-005, FP-2 | CERTIFIED |
| EventBus events are audit/observability only | ADR-003, FP-0 | CERTIFIED |
| `annualized_vol = sample_std(log_return,1440)*sqrt(525600)` | FP-3D | CERTIFIED PASS |
| `feature name="annualized_vol"`, `target_vol=0.10`, `fallback=0.50`, `max_leverage=2.0` | FP-3D | CERTIFIED PASS |
| FP-3D is CLOSED | CTO directive | BINDING |

### 4.2 Runtime Data Flow (PROVEN from source)

```
Exchange WebSocket
    │
    ▼ process_tick(symbol, price, ts, vol)
PriceActionOrchestrator
    ├─ _calculate_atr(symbol)          ← computes PA-ATR (per bar-close)
    │   • SMA of last 14 True Ranges
    │   • stable between bar boundaries
    │   • stored in self._atr[symbol]
    │   • returns 0.0 before 2 bars
    └─ get_bars(symbol) → List[Dict]
           │
           ▼ pd.DataFrame(bars_list) — per tick
    FeaturePlatformOrchestrator.compute_and_store(features, symbol, df)
           │
           ▼ AtrTransformer (window=14) → rolling(14).mean(TR)
           │   • fills NaN→0.0 during warm-up
           │   • DAG-internal output only
           ├─ "atr"             [DAG internal — feeds normalized_atr]
           ├─ "normalized_atr"  [FP feature — exit_engine: keep via query_realtime]
           ├─ "risk_score"      [FP feature — exit_engine: keep via query_realtime]
           ├─ "annualized_vol"  [FP-3D canonical volatility — position_sizing]
           └─ (all other 21 features)
                  │
                  ▼ query_realtime(["normalized_atr","risk_score"], [symbol])
           ExitEngineOrchestrator
                  │  norm_atr_val → volatility threshold exit
                  │  risk_score_val → (future use)
                  │
                  │  ← FP-4: migrate atr_val from here ─────────────────────┐
                  │           to pa_orch.get_atr(symbol)  ←──────────────────┘
                  │
                  ▼ pa_orch.get_atr(symbol) [CANONICAL — bar-stable float]
           ExitEngineOrchestrator.check_position(symbol, price, pos)
                  • atr_val → initial_atr_stop = entry ± (atr_multiplier * atr_val)
```

---

## 5. SOURCE AUDIT

### 5.1 PA-ATR — Price Action Implementation

| Attribute | Value |
|---|---|
| **File** | `research_platform/price_action/orchestrator.py` |
| **Method** | `_calculate_atr(self, symbol, period=14)` (lines 227–242) |
| **Public API** | `get_atr(self, symbol) → float` (line 256) |
| **Algorithm** | SMA of True Range: `sum(tr_list[-14:]) / min(len(tr_list), 14)` |
| **Trigger** | Per bar-close (called from `_run_detectors`) |
| **Warm-up** | Available after 2 bars; returns 0.0 before first computation |
| **Storage** | `self._atr[symbol]` — single float per symbol |
| **Stability** | Stable between bar boundaries; never changes during intra-bar ticks |
| **Interface** | `IPriceActionOrchestrator.get_atr(symbol)` — Sprint 003 certified |
| **Fallback** | Returns `0.0` for unknown symbol |
| **Thread safety** | Writes in `_calculate_atr`; reads in `get_atr` — no locking observed (PROVEN: no lock) |

### 5.2 FP-ATR — Feature Platform Implementation

| Attribute | Value |
|---|---|
| **File** | `research_platform/feature_platform/transformers.py` |
| **Class** | `AtrTransformer(window=14)` (lines 92–112) |
| **Algorithm** | `rolling(14).mean()` of True Range on full bar DataFrame |
| **Trigger** | Per-tick via `compute_and_store()` |
| **Warm-up** | Returns 0.0 (via `fillna(0.0)`) during first 13 bars |
| **Storage** | Feature Store `_online_db["atr"]["1.0.0"][symbol]` |
| **Stability** | Potentially called per-tick on partial bars (FP called per-tick, not per bar-close) |
| **Authorization** | DAG-internal only — authorised as input to `normalized_atr → risk_score` |

### 5.3 Numerical Divergence Analysis (PROVEN by test)

```
Test: 50 synthetic 1-minute bars, random seed 42

n=bars  PA-ATR       FP-ATR       Absolute diff   Diverge?
──────  ──────────   ──────────   ─────────────   ────────
2       530.660356   0.000000     530.660356      YES
5       370.925423   0.000000     370.925423      YES
14      545.934433   535.438895   10.495538       YES
15      530.653826   530.653826   0.000000        no
20      554.662352   554.662352   0.000000        no
50      577.860363   577.860363   0.000000        no
100     618.182285   618.182285   0.000000        no
```

**Finding:** Both implementations produce **identical values at ≥15 bars**. They diverge only during the warm-up window (n < 15). The PA implementation provides a partial-warm-up estimate (uses however many TRs it has); FP returns 0.0 during warm-up.

**Implication for FP-4:** At ≥15 bars, the ATR stop computed by `exit_engine` is numerically identical whether it uses PA-ATR or FP-ATR. The migration is an architectural boundary correction, not a numerical change in steady state.

### 5.4 External ATR Consumers — Complete Map (PROVEN)

| File | Access Method | ATR Use | ADR-001 Conformant? | FP-4 Action |
|---|---|---|---|---|
| `ai_signal/signal_generator.py:26` | `pa_orch.get_atr(symbol)` | SL/TP distance | ✅ YES | None — already correct |
| `confluence/scoring_engine.py:31` | `pa_orch.get_atr(symbol)` | Proximity scoring | ✅ YES | None — already correct |
| `scripts/run_paper_trading.py:350` | `pa_orch.get_atr(symbol)` | Strategy band | ✅ YES | None — already correct |
| `exit_engine/orchestrator.py:133` | `fp_orch.query_realtime(["atr",...])` | ATR stop-loss distance | ❌ VIOLATION | **MIGRATE to `pa_orch.get_atr()`** |
| `trade_journal/orchestrator.py:192` | `fp_orch.query_realtime(["atr",...])` | Post-trade memory snapshot | ⚠️ PARTIAL | **MIGRATE (see OQ-1)** |
| `trade_memory/mistake_detector.py:28` | Receives `features.get("ATR")` dict | Entry mistake analysis | N/A (receives dict) | Migrate if trade_journal migrates |
| `feature_platform/feature_pipeline.py:48` | Internal DAG registration | Feeds `normalized_atr` | ✅ AUTHORISED | None — exempt |
| `feature_platform/orchestrator.py:94` | `FeatureRecord(name="atr")` | Feature registry | ✅ AUTHORISED | None — exempt |

### 5.5 Internal FP-ATR Consumers — EXEMPT

| File | Use | Status |
|---|---|---|
| `feature_platform/feature_pipeline.py:49` | `NormalizedAtrTransformer("atr", "close")` | AUTHORISED internal DAG |
| `feature_platform/feature_pipeline.py:50` | `RiskScoreTransformer("normalized_atr")` | AUTHORISED internal DAG |
| `exit_engine/orchestrator.py:133` | `query_realtime(["normalized_atr","risk_score"])` | AUTHORISED — these have no PA equivalent |

---

## 6. RUNTIME DATA FLOW AUDIT

### 6.1 Exit Engine ATR Flow (Current — Violates ADR-001)

```python
# exit_engine/orchestrator.py lines 126-148

atr_val = None
fp_orch = self._container.resolve("FeaturePlatformOrchestrator")
df_feat = fp_orch.query_realtime(["atr", "normalized_atr", "risk_score"], [symbol])
if df_feat is not None and not df_feat.empty:
    row = df_feat.iloc[-1]
    atr_val = row.get("atr")         # ← VIOLATION: FP-ATR used for risk decision
    norm_atr_val = row.get("normalized_atr")   # ← AUTHORISED (no PA equivalent)
    risk_score_val = row.get("risk_score")      # ← AUTHORISED (no PA equivalent)

if state.initial_atr_stop is None and self.config.atr_multiplier is not None and atr_val is not None:
    dist = self.config.atr_multiplier * atr_val
    state.initial_atr_stop = pos.average_entry - dist  # ATR stop-loss level
```

**Issue:** `atr_val` is used to compute a live risk stop-loss. This is a strategy/risk decision. ADR-001 requires this to come from `pa_orch.get_atr(symbol)`.

### 6.2 Exit Engine ATR Flow (Proposed — FP-4)

```python
# Proposed: exit_engine/orchestrator.py

# PA-ATR for ATR stop-loss (canonical per ADR-001)
atr_val = None
if self._container and self._container.has("PriceActionOrchestrator"):
    pa_orch = self._container.resolve("PriceActionOrchestrator")
    pa_atr = pa_orch.get_atr(symbol)
    if pa_atr > 0.0:
        atr_val = pa_atr

# FP features for volatility/risk-score exits (no PA equivalent — remain via query_realtime)
norm_atr_val = None
risk_score_val = None
try:
    if self._container and self._container.has("FeaturePlatformOrchestrator"):
        fp_orch = self._container.resolve("FeaturePlatformOrchestrator")
        df_feat = fp_orch.query_realtime(["normalized_atr", "risk_score"], [symbol])
        if df_feat is not None and not df_feat.empty:
            row = df_feat.iloc[-1]
            norm_atr_val = row.get("normalized_atr")
            risk_score_val = row.get("risk_score")
except Exception as e:
    logger.debug("ExitEngine: error querying features: %s", e)
```

### 6.3 Trade Journal ATR Flow (Current — Partial Violation)

```python
# trade_journal/orchestrator.py lines 191-203

latest_df = feature_platform.query_realtime([
    "rsi", "ema9", "ema21", "ema50", "atr", "trend",   # ← "atr" is violation
    "support", "resistance", "breakout", "volume_change"
], [order.symbol])
features_dict = {
    "ATR": feat_row.get("atr", 0.0),   # stored in trade memory
    "atr": feat_row.get("atr", 0.0),
    ...
}
memory_engine.save_trade(..., features_at_entry=features_dict)
```

**Mitigating factor:** The ATR here is stored as a historical snapshot for post-trade analysis (mistake detection, learning). It is NOT used to trigger a live risk decision. See OQ-1 below.

---

## 7. EXISTING CAPABILITY MATRIX

| Component | FP-4 Relevant State | Evidence |
|---|---|---|
| `PriceActionOrchestrator.get_atr(symbol)` | PROVEN in production; Sprint 003-certified | `orchestrator.py:256`, `interfaces.py:35` |
| `IPriceActionOrchestrator.get_atr()` | Interface certified in Sprint 003 | `interfaces.py:35` |
| `ExitEngineOrchestrator.__init__(event_bus, container)` | Has `self._container` (DI container) | `orchestrator.py:32-34` |
| `container.has("PriceActionOrchestrator")` | PROVEN used in `live_trading/plugin.py` | `plugin.py:180` (INFERRED from pattern) |
| `feature_platform.query_realtime(["normalized_atr","risk_score"])` | Already used in exit_engine:133 | Stays unchanged |
| `test_exit_engine_atr_stop` | **PRE-EXISTING FAILURE** before FP-4 | `assert 0 == 1` — DB service not registered |
| 8 other exit_engine tests | ALL PASS | baseline 8/9 |

---

## 8. FINDINGS

### F-1 [CRITICAL] — exit_engine queries FP-ATR for live ATR stop-loss (ADR-001 violation)

- **File:** `research_platform/exit_engine/orchestrator.py:133`
- **Symbol:** `ExitEngineOrchestrator.check_position()`
- **Behavior:** Queries `fp_orch.query_realtime(["atr", ...])` and uses `atr_val` to set `initial_atr_stop` — a live risk decision
- **Evidence:** Lines 126–148. `atr_multiplier * atr_val` computes ATR stop distance.
- **ADR-001 rule:** External consumers of ATR for strategy/risk decisions must use `pa_orch.get_atr()`
- **Severity:** HIGH (architectural boundary violation)
- **FP-4 scope:** YES — primary migration target

### F-2 [HIGH] — trade_journal queries FP-ATR for memory snapshot

- **File:** `research_platform/trade_journal/orchestrator.py:192`
- **Symbol:** `TradeJournalOrchestrator` (post-trade callback)
- **Behavior:** Queries `query_realtime(["atr", ...])` and stores in `features_at_entry`. Used by `MistakeDetector` for post-trade analysis.
- **Evidence:** Lines 191–203
- **Severity:** MEDIUM — not a live risk decision; used for retrospective analysis
- **FP-4 scope:** YES per FP-0 Section 10.1, but see OQ-1 for semantic nuance

### F-3 [MEDIUM] — test_exit_engine_atr_stop is a pre-existing failure

- **File:** `research_platform/tests/test_exit_engine.py:284–322`
- **Behavior:** Test injects ATR directly into `FeatureStore` (`feat_orch.store.save_features("atr", ...)`), then expects ATR_STOP to trigger. Fails because `AccountingService.on_fill` cannot write to SQLite in test environment — same pre-existing DB infrastructure gap as FP-2 certified regression.
- **Evidence:** `assert 0 == 1` — `events_triggered` is empty; log shows `"Database service not registered in ServiceRegistry"`
- **Severity:** MEDIUM — this test's injection pattern is itself a boundary violation (injects directly into store) that will be replaced by FP-4 test
- **FP-4 scope:** YES — FP-4 will replace this test with a PA-ATR-aware version that does not inject into FeatureStore

### F-4 [MEDIUM] — run_paper_trading.py computes FP-ATR via compute_and_store then overwrites with PA-ATR

- **File:** `scripts/run_paper_trading.py:295,350`
- **Behavior:** Line 295 includes `"atr"` in `features_to_compute` for `compute_and_store()`. Line 350 then overwrites `indicators["atr"] = pa_orch.get_atr(symbol)`. The FP-ATR computed on line 295 is stored in Feature Store but never read by the `indicators` dict; it is overwritten.
- **Evidence:** Lines 293–350. `indicators = clean_features.copy()` (which includes FP-ATR), then `indicators["atr"] = pa_orch.get_atr(symbol)` overwrites it.
- **Severity:** LOW — the strategy/risk path correctly uses PA-ATR. The FP-ATR stored in the Feature Store is only consumed by `exit_engine` (violation) and `trade_journal` (partial). Computing FP-ATR in `features_to_compute` is authorised (it feeds `normalized_atr` DAG).
- **FP-4 scope:** No production change needed here. However, the comment at line 339 (`"[FEATURE] RSI EMA ATR calculated"`) is misleading — the ATR actually used downstream comes from PA, not Feature Platform. Documentation fix only.

### F-5 [LOW] — trade_memory/mistake_detector.py reads ATR from features dict

- **File:** `research_platform/trade_memory/mistake_detector.py:28`
- **Behavior:** `atr = float(features.get("ATR", 0.0) or features.get("atr", 0.0))`. Receives a dict from `trade_journal`; does not query Feature Store directly.
- **Evidence:** Lines 24–29. Passive receiver.
- **Severity:** LOW — downstream of trade_journal; migrates automatically if trade_journal migrates
- **FP-4 scope:** Indirect; no direct change needed

### F-6 [LOW] — query_realtime(["atr"]) produces Feature Platform ATR, not PA-ATR

- **Symbol:** `FeaturePlatformOrchestrator.query_realtime()`
- **Behavior:** When called with `["atr"]`, returns the last row from the Feature Store `_online_db["atr"]`, which contains values computed by `AtrTransformer`. Callers cannot distinguish this from PA-ATR by value at ≥15 bars.
- **Severity:** LOW — numerically identical at ≥15 bars; only semantically wrong at warm-up (where FP returns 0.0, PA returns a partial estimate)
- **FP-4 scope:** Eliminated by migrating callers, not by changing the Feature Platform

---

## 9. RISK REGISTER

### CRITICAL

None.

### HIGH

| ID | Risk | Evidence | Impact | Resolution | FP-4? |
|---|---|---|---|---|---|
| R-1 | `exit_engine` ATR stop-loss computed from FP-ATR instead of PA-ATR | F-1: `orchestrator.py:133` | Stop-loss placed at 0.0 distance during warm-up (FP returns 0.0); correct at ≥15 bars but semantically wrong ownership | Migrate to `pa_orch.get_atr()` | **YES** |
| R-2 | `test_exit_engine_atr_stop` is a pre-existing failure with wrong injection pattern | F-3: test injects into FeatureStore | FP-4 migration has no existing passing regression baseline for ATR stop | Replace test with PA-ATR-aware version | **YES** |

### MEDIUM

| ID | Risk | Evidence | Impact | Resolution | FP-4? |
|---|---|---|---|---|---|
| R-3 | `trade_journal` stores FP-ATR in trade memory | F-2: `orchestrator.py:192` | Trade memory ATR may differ from actual entry ATR used by `ai_signal`/strategy | Migrate to `pa_orch.get_atr()` | YES (per OQ-1) |
| R-4 | `PriceActionOrchestrator` may not be registered in all containers that host `ExitEngine` | INFERRED — not all test fixtures register PA | ATR migration would fail silently if PA is absent from container | Verify container wiring in every `ExitEngine` deployment path; add defensive fallback | YES |
| R-5 | `ExitEngineOrchestrator` has no `PriceActionOrchestrator` reference today | F-1: constructor takes `event_bus, container` only | Migration adds a `container.resolve("PriceActionOrchestrator")` call — container registration must be verified | Check all call sites that instantiate `ExitEngineOrchestrator`; verify PA is registered | YES |

### LOW

| ID | Risk | Evidence | Impact | Resolution | FP-4? |
|---|---|---|---|---|---|
| R-6 | Comment at `run_paper_trading.py:339` (`"[FEATURE] RSI EMA ATR calculated"`) implies FP-ATR is authoritative | F-4 | Developer confusion | Update comment (documentation only) | YES (comment only) |
| R-7 | `atr_val` in `exit_engine` is set only once (when `initial_atr_stop is None`) | F-1: line 143 check | ATR stop is latched at position open time; even if PA-ATR later diverges, stop does not move | By design — position is opened once; ATR at open is the canonical reference | N/A (by design) |
| R-8 | AtrTransformer `fillna(0.0)` during warm-up | `transformers.py:112` | 0.0 ATR causes `atr_val is None` check to fail (0.0 is falsy) | PA-ATR is used instead; warm-up is handled by PA's partial estimate | Eliminated by FP-4 |

---

## 10. CERTIFIED CONTRACTS PRESERVED

The following contracts are NOT changed by FP-4:

| # | Contract | Gate |
|---|---|---|
| C-1 | Feature registration once at startup | FP-1 CERTIFIED |
| C-2 | `query_realtime()` is the public query API | FP-2 CERTIFIED |
| C-3 | `store.query_latest()` not called directly from external callers | FP-2 CERTIFIED |
| C-4 | EventBus = audit/observability only | ADR-003 |
| C-5 | `AtrTransformer` remains internal DAG node — NOT removed | ADR-001 consequence |
| C-6 | `FeatureRecord(name="atr")` remains in registry (21 features) | ADR-001 consequence |
| C-7 | `annualized_vol` formula, params, and key | FP-3D CERTIFIED PASS |
| C-8 | `normalized_atr` = `atr / close` — unchanged | FP-3D upstream |
| C-9 | `risk_score` = z-score of `normalized_atr` — unchanged | FP-3D upstream |
| C-10 | FP-3D is CLOSED | CTO directive |

**Contradiction check:** No FP-4 change conflicts with any of the above. The migration does NOT:
- Remove `AtrTransformer`
- Remove `atr` from the feature registry
- Change `normalized_atr` or `risk_score`
- Change any FP-3D artifact

---

## 11. PROPOSED FP-4 CONTRACT

### 11.1 Objective

Correct the ownership boundary for ATR consumption in `ExitEngineOrchestrator` and `TradeJournalOrchestrator` to comply with ADR-001.

### 11.2 Inputs

| Input | Source | API |
|---|---|---|
| ATR (absolute float) | `PriceActionOrchestrator` | `pa_orch.get_atr(symbol) → float` |
| `normalized_atr` | Feature Platform | `fp_orch.query_realtime(["normalized_atr"], [symbol])` |
| `risk_score` | Feature Platform | `fp_orch.query_realtime(["risk_score"], [symbol])` |

### 11.3 Outputs / Invariants

| Invariant | Proof |
|---|---|
| `exit_engine` ATR stop distance uses `pa_orch.get_atr(symbol)` | Test: mock PA returns 100.0; assert `initial_atr_stop = entry ∓ (multiplier * 100.0)` |
| `exit_engine` does NOT query `query_realtime(["atr"])` | Test: assert `"atr"` is NOT in the feature names passed to `query_realtime` |
| `exit_engine` STILL queries `query_realtime(["normalized_atr","risk_score"])` | Test: mock FP returns non-null; volatility exit still triggers |
| `trade_journal` ATR snapshot uses `pa_orch.get_atr(symbol)` (if OQ-1 → YES) | Test: verify `features_dict["atr"] == pa_atr_value` |
| No other external consumer queries `store.query_latest(["atr"])` as canonical | Static grep + assertion |

### 11.4 Error Behavior

| Condition | Behavior |
|---|---|
| PA not registered in container | Log at DEBUG; `atr_val = None`; skip ATR stop (same as current behavior when Feature Store is empty) |
| PA returns 0.0 (before 2 bars) | `atr_val = None` via `if pa_atr > 0.0`; skip ATR stop |
| `query_realtime(["normalized_atr","risk_score"])` returns empty | Log at DEBUG; `norm_atr_val = None`; skip volatility exit |

### 11.5 Determinism Requirements

ATR stop is set once per position (when `initial_atr_stop is None`). The value used is `pa_orch.get_atr(symbol)` at the moment `PositionValuationUpdated` is first received. This is deterministic given the same bar sequence (PA-ATR is deterministic per PA-4 certification).

### 11.6 Performance Expectations

`pa_orch.get_atr(symbol)` is `self._atr.get(symbol, 0.0)` — a single dict lookup, O(1). This is strictly faster than the current `query_realtime()` call which involves a Feature Store lookup. **PROVEN:** No performance regression possible.

---

## 12. TEST STRATEGY

### 12.1 Existing Tests

| Test | Current Status | FP-4 Action |
|---|---|---|
| `test_exit_engine_stop_loss_pct` | PASS | None — unaffected |
| `test_exit_engine_take_profit_pct` | PASS | None — unaffected |
| `test_exit_engine_trailing_stop` | PASS | None — unaffected |
| `test_exit_engine_break_even` | PASS | None — unaffected |
| `test_exit_engine_time_stop` | PASS | None — unaffected |
| `test_exit_engine_atr_stop` | **PRE-EXISTING FAIL** | Replace with PA-ATR-aware version |
| `test_exit_engine_summary` | PASS | None — unaffected |
| `test_exit_engine_e2e_pipeline` | PASS | None — unaffected |
| `test_exit_engine_recovery_from_rejected_order` | PASS | None — unaffected |

### 12.2 New Tests Required for FP-4

| Test ID | Description | Acceptance |
|---|---|---|
| T-1 | ATR stop uses PA-ATR: mock `PriceActionOrchestrator.get_atr()` to return 100.0; assert `initial_atr_stop = 10000.0 - 200.0 = 9800.0` (multiplier=2.0) | ATR_STOP triggers at 9790, not at 9850 |
| T-2 | `query_realtime` NOT called with `"atr"` by ExitEngine: capture all `query_realtime` calls; assert `"atr"` not in any call's feature list | Zero `query_realtime(["atr"])` calls |
| T-3 | `query_realtime` IS called with `["normalized_atr","risk_score"]` by ExitEngine | `query_realtime` called with norm_atr and risk_score |
| T-4 | PA unavailable: if container has no PA, ATR stop gracefully skipped | `initial_atr_stop is None`; no exception |
| T-5 | PA returns 0.0 (warm-up): `atr_val = None`, ATR stop not set | `initial_atr_stop is None` |
| T-6 | `trade_journal` ATR snapshot = PA-ATR value (if OQ-1 → YES) | `features_dict["atr"] == pa_orch.get_atr()` |
| T-7 | Global grep assertion: no production file outside feature_platform calls `query_realtime(["atr"])` as sole ATR source | Zero matches in exit_engine, trade_journal |

### 12.3 Regression Requirements

All 8 currently-passing exit_engine tests must remain passing after FP-4.

---

## 13. ACCEPTANCE CRITERIA

FP-4 is COMPLETE when ALL of the following are true:

| # | Criterion |
|---|---|
| AC-1 | `exit_engine/orchestrator.py` obtains `atr_val` from `pa_orch.get_atr(symbol)` — source-verified |
| AC-2 | `exit_engine/orchestrator.py` does NOT pass `"atr"` to `query_realtime()` — source-verified |
| AC-3 | `exit_engine/orchestrator.py` STILL passes `"normalized_atr"` and `"risk_score"` to `query_realtime()` — source-verified |
| AC-4 | `trade_journal/orchestrator.py` obtains ATR from `pa_orch.get_atr(symbol)` — source-verified (pending OQ-1) |
| AC-5 | All 8 previously-passing `test_exit_engine_*` tests continue to PASS |
| AC-6 | `test_exit_engine_atr_stop` replaced with PA-ATR-aware test that PASSES |
| AC-7 | No `AtrTransformer` removed, no `FeatureRecord(name="atr")` removed |
| AC-8 | `normalized_atr` and `risk_score` continue to compute correctly |
| AC-9 | FP-3D features (`annualized_vol`, `SizingConfig`, `PositionSizingOrchestrator`) unmodified |
| AC-10 | `run_paper_trading.py:350` `indicators["atr"] = pa_orch.get_atr(symbol)` — unchanged |
| AC-11 | Log comment at `run_paper_trading.py:339` updated to reflect PA-ATR ownership |

---

## 14. CTO DECISIONS / OPEN QUESTIONS

### OQ-1 — trade_journal ATR semantic classification

**Question:** Should `TradeJournalOrchestrator`'s ATR snapshot be migrated to `pa_orch.get_atr(symbol)`?

**Evidence already known:**
- Trade journal uses ATR to record `features_at_entry` in trade memory. This snapshot is used by `MistakeDetector.detect_mistakes()` retrospectively — it is NOT used to make a live risk decision.
- The ATR value in the trade memory snapshot should represent "what ATR was visible to the system at the moment of trade execution." At trade execution, the signal generators (`ai_signal`, `confluence`) use `pa_orch.get_atr(symbol)`. Therefore the canonical value at execution time IS the PA-ATR.
- FP-0 Section 10.1 explicitly lists `trade_journal` as a FP-4 migration target.

**Available choices:**
- A. Migrate to `pa_orch.get_atr(symbol)` — consistent with ADR-001; snapshot reflects actual execution-time ATR
- B. Leave as FP-ATR — acceptable if retrospective analysis only and values are identical at ≥15 bars

**Recommended CTO choice:** A. Migrate to `pa_orch.get_atr(symbol)`. The snapshot should reflect the ATR actually used by the strategy at execution time, which is PA-ATR.

**Stage blocked:** FP-4 implementation of `trade_journal` migration. Exit engine migration can proceed regardless.

**Urgency:** LOW (no live risk decision affected). CTO may authorize FP-4 implementation of `exit_engine` only, deferring `trade_journal` migration.

---

## 15. EXACT IMPLEMENTATION PLAN

> **Status: PROPOSED — requires CTO authorization before any code is written.**

### Step 1 — exit_engine/orchestrator.py (Primary — HIGH priority)

**File:** `research_platform/exit_engine/orchestrator.py`

**Change:**

```python
# BEFORE (lines 126-140) — VIOLATION
atr_val = None
norm_atr_val = None
risk_score_val = None
try:
    if self._container and self._container.has("FeaturePlatformOrchestrator"):
        fp_orch = self._container.resolve("FeaturePlatformOrchestrator")
        df_feat = fp_orch.query_realtime(["atr", "normalized_atr", "risk_score"], [symbol])
        if df_feat is not None and not df_feat.empty:
            row = df_feat.iloc[-1]
            atr_val = row.get("atr")
            norm_atr_val = row.get("normalized_atr")
            risk_score_val = row.get("risk_score")
except Exception as e:
    logger.debug("ExitEngine: error querying features via query_realtime: %s", e)

# AFTER (ADR-001 compliant)
# 1. PA-ATR for ATR stop-loss (canonical per ADR-001)
atr_val = None
if self._container and self._container.has("PriceActionOrchestrator"):
    try:
        pa_orch = self._container.resolve("PriceActionOrchestrator")
        pa_atr = pa_orch.get_atr(symbol)
        if pa_atr > 0.0:
            atr_val = pa_atr
    except Exception as e:
        logger.debug("ExitEngine: error resolving PriceActionOrchestrator: %s", e)

# 2. FP features for volatility/risk-score exits (no PA equivalent)
norm_atr_val = None
risk_score_val = None
try:
    if self._container and self._container.has("FeaturePlatformOrchestrator"):
        fp_orch = self._container.resolve("FeaturePlatformOrchestrator")
        df_feat = fp_orch.query_realtime(["normalized_atr", "risk_score"], [symbol])
        if df_feat is not None and not df_feat.empty:
            row = df_feat.iloc[-1]
            norm_atr_val = row.get("normalized_atr")
            risk_score_val = row.get("risk_score")
except Exception as e:
    logger.debug("ExitEngine: error querying features via query_realtime: %s", e)
```

**Lines affected:** 126–140 only. All downstream logic (`initial_atr_stop`, `ATR_STOP`, `VOLATILITY` check) is unchanged.

---

### Step 2 — trade_journal/orchestrator.py (Conditional on OQ-1 → A)

**File:** `research_platform/trade_journal/orchestrator.py`

**Change (approximate):**

```python
# BEFORE: features_dict["atr"] from query_realtime(["atr", ...])
# AFTER: obtain ATR from PA before feature query
pa_atr_val = 0.0
pa_orch = self._resolve("PriceActionOrchestrator")
if pa_orch:
    pa_atr_val = pa_orch.get_atr(order.symbol)

latest_df = feature_platform.query_realtime([
    "rsi", "ema9", "ema21", "ema50", "trend",
    "support", "resistance", "breakout", "volume_change"
    # "atr" removed — obtained from PA
], [order.symbol])

features_dict = {
    "ATR": pa_atr_val,
    "atr": pa_atr_val,
    ...  # all other fields from feat_row unchanged
}
```

---

### Step 3 — test_exit_engine.py (ATR stop test replacement)

Replace `test_exit_engine_atr_stop` pattern:
- Current: injects ATR directly into `FeatureStore` (boundary violation in test)
- New: registers mock `PriceActionOrchestrator` in fixture that returns `100.0` from `get_atr()`
- Assert: `initial_atr_stop = entry - (multiplier * pa_atr) = 10000.0 - 200.0 = 9800.0`
- Assert: `"atr"` NOT in any `query_realtime` call arguments

---

### Step 4 — run_paper_trading.py (comment only)

Update line 339 comment from `"[FEATURE] RSI EMA ATR calculated"` to clarify:  
`"[FEATURE] RSI EMA calculated. ATR for strategy decisions sourced from PriceActionOrchestrator (ADR-001)."`

---

### Step 5 — FP-4 Gate Document

Create `docs/architecture/SPRINT-004-FP4-IMPLEMENTATION-GATE.md` after implementation verifying:
- All AC-1 through AC-11 pass
- Test results for all 9+ exit_engine tests
- Source diffs confirming no FP-3D artifacts touched
- Grep evidence: zero `query_realtime(["atr"])` calls in `exit_engine` or `trade_journal`

---

## 16. GATE CLASSIFICATION

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   SPRINT-004 FP-4 DISCOVERY GATE:                                            ║
║   COMPLETE — AWAITING CTO AUTHORIZATION FOR IMPLEMENTATION                   ║
║                                                                              ║
║   FP-4 Objective:  ATR Canonical Source Migration (ADR-001)                  ║
║                                                                              ║
║   Primary violation:                                                          ║
║     exit_engine/orchestrator.py — queries FP-ATR for live ATR stop-loss     ║
║     → must migrate to pa_orch.get_atr() [PROVEN: source lines 126-148]      ║
║                                                                              ║
║   Secondary migration:                                                        ║
║     trade_journal/orchestrator.py — ATR in trade memory snapshot             ║
║     → pending OQ-1 CTO decision (recommended: migrate)                       ║
║                                                                              ║
║   Already conformant (no change):                                             ║
║     ai_signal, confluence, run_paper_trading, strategy_composer              ║
║                                                                              ║
║   Exempt (internal DAG — do NOT touch):                                       ║
║     AtrTransformer → normalized_atr → risk_score pipeline                   ║
║     FeatureRecord(name="atr") in registry                                    ║
║                                                                              ║
║   Key finding: At ≥15 bars, PA-ATR == FP-ATR numerically.                   ║
║   Migration is architectural boundary correction, not numerical change.       ║
║                                                                              ║
║   Open Questions Requiring CTO Decision: 1 (OQ-1)                            ║
║   OQ-1 does NOT block exit_engine migration.                                  ║
║   OQ-1 blocks trade_journal migration only.                                   ║
║                                                                              ║
║   Pre-existing failure: test_exit_engine_atr_stop (pre-FP-4 baseline)        ║
║     → same DB infrastructure class as FP-2 certified regression              ║
║     → will be REPLACED by PA-ATR-aware test in FP-4                          ║
║                                                                              ║
║   Production files to be modified: 2 (exit_engine, trade_journal)            ║
║   Test files to be modified: 1 (test_exit_engine.py)                         ║
║   Documentation files: 1 comment update (run_paper_trading.py)               ║
║                                                                              ║
║   STOP. Awaiting CTO authorization before implementation begins.              ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

**Production files modified in this discovery stage: 0**  
**Test files modified in this discovery stage: 0**  
**New documentation files: 1 (this document)**

**STOP.** Discovery audit is complete. Returning gate document for CTO review and FP-4 authorization.
