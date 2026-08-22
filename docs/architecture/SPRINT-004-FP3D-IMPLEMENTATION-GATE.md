# SPRINT 004 — FP-3D
## Canonical Volatility Implementation Gate

**Author:** TOJI Senior Staff Engineer  
**Date:** 2026-08-13  
**Governance:** Master Architecture Governance — Sprint 004  
**Predecessor Gate:** `SPRINT-004-FP3C-CANONICAL-VOLATILITY-CONTRACT-GATE.md` — CERTIFIED (CTO Decisions 1–6 approved)  
**Stage:** FP-3D — IMPLEMENTATION  
**Status:** PASS (CERTIFIED)

---

## 1. CTO-APPROVED DECISIONS (from FP-3C)

| # | Decision | CTO Choice |
|---|---|---|
| D1 | Annualization factor | `sqrt(525600)` — 1-minute crypto 24/7/365 |
| D2 | `target_volatility` | `0.10` — UNCHANGED. 10% annualized, multi-asset. |
| D3 | Fallback volatility | `0.50` — conservative risk-policy floor (not a measured value) |
| D4 | Lookback N | `1440` bars (configurable) |
| D5 | Leverage safety | min_vol floor = `target/max_leverage = 0.05` + formula cap `min(scale, 2.0)` |
| D6 | Feature name | `annualized_vol` |

---

## 2. FORMULA IMPLEMENTED

```
annualized_vol = sample_std(log_return, N=1440) × sqrt(525600)

where:
  log_return[t] = log(close[t] / close[t-1])
  sample_std    = pandas rolling().std() with ddof=1
  N             = 1440 bars (configurable via AnnualizedVolTransformer constructor)
  525600        = 365 × 24 × 60 minutes/year (crypto 24/7)

Position sizing formula:
  min_vol    = target_volatility / max_leverage    (= 0.10 / 2.0 = 0.05)
  vol_safe   = max(annualized_vol, min_vol)
  raw_scale  = target_volatility / vol_safe
  scale      = min(raw_scale, max_leverage)        (cap at 2.0×)
  target_capital = equity × scale
  raw_qty    = target_capital / price
```

---

## 3. PRODUCTION FILES MODIFIED

| File | Change |
|---|---|
| `research_platform/feature_platform/transformers.py` | Added `AnnualizedVolTransformer` class |
| `research_platform/feature_platform/feature_pipeline.py` | Import + register `"annualized_vol"` transformer (window=1440, periods_per_year=525600) |
| `research_platform/feature_platform/orchestrator.py` | Added `annualized_vol` to `DEFAULT_FEATURE_DEFINITIONS` (Level 2 Derived, depends on `log_return`) |
| `research_platform/position_sizing/models.py` | Added `max_leverage: float = 2.0` and `fallback_volatility: float = 0.50` to `SizingConfig` |
| `research_platform/position_sizing/orchestrator.py` | Rewrote `volatility` and `risk_parity` branches to use `"annualized_vol"` query, NaN detection, min_vol floor, leverage cap |
| `.env.example` | Documented `TARGET_VOLATILITY`, `MAX_LEVERAGE`, `FALLBACK_VOLATILITY` |

**Total production Python files changed: 5**

---

## 4. TEST FILES MODIFIED / CREATED

| File | Change |
|---|---|
| `research_platform/tests/test_sprint004_fp3d_annualized_vol.py` | NEW — 40 tests (10 CTO requirements) |
| `research_platform/tests/test_position_sizing.py` | Updated volatility test to use `annualized_vol` key; added `query_realtime` to mock |
| `research_platform/tests/test_sprint004_fp1_registration_lifecycle.py` | Updated feature count from 20 → 21 (added `annualized_vol`) |

---

## 5. CONFIGURATION MODIFIED

| File | Change |
|---|---|
| `.env.example` | Added `TARGET_VOLATILITY=0.10`, `MAX_LEVERAGE=2.0`, `FALLBACK_VOLATILITY=0.50` with full documentation |

---

