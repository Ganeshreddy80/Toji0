# SPRINT-004 FP-7B — QUERY API STANDARDIZATION IMPLEMENTATION GATE

**Author:** TOJI Senior Staff Engineer / Principal Architect  
**Date:** 2026-08-17  
**Governance:** Master Architecture Governance — Sprint 004 / FP-7B  
**Stage:** IMPLEMENTATION COMPLETE — REGRESSION VERIFIED  
**Predecessors:** FP-1 through FP-7A — ALL CERTIFIED PASS (FROZEN)

---

## 1. DISCOVERY EVIDENCE

### 1.1 Discovery Scope

Searched entire repository for:
- `query_history(` — all `.py` and `.md` files
- `query_historical(` — all `.py` and `.md` files

### 1.2 Method Inventory

| Location | Method Name | Type | Evidence |
|---|---|---|:---:|
| `research_platform/feature_platform/interfaces.py:50` | `query_historical` | `@abc.abstractmethod` on `IFeatureStore` | **PROVEN** |
| `research_platform/feature_platform/feature_store.py:55` | `query_historical` | Concrete implementation | **PROVEN** |
| `research_platform/feature_platform/orchestrator.py:349` | `query_history` | Thin delegation wrapper (`return self._store.query_historical(...)`) | **PROVEN** |
| `research_platform/feature_platform/orchestrator.py:357` | calls `self._store.query_historical` | Internal call from `query_history` | **PROVEN** |

### 1.3 Production Caller Count

| Method | Production Callers (non-test) | Evidence |
|---|:---:|:---:|
| `FeaturePlatformOrchestrator.query_history()` | **0** (zero callers) | **PROVEN** |
| `FeatureStore.query_historical()` | 1 — called by `orchestrator.query_history()` only | **PROVEN** |
| `IFeatureStore.query_historical()` | Interface only, not called directly | **PROVEN** |

### 1.4 Test Caller Count

| Method | Test Callers | File | Evidence |
|---|:---:|---|:---:|
| `FeatureStore.query_historical()` | 1 | `test_sprint004_fp7a_correctness.py:98` | **PROVEN** |
| `FeaturePlatformOrchestrator.query_history()` | **0** | — | **PROVEN** |
| `FeaturePlatformOrchestrator.query_historical()` | 0 (new method — FP-7B tests first) | — | **PROVEN** |

### 1.5 Documentation References

| Document | Reference | Evidence |
|---|---|:---:|
| `SPRINT-004-FP0-CONTRACT-GATE.md:315` | `query_historical()` named as FeatureStore method | **PROVEN** |
| `SPRINT-004-FEATURE-PIPELINE-DISCOVERY-GATE.md:119` | `store.query_historical` named | **PROVEN** |
| `SPRINT-004-FP6-DISCOVERY-GATE.md:432` | `query_historical()` 0 production callers noted | **PROVEN** |
| `repository_inventory.md:3572,4031,5450` | `query_historical` listed under FeatureStore functions | **PROVEN** |
| `SPRINT-004-FP7-DISCOVERY-GATE.md:34,181,259,283` | Inconsistency named as R-7 | **PROVEN** |

---

## 2. CANONICAL NAMING DECISION

### Decision: `query_historical` is canonical

**Rationale (in priority order):**

1. **Interface contract is the architectural source of truth.** `IFeatureStore` declares `query_historical` as `@abc.abstractmethod`. The interface name dominates.
2. **Concrete implementation matches interface.** `FeatureStore.query_historical` — the implementation contract aligns with the interface.
3. **Naming symmetry with the store's online counterpart.** The store pair is `query_historical` / `query_latest`. The public orchestrator pair should be `query_historical` / `query_realtime`. This is symmetric; `query_history` / `query_realtime` is not.
4. **All architecture documentation uses `query_historical`.** FP-0, FP-6 discovery, feature pipeline discovery, and repository inventory all name the store method `query_historical`.
5. **`query_history` has zero external callers.** Renaming it to `query_historical` on the orchestrator breaks nothing.

**Rejected alternative: `query_history` as canonical.** Would require renaming the interface and store method (`IFeatureStore`, `FeatureStore`) and contradicts all existing documentation. Much higher risk, zero benefit.

