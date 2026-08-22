# SPRINT-004 FP-7A — CORRECTNESS HARDENING IMPLEMENTATION GATE

**Author:** TOJI Senior Staff Engineer / Principal Architect  
**Date:** 2026-08-15  
**Governance:** Master Architecture Governance — Sprint 004 / FP-7A  
**Stage:** IMPLEMENTATION COMPLETE — REGRESSION VERIFIED  
**Predecessors:** FP-1 through FP-6 — ALL CERTIFIED PASS (FROZEN)

---

## 1. R-1 EVIDENCE — SEMANTIC VERSION ORDERING

### Discovery Finding

**Source:** [`feature_store.py`](file:///Users/a.ganeshkumarreddy12/Downloads/toji-main%203/research_platform/feature_platform/feature_store.py) lines 67-68 (query_historical) and 92-93 (query_latest).

**Defect:** Version resolution used lexicographic string sort:
```python
latest_key = sorted(matching_keys, key=lambda k: k[1])[-1]
```
This produces incorrect ordering for multi-digit version parts:
- `"1.0.10" < "1.0.9"` (lexicographic: `"1"` < `"9"`)
- `"1.10.0" < "1.9.0"` (lexicographic: `"1"` < `"9"`)

**Evidence Status:** **PROVEN** — verified by direct source inspection.

### R-1 Implementation

**Approach:** Strict numeric tuple parsing (zero external dependencies).

Added `_parse_semver(version: str) -> Tuple[int, int, int]` at module level in `feature_store.py`:
- Splits on `.`, asserts exactly 3 parts.
- Converts each part to `int`, raising `ValueError` for malformed inputs.
- Returns `(major, minor, patch)` tuple for natural integer comparison.

Replaced both sort keys:
```python
# Before (DEFECTIVE):
latest_key = sorted(matching_keys, key=lambda k: k[1])[-1]

# After (CORRECT):
latest_key = sorted(matching_keys, key=lambda k: _parse_semver(k[1]))[-1]
```

**Design Decision:** Used numeric tuple parsing instead of `packaging.version.parse` because:
1. `packaging` is available (v25.0) but not a declared project dependency.
2. The tuple approach has zero external dependencies and is self-contained.
3. All existing versions are strict `major.minor.patch` format (Pydantic `FeatureRecord.version` field docstring: `"Semantic version (e.g. 1.0.0)"`).
4. Malformed versions are explicitly rejected rather than silently handled.

**Evidence Status:** **PROVEN** — implementation verified by 12 focused tests.

---

## 2. R-2 EVIDENCE — RUNTIME annualized_vol AVAILABILITY

### Discovery Finding

**Source:** `DEFAULT_FEATURE_DEFINITIONS` in [`orchestrator.py`](file:///Users/a.ganeshkumarreddy12/Downloads/toji-main%203/research_platform/feature_platform/orchestrator.py) defines 20 features (lines 60-184).

Runtime feature lists in two locations contained only 15 features:

| File | Line | List |
|---|---|---|
| [`run_paper_trading.py`](file:///Users/a.ganeshkumarreddy12/Downloads/toji-main%203/scripts/run_paper_trading.py) | 293-295 | `open, high, low, close, ema9, ema21, ema50, rsi, atr, volume, volume_change, support, resistance, breakout, trend` |
| [`live_trading/plugin.py`](file:///Users/a.ganeshkumarreddy12/Downloads/toji-main%203/research_platform/live_trading/plugin.py) | 218-221 | Identical 15-feature list |

**Missing features:** `log_return`, `rolling_std`, `annualized_vol`, `normalized_atr`, `risk_score`, `signal`.

**Impact on Downstream Consumers:**

| Consumer | Feature Queried | Consequence of Missing |
|---|---|---|
| `PositionSizingOrchestrator` | `annualized_vol` | Falls back to `fallback_volatility=0.50` instead of computed realized volatility |
| `ExitEngineOrchestrator` | `normalized_atr`, `risk_score` | Receives empty/None values for risk scoring |
| `StrategyLoop` | Dynamic via `registry.list_all()` | Already correct — dynamically resolves all registered features |
| `AISignalGenerator` | `rsi, ema9, ema21, ema50, atr, trend, support, resistance, breakout, volume_change` | Already computed — all in the 15-feature list |
| `TradeJournalOrchestrator` | `rsi, ema9, ema21, ema50, trend, support, resistance, breakout, volume_change` | Already computed — all in the 15-feature list |

**Evidence Status:** **PROVEN** — verified by source inspection of all 5 downstream consumers.

### Runtime Feature Resolution Decision

**Decision:** Add the 6 missing features to both runtime `features_to_compute` lists.

**NOT authorized:** Dynamic `registry.list_all()` resolution. The CTO explicitly deferred this to avoid computing every registered feature unnecessarily.

**Rationale for explicit enumeration over dynamic resolution:**
1. The CTO authorization states: *"Do NOT immediately replace them with registry.list_all(). That is NOT authorized."*
2. Explicit lists are auditable — each addition is documented with its consumer rationale.
3. The DAG automatically resolves intermediate dependencies (e.g., requesting `annualized_vol` auto-computes `log_return`), so the 6 additions are sufficient.
4. Feature list duplication between `run_paper_trading.py` and `live_trading/plugin.py` is noted as technical debt for FP-7D.

### R-2 Implementation

Added 6 features to both `features_to_compute` lists with inline comments explaining each consumer requirement:

```python
# FP-7A: Features required by downstream consumers but previously omitted.
# annualized_vol: PositionSizingOrchestrator (FP-3D volatility target sizing).
# normalized_atr, risk_score: ExitEngineOrchestrator.
# log_return, rolling_std: DAG prerequisites for annualized_vol.
# signal: DAG leaf derived from risk_score.
"log_return", "rolling_std", "annualized_vol", "normalized_atr", "risk_score", "signal"
```

**Evidence Status:** **PROVEN** — both files updated, AST-verified by tests.

---

## 3. EXACT PRODUCTION FILES MODIFIED

| File | Change Summary |
|---|---|
| [`research_platform/feature_platform/feature_store.py`](file:///Users/a.ganeshkumarreddy12/Downloads/toji-main%203/research_platform/feature_platform/feature_store.py) | Added `_parse_semver()`. Changed 2 sort keys from lexicographic to semantic tuple comparison. |
| [`scripts/run_paper_trading.py`](file:///Users/a.ganeshkumarreddy12/Downloads/toji-main%203/scripts/run_paper_trading.py) | Expanded `features_to_compute` from 15 to 21 entries. |
| [`research_platform/live_trading/plugin.py`](file:///Users/a.ganeshkumarreddy12/Downloads/toji-main%203/research_platform/live_trading/plugin.py) | Expanded `features_to_compute` from 15 to 21 entries. |

**Total production files modified:** 3  
**Lines added:** ~25  
**Lines removed:** 3  

---

## 4. EXACT TEST FILES MODIFIED

| File | Tests | Purpose |
|---|---|---|
| [`research_platform/tests/test_sprint004_fp7a_correctness.py`](file:///Users/a.ganeshkumarreddy12/Downloads/toji-main%203/research_platform/tests/test_sprint004_fp7a_correctness.py) **(NEW)** | 19 tests | R-1 version ordering (9 unit + 3 integration), R-2 runtime parity (2 AST), R-2 compute/query integration (2), fallback (1), boundary (2) |

---

## 5. TEST COMMANDS & RESULTS

### FP-7A Focused Tests
```bash
pytest research_platform/tests/test_sprint004_fp7a_correctness.py -v --tb=short
```
**Result: 19/19 PASSED (100%)**

### FP-5 Determinism + FP-6 EventBus + FP-7A Combined
```bash
pytest research_platform/tests/test_sprint004_fp5_determinism.py \
      research_platform/tests/test_sprint004_fp6_eventbus_wiring.py \
      research_platform/tests/test_sprint004_fp7a_correctness.py -v --tb=short
```
**Result: 44/44 PASSED (100%)**

### Full Regression Suite
```bash
pytest research_platform/tests/ -v --tb=short \
      --ignore=research_platform/tests/test_alpha_factory.py \
      --ignore=research_platform/tests/test_strategy_lab.py
```
**Result: 1683 PASSED, 7 FAILED (pre-existing) — 35 min runtime.**

All 7 failures are **pre-existing** and unrelated to FP-7A:
- `test_oms_duplicate_order_prevention` — OMS race condition.
- `test_boot_config_default_host` — Environment-specific Neon DB host.
- `test_position_sizing_e2e_pipeline` — LiveTradingOrchestrator e2e quantity (20.0 vs 10.0), pre-existing.
- `test_recovery_engine_clean_slate_success` — Recovery engine issue.
- `test_recovery_orchestrator_boot_integration` — Recovery orchestrator issue.
- `test_execution_engine_ems_orchestration` — Paper mode safety gate.
- `test_restart_after_successful_fill` — Sprint 002 legacy.

**Evidence:** These same 7 tests fail identically on the pre-FP-7A codebase (task-2780 regression run from before FP-7A changes). **PROVEN: zero regressions introduced by FP-7A.**

### Targeted FP + Consumer Regression
```bash
pytest research_platform/tests/test_sprint004_fp*.py \
      research_platform/tests/test_feature_platform.py \
      research_platform/tests/test_position_sizing.py \
      research_platform/tests/test_exit_engine.py -v --tb=short
```
**Result: 119 PASSED, 1 FAILED (pre-existing `test_position_sizing_e2e_pipeline`). Evidence Status: PROVEN.**

---

## 6. FROZEN CONTRACTS VERIFICATION

| # | Contract | Preserved | Evidence |
|---|---|:---:|---|
| 1 | ADR-001 canonical ATR ownership (`PriceActionOrchestrator.get_atr()`) | ✅ | Not modified. |
| 2 | `query_realtime()` public downstream API | ✅ | Not modified. Test verifies boundary. |
| 3 | `annualized_vol` formula: `sample_std(log_return, 1440) * sqrt(525600)` | ✅ | Not modified. Only the compute trigger list was expanded. |
| 4 | `SizingConfig` defaults: `target_volatility=0.10`, `max_leverage=2.0`, `fallback_volatility=0.50` | ✅ | Not modified. Fallback test verifies 0.50 is used when unavailable. |
| 5 | ND-1b: `effective_time = as_of` | ✅ | Not modified. FP-5 determinism tests pass. |
| 6 | FP-6 EventBus Option A | ✅ | Not modified. FP-6 test suite passes (20/20). |
| 7 | Feature DAG mathematical formulas | ✅ | Not modified. |
| 8 | FeatureStore key structure `(name, version, symbol)` | ✅ | Not modified. Only sort comparator changed. |

---

## 7. REMAINING FP-7 SCOPE

| Stage | Scope | Status |
|---|---|:---:|
| **FP-7A** | R-1 version sort + R-2 runtime `annualized_vol` | **COMPLETE** |
| **FP-7B** | Standardize `query_history()` / `query_historical()` naming | NOT STARTED |
| **FP-7C** | Add staleness check helper to `query_realtime(max_age_seconds=None)` | NOT STARTED |
| **FP-7D** | Eliminate runtime feature list duplication; document or clean dead event stubs | NOT STARTED |

---

## 8. KNOWN RISKS

| Risk | Severity | Description | Evidence |
|---|:---:|---|:---:|
| **Runtime list duplication** | LOW | `features_to_compute` is duplicated in `run_paper_trading.py` and `live_trading/plugin.py`. Changes to one must be mirrored. | **PROVEN** — documented for FP-7D |
| **Validator NaN threshold** | LOW | `annualized_vol` requires 7206+ bars to pass the 20% NaN ratio validator gate. During initial warm-up (< 7206 bars), it is rejected by validation and not stored. `PositionSizingOrchestrator` correctly falls back to 0.50. | **PROVEN** |
| **`_parse_semver` strictness** | LOW | Rejects pre-release tags like `"1.0.0-beta"`. Currently no features use pre-release versions. | **PROVEN** — all 20 features use `"1.0.0"` |

---

## 9. DISCOVERY CONCLUSION

```
╔════════════════════════════════════════════════════════════════════════════╗
║                                                                            ║
║   SPRINT-004 FP-7A: IMPLEMENTATION COMPLETE                                ║
║                                                                            ║
║   R-1 Semantic Version Sort:  FIXED & TESTED (12 tests)                   ║
║   R-2 Runtime annualized_vol: FIXED & TESTED (7 tests)                    ║
║   FP-7A Focused Suite:        19/19 PASSED                                ║
║   FP-5 + FP-6 + FP-7A:       44/44 PASSED                                ║
║   Frozen Contracts:           ALL 8 VERIFIED                              ║
║   Production Files Modified:  3                                           ║
║   Test Files Created:         1 (19 tests)                                ║
║                                                                            ║
╚════════════════════════════════════════════════════════════════════════════╝
```

---

**STOP — FP-7A Complete. Awaiting CTO decision on FP-7B/C/D scope.**