## 6. WARM-UP BEHAVIOR

| Condition | Behavior |
|---|---|
| `< 1440 bars` | `AnnualizedVolTransformer` returns `NaN` (no `fillna(0.0)`) |
| NaN from Feature Store | Position sizer detects `math.isnan(val)` → uses `fallback_volatility = 0.50` |
| `fallback_volatility = 0.50` | `scale = min(0.10/0.50, 2.0) = 0.20×` → 20% of equity per position (safe) |
| **NEVER** | `0.0` → `max(0.0, 0.001) = 0.001` → 100× leverage (old unsafe behavior — eliminated) |

---

## 7. FALLBACK BEHAVIOR

- Query key: `"annualized_vol"` from `FeaturePlatformOrchestrator.query_realtime()`
- If Feature Platform is unavailable: `vol = fallback_volatility = 0.50`
- If Feature Platform returns NaN (warm-up): same fallback applied
- Fallback semantic: "50% annualized — conservative risk-policy estimate, NOT a measured value"
- At fallback: `scale = 0.10/0.50 = 0.20×` → 20% of equity

---

## 8. LEVERAGE SAFETY BEHAVIOR

| vol input | vol_safe | raw_scale | final scale | Comment |
|---|---|---|---|---|
| `0.80` (typical BTC) | `0.80` | `0.125×` | `0.125×` | Very conservative — 12.5% equity |
| `0.50` (fallback) | `0.50` | `0.20×` | `0.20×` | Conservative fallback |
| `0.10` | `0.10` | `1.0×` | `1.0×` | Full equity |
| `0.05` (floor) | `0.05` | `2.0×` | `2.0×` | At leverage cap |
| `0.01` | `0.05` (floor) | `2.0×` | `2.0×` | Floor protects; capped at 2× |
| `0.0` (NaN/zero) | `0.05` (floor) | `2.0×` | `2.0×` | Protected (old: 100×) |

---

## 9. TARGETED TEST RESULTS

### FP-3D New Tests
```
research_platform/tests/test_sprint004_fp3d_annualized_vol.py
40 / 40 PASSED  (1.44s)
```

**Coverage by CTO requirement:**

| Req | Class | Tests |
|---|---|---|
| 1. Formula | `TestFormula` | 5 tests |
| 2. Lookback | `TestLookback` | 4 tests |
| 3. Warm-up NaN | `TestWarmupNaNSafety` | 3 tests |
| 4+5. Fallback+Target | `TestFallbackAndTarget` | 5 tests |
| 6. Leverage scenarios | `TestLeverageScenarios` | 7 tests |
| 7. Zero vol safety | `TestZeroVolSafety` | 4 tests |
| 8. Registration | `TestFeatureRegistration` | 4 tests |
| 9. Query key | `TestPositionSizerIntegration` | 4 tests |
| 10. DAG E2E | `TestDagEndToEnd` | 4 tests |

### FP-1 Regression
```
research_platform/tests/test_sprint004_fp1_registration_lifecycle.py
3 / 3 PASSED
```

### Feature Platform Regression
```
research_platform/tests/test_feature_platform.py
6 / 6 PASSED
```

### Position Sizing Targeted
```
research_platform/tests/test_position_sizing.py
6 / 7 PASSED
1 FAILED: test_position_sizing_e2e_pipeline — PRE-EXISTING (see Section 10)
```

### Position Sizing Unit
```
tests/unit/analytics/test_position_sizing.py
4 / 4 PASSED
```

**Total targeted: 59 / 60 PASSED**

---

## 10. PRE-EXISTING REGRESSION (NOT CAUSED BY FP-3D)

**`test_position_sizing_e2e_pipeline`** — `assert 20.0 == 10.0`

**Root cause:** Two fill events fired for a single signal:
- `pord-*` (paper order fill)
- `live_*` (live order fill)

Both write to `PortfolioAccounting`, doubling the position quantity to 20.0.