---

## 3. COMPATIBILITY STRATEGY

### Architecture

```
PUBLIC API (Orchestrator layer)
──────────────────────────────
query_historical(names, symbols, start, end)   ← CANONICAL (new)
    └→ self._store.query_historical(...)       ← single implementation call

query_history(names, symbols, start, end)      ← DEPRECATED COMPAT ALIAS
    └→ self.query_historical(...)              ← delegates, no logic duplication
```

**Key properties:**
- **Zero implementation duplication.** `query_history` calls `query_historical`; `query_historical` calls `self._store`. The implementation exists exactly once.
- **Backward compatible.** Any future caller of `query_history` continues to work identically.
- **Deprecation signalled.** The `query_history` docstring carries a `.. deprecated::` marker.
- **No `IFeatureStore` or `FeatureStore` changes.** The interface and concrete store are not touched — only the orchestrator public API is updated.

---

## 4. EXACT PRODUCTION FILES MODIFIED

| File | Change Summary | Lines Changed |
|---|---|:---:|
| [`research_platform/feature_platform/orchestrator.py`](file:///Users/a.ganeshkumarreddy12/Downloads/toji-main%203/research_platform/feature_platform/orchestrator.py) | Added `query_historical()` as canonical method. Converted existing `query_history()` to deprecated compatibility alias that delegates to `query_historical()`. | +16 added, −1 changed |

**Files NOT modified (confirmed unchanged):**

| File | Reason |
|---|---|
| `research_platform/feature_platform/interfaces.py` | Already has `query_historical` as abstract — correct. No change needed. |
| `research_platform/feature_platform/feature_store.py` | Already has `query_historical` as concrete implementation — correct. No change needed. |
| `scripts/run_paper_trading.py` | No call to either method. |
| `research_platform/live_trading/plugin.py` | No call to either method. |
| All other production files | No call to either method. |

---

## 5. EXACT TEST FILES MODIFIED

| File | Tests | Purpose |
|---|---|---|
| [`research_platform/tests/test_sprint004_fp7b_query_api.py`](file:///Users/a.ganeshkumarreddy12/Downloads/toji-main%203/research_platform/tests/test_sprint004_fp7b_query_api.py) **(NEW)** | 19 tests | See test classes below |

### FP-7B Test Class Summary

| Class | Tests | Coverage |
|---|:---:|---|
| `TestOrchQueryHistoricalCanonical` | 3 | Canonical method exists, returns DataFrame, returns data when stored |
| `TestOrchQueryHistoryCompatAlias` | 3 | Alias exists, returns DataFrame, source delegates to canonical |
| `TestBothMethodsProduceIdenticalOutput` | 2 | Identical output on empty store, identical output with stored data |
| `TestNoDuplicatedImplementation` | 3 | Canonical calls store, alias does not call store, methods are distinct objects |
| `TestIFeatureStoreInterface` | 2 | Interface has `query_historical` as abstract; does NOT have `query_history` |
| `TestFeatureStoreConcreteClass` | 3 | Concrete has `query_historical`; does NOT have `query_history`; PIT behaviour unchanged |
| `TestQueryRealtimeUnchanged` | 3 | `query_realtime` exists, returns DataFrame, returns data when stored |

---

## 6. EXACT TEST COMMANDS & RESULTS

### FP-7B Focused Tests
```bash
pytest research_platform/tests/test_sprint004_fp7b_query_api.py -v --tb=short
```
**Result: 19/19 PASSED (100%)**

### FP-7B + FP-7A + FP-5 + FP-6 + Predecessor Suite
```bash
pytest \
  research_platform/tests/test_sprint004_fp7b_query_api.py \
  research_platform/tests/test_sprint004_fp7a_correctness.py \
  research_platform/tests/test_sprint004_fp5_determinism.py \
  research_platform/tests/test_sprint004_fp6_eventbus_wiring.py \
  research_platform/tests/test_sprint004_fp2_public_api_boundary.py \
  research_platform/tests/test_sprint004_fp1_registration_lifecycle.py \
  research_platform/tests/test_sprint004_fp3d_annualized_vol.py \
  research_platform/tests/test_feature_platform.py \
  research_platform/tests/test_position_sizing.py \
  research_platform/tests/test_exit_engine.py \
  -v --tb=short
```
**Result: 138 PASSED, 1 FAILED (`test_position_sizing_e2e_pipeline` — pre-existing baseline failure confirmed in FP-7A regression). Zero regressions introduced by FP-7B.**

---

## 7. FROZEN CONTRACTS VERIFIED

| # | Contract | Preserved | Evidence |
|---|---|:---:|---|
| 1 | ADR-001 canonical ATR ownership (`PriceActionOrchestrator.get_atr()`) | ✅ | Not modified |
| 2 | `query_realtime()` public downstream API | ✅ | Not modified. Verified by 3 dedicated tests |
| 3 | `annualized_vol` formula: `sample_std(log_return, 1440) * sqrt(525600)` | ✅ | Not modified |
| 4 | `SizingConfig` defaults: `target_volatility=0.10`, `max_leverage=2.0`, `fallback_volatility=0.50` | ✅ | Not modified |
| 5 | ND-1b: `effective_time = as_of` | ✅ | Not modified. FP-5 determinism 5/5 PASS |
| 6 | FP-6 EventBus Option A observability subscribers | ✅ | Not modified. FP-6 suite 20/20 PASS |
| 7 | Feature DAG mathematical formulas | ✅ | Not modified |
| 8 | FeatureStore key schema `(name, version, symbol)` | ✅ | Not modified |
| 9 | `IFeatureStore.query_historical()` abstract interface | ✅ | Not modified — this is the canonical contract |
| 10 | `FeatureStore.query_historical()` PIT merge join implementation | ✅ | Not modified. Verified by `test_feature_store_query_historical_pit_behaviour_unchanged` |

---

## 8. KNOWN RISKS

| Risk | Severity | Description | Evidence |
|---|:---:|---|:---:|
| **`query_history` compat alias deprecation lifecycle** | LOW | `query_history` is retained as a deprecated alias. It must be tracked for removal in FP-7D or a future sprint. Zero callers exist now. | **PROVEN** |
| **`FeatureStore.query_historical` symbol column requirement** | LOW | `query_historical` requires a `symbol` column in stored DataFrames. `compute_and_store` does not always add this column, making the orchestrator's `query_historical` return an empty DataFrame for features stored via the pipeline. This is a **pre-existing behaviour** documented in FP-7 Discovery Gate and is NOT in FP-7B scope. | **PROVEN** — pre-existing |

---

## 9. REMAINING FP-7 SCOPE

| Sub-Stage | Description | Status |
|---|---|:---:|
| **FP-7A** | R-1 Semantic Version Sort + R-2 Runtime `annualized_vol` | **CERTIFIED PASS** |
| **FP-7B** | Query API naming standardization (`query_history` → `query_historical`) | **COMPLETE** |
| **FP-7C** | Add staleness check helper to `query_realtime(max_age_seconds=None)` | NOT STARTED |
| **FP-7D** | Centralized runtime feature set resolver; remove `query_history` alias | NOT STARTED |

---

## 10. DISCOVERY CONCLUSION

```
╔════════════════════════════════════════════════════════════════════════════╗
║                                                                            ║
║   SPRINT-004 FP-7B: IMPLEMENTATION COMPLETE                                ║
║                                                                            ║
║   Canonical API:      query_historical() — added to orchestrator          ║
║   Compat Alias:       query_history()    — retained, delegates            ║
║   IFeatureStore:      UNCHANGED (already query_historical)                ║
║   FeatureStore:       UNCHANGED (already query_historical)                ║
║                                                                            ║
║   FP-7B Focused Suite:    19/19 PASSED                                    ║
║   Full Predecessor Suite: 138/139 PASSED (1 pre-existing baseline)        ║
║   Frozen Contracts:       ALL 10 VERIFIED                                 ║
║   Production Files Changed: 1 (orchestrator.py only)                     ║
║   Test Files Created:     1 (19 tests)                                    ║
║                                                                            ║
╚════════════════════════════════════════════════════════════════════════════╝
```

---

**STOP — FP-7B Complete. Awaiting CTO decision on FP-7C/FP-7D scope.**