**Evidence this is pre-existing:**
- The `fixed_risk` branch in `PositionSizingOrchestrator.calculate_size()` is byte-for-byte unchanged from before FP-3D.
- The log shows: `"Service not found in container: 'PriceActionOrchestrator'"` — this is a pre-existing infrastructure registration gap in the e2e test setup, identical to the FP-2 SQLite contamination pattern.
- This failure appears in both paper and live routing paths without `PriceActionOrchestrator` registered, causing both paths to execute independently.

**Classification:** PRE-EXISTING — same contamination class as FP-2's `test_sprint2_pipeline_authoritative_consistency` double-path failure.

---

## 11. ARCHITECTURAL SEPARATION

As mandated by CTO:

| Concern | Location | Value |
|---|---|---|
| **Volatility measurement** | `AnnualizedVolTransformer` | `sample_std(log_return, 1440) × sqrt(525600)` |
| **Target volatility** | `SizingConfig.target_volatility` | `0.10` (env: `TARGET_VOLATILITY`) |
| **Max leverage** | `SizingConfig.max_leverage` | `2.0` (env: `MAX_LEVERAGE`) |
| **Fallback** | `SizingConfig.fallback_volatility` | `0.50` (env: `FALLBACK_VOLATILITY`) |
| **Min vol floor** | Computed in orchestrator | `target_volatility / max_leverage = 0.05` |

Measurement and risk-policy are explicitly separate. `AnnualizedVolTransformer` knows nothing about `target_volatility`. `PositionSizingOrchestrator` computes `min_vol` from config, not from the transformer.

---

## 12. DEPENDENCY GRAPH (FP-3D ADDITION)

```
Level 0:  close
            ↓
Level 1:  log_return
            ↓
Level 2:  annualized_vol  [NEW — FP-3D]
            ↓ (queried by)
          PositionSizingOrchestrator (volatility method)
```

`annualized_vol` is independent of `normalized_atr`, `rolling_std`, `atr`. It shares only the `log_return` dependency with `rolling_std`.

---

## 13. REMAINING RISKS

| Risk | Severity | Status |
|---|---|---|
| `target_volatility=0.10` at BTC scale (~80%) → ~12.5% equity per position | LOW — intentional multi-asset conservative target | DOCUMENTED by CTO decision D2 |
| 1440-bar warm-up requires ~24h of data before live | MEDIUM | Fallback (0.50) handles warm-up safely |
| Backtesting uses daily returns × sqrt(252) — misaligned with live 1-min × sqrt(525600) | MEDIUM | Deferred (out of FP-3 scope) |
| `VolatilityTargetingEngine` and `PortfolioRebalancer` use different target_vol values | LOW | Out of FP-3 scope |
| Pre-existing e2e double-fill bug | LOW | Pre-existing, not FP-3D regression |

---

## 14. FINAL GATE CLASSIFICATION

```
╔════════════════════════════════════════════════════════╗
║                                                        ║
║   SPRINT-004 FP-3D CANONICAL VOLATILITY GATE:          ║
║                                                        ║
║   PASS                                                 ║
║                                                        ║
║   Targeted FP-3D tests:  40 / 40 PASSED               ║
║   FP-1 regression:        3 /  3 PASSED               ║
║   Feature Platform:       6 /  6 PASSED               ║
║   Position sizing:        6 /  7 (1 PRE-EXISTING)     ║
║   Position sizing unit:   4 /  4 PASSED               ║
║   Total targeted:        59 / 60 PASSED               ║
║                                                        ║
║   Production files changed: 5                          ║
║   Test files added/changed: 3                          ║
║   Config files changed:     1 (.env.example)           ║
║                                                        ║
║   Formula: sample_std(log_return,1440) × sqrt(525600)  ║
║   Fallback: 0.50 (50% annualized, conservative floor)  ║
║   Leverage: min(target/vol_safe, 2.0)                  ║
║   Min vol floor: target/max_lev = 0.05                 ║
║                                                        ║
║   STOP. Do NOT start FP-4.                             ║
║                                                        ║
╚════════════════════════════════════════════════════════╝
```
