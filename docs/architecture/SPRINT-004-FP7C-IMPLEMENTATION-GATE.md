# SPRINT-004 FP-7C — REALTIME FEATURE STALENESS HARDENING IMPLEMENTATION GATE

**Author:** TOJI Senior Staff Engineer / Principal Architect  
**Date:** 2026-08-18  
**Governance:** Master Architecture Governance — Sprint 004 / FP-7C  
**Stage:** IMPLEMENTATION COMPLETE — REGRESSION VERIFIED  
**Predecessors:** FP-1 through FP-7B — ALL CERTIFIED PASS (FROZEN)

---

## 1. DISCOVERY EVIDENCE

### 1.1 Scope

Searched entire repository for: `query_realtime(`, `query_latest(`, `"as_of"`, `"_online_db"`.

### 1.2 `as_of` Freshness Timestamp Origin

| Finding | Evidence |
|---|:---:|
| `compute_and_store()` sets `as_of = as_of_time or datetime.now(timezone.utc)` | **PROVEN** |
| `as_of` is **always timezone-aware UTC** in the canonical compute path | **PROVEN** |
| `_online_db[key] = df.sort_values("as_of").tail(1)` — stores the 1-row latest DataFrame | **PROVEN** |
| `query_latest()` outputs `{name}_as_of` per feature in each symbol row | **PROVEN** |
| `validators.py` strips timezone with `tz_localize(None)` for PIT check (internal only) | **PROVEN** |

### 1.3 `_online_db` Storage Behaviour

| Finding | Evidence |
|---|:---:|
| Schema: `Dict[Tuple[name, version, symbol], pd.DataFrame]` — 1-row per key | **PROVEN** |
| Updated on every `save_features()` call (new compute overwrites old) | **PROVEN** |
| After market disconnect, old value remains (never evicted) — root of FP7-R-3 | **PROVEN** |

### 1.4 Timezone Handling Discovery

| Finding | Evidence |
|---|:---:|
| Canonical `as_of` from `compute_and_store` is always `timezone.utc`-aware | **PROVEN** |
| Direct `save_features()` calls in tests may use naive datetime (no tzinfo) | **PROVEN** |
| `pd.Timestamp` of a TZ-aware value preserves tz; naive → `tz_localize("UTC")` is safe normalisation | **PROVEN** |
| Pandas converts `float("nan")` assignment into datetime column as `NaT` (not `float NaN`) | **PROVEN** — discovered during test iteration |

### 1.5 `as_of` Missing / Malformed Semantics

| Case | Handling | Evidence |
|---|---|:---:|
| `None` | `pd.isna(None)` → True → treated as stale | **PROVEN** |
| `float NaN` | `pd.isna(NaN)` → True → treated as stale | **PROVEN** |
| `pd.NaT` | `pd.isna(NaT)` → True → treated as stale | **PROVEN** |
| Raises on `pd.Timestamp()` | `except Exception → stale` | **PROVEN** |

### 1.6 Production Callers of `query_realtime()`

| Caller | File | Call Style |
|---|---|---|
| `PositionSizingOrchestrator` | `position_sizing/orchestrator.py:130,173` | `query_realtime(["annualized_vol"], [symbol])` — no TTL |
| `ExitEngineOrchestrator` | `exit_engine/orchestrator.py:146` | `query_realtime(["normalized_atr", "risk_score"], [symbol])` — no TTL |
| `AISignalGenerator` | `ai_signal/signal_generator.py:76` | `query_realtime([...10 features...], [symbol])` — no TTL |
| `StrategyLoop` | `runtime/strategy_loop.py:34` | `query_realtime(feature_names, symbols)` — no TTL |

**PROVEN: All 4 production callers use the no-TTL form. Zero callers use `max_age_seconds`.**  
**All 4 callers will continue to receive EXACT current behaviour — unaffected by FP-7C.**

### 1.7 Whether Any Caller Depends on Stale Values

| Finding | Evidence |
|---|:---:|
| `PositionSizingOrchestrator` has explicit `isnan` guard — falls back to `fallback_volatility=0.50` if value absent | **PROVEN** |
| `ExitEngineOrchestrator` wraps query in `try/except`; guards `df_feat is not None and not df_feat.empty` | **PROVEN** |
| `AISignalGenerator` guards `if not latest_df.empty` | **PROVEN** |
| `StrategyLoop` guards `if df_realtime is not None and not df_realtime.empty` | **PROVEN** |
| No caller depends on stale values being present — all have safe fallbacks | **PROVEN** |

---

## 2. FRESHNESS OWNERSHIP DECISION

**Decision: Freshness filter lives in `FeaturePlatformOrchestrator`. `IFeatureStore` and `FeatureStore` are NOT modified.**

**Rationale:**

1. **`IFeatureStore.query_latest()` is an abstract interface.** Adding `max_age_seconds` requires changing the interface and every concrete implementation — far wider blast radius than needed.
2. **The orchestrator is already the public API boundary.** All callers interact with `query_realtime()` on the orchestrator; none call `query_latest()` directly.
3. **`query_latest()` output already carries `{name}_as_of` per feature.** The orchestrator can filter entirely from this output — no store-layer change needed.
4. **Staleness filtering is a query-time policy.** It belongs in the API boundary layer (orchestrator), not the storage concern (store).
5. **Smallest safe change.** Only `orchestrator.py` is modified.

---

## 3. API SIGNATURE

```python
def query_realtime(
    self,
    names: List[str],
    symbols: List[str],
    max_age_seconds: Optional[float] = None,
) -> pd.DataFrame:
```

**Existing callers:** `query_realtime(names, symbols)` — positionally compatible. **Zero signature breakage.**

---

## 4. EXACT SEMANTICS

| Condition | Behaviour |
|---|---|
| `max_age_seconds=None` (default) | **Exact pre-FP-7C behaviour.** No filtering applied. All stored values returned regardless of age. |
| `max_age_seconds > 0` | A single `now_utc = datetime.now(timezone.utc)` is captured once for the call. For each requested feature: if `(now_utc - as_of) > timedelta(seconds=max_age_seconds)` → feature value is set to `NaN` and `{name}_as_of` is set to `NaN`. Symbol row is preserved. |
| `df.empty` | Returns immediately (no filtering attempted). |
| Feature not present in result | No action taken — absent features remain absent. |

**Staleness granularity: per-feature, not per-symbol-row.** Individual features within the same symbol can have different staleness classifications. Symbol rows are always preserved.

---

## 5. TIMEZONE SEMANTICS

| Case | Handling | Rationale |
|---|---|---|
| TZ-aware UTC `as_of` | Compared directly against `now_utc` | Repository canonical convention (`compute_and_store` always produces TZ-aware UTC) |
| TZ-naive `as_of` | `pd.Timestamp(as_of_val).tz_localize("UTC")` | Explicit normalisation — no silent comparison of naive and aware |
| `pd.NaT` | `pd.isna(NaT)` → treated as stale | Pandas datetime column behaviour when assigned `float NaN` |
| `float NaN` | `pd.isna(NaN)` → treated as stale | Float-typed column edge case |
| `None` | `pd.isna(None)` → treated as stale | Explicit null handling |
| Malformed (raises on `pd.Timestamp()`) | `except Exception → treated as stale` | Defensive guard |

**Single reference time:** `datetime.now(timezone.utc)` is called **once** at the start of the staleness loop, before iterating over features. All feature staleness comparisons use the same `now_utc`.

---

## 6. STALE DATA SEMANTICS

**When a feature is stale:**
- `df.loc[stale_mask, name]` → `NaN`
- `df.loc[stale_mask, f"{name}_as_of"]` → `NaN` (converted to `NaT` by Pandas for datetime columns)
- **Symbol row preserved.** Downstream callers can still process the symbol row and detect missing values via existing `isnan` / `.empty` guards.

**Why per-feature granularity, not per-row:**
- `query_latest()` output schema is one row per symbol with multiple feature columns.
- Downstream consumers already guard individual feature values (e.g. `PositionSizingOrchestrator` checks `isnan(raw_val)` per feature).
- Dropping entire rows when only one feature is stale would incorrectly suppress still-fresh features for the same symbol.

---

## 7. EXACT PRODUCTION FILES MODIFIED

| File | Changes |
|---|---|
| [`research_platform/feature_platform/orchestrator.py`](file:///Users/a.ganeshkumarreddy12/Downloads/toji-main%203/research_platform/feature_platform/orchestrator.py) | Added `import math as _math`; added `timedelta` to datetime imports. Added `max_age_seconds: Optional[float] = None` parameter to `query_realtime()`. Added staleness filter logic: single `now_utc`, per-feature `_is_stale()`, conditional NaN assignment. |

**Files NOT modified (confirmed unchanged):**

| File | Reason |
|---|---|
| `research_platform/feature_platform/interfaces.py` | `IFeatureStore.query_latest()` — not changed. No TTL on store interface. |
| `research_platform/feature_platform/feature_store.py` | `FeatureStore.query_latest()` — not changed. No TTL on store. |
| `research_platform/position_sizing/orchestrator.py` | Existing no-TTL caller — unchanged |
| `research_platform/exit_engine/orchestrator.py` | Existing no-TTL caller — unchanged |
| `research_platform/ai_signal/signal_generator.py` | Existing no-TTL caller — unchanged |
| `research_platform/runtime/strategy_loop.py` | Existing no-TTL caller — unchanged |
| All other production files | Not modified |

---

## 8. EXACT TEST FILES CHANGED

| File | Tests | Purpose |
|---|---|---|
| [`research_platform/tests/test_sprint004_fp7c_staleness.py`](file:///Users/a.ganeshkumarreddy12/Downloads/toji-main%203/research_platform/tests/test_sprint004_fp7c_staleness.py) **(NEW)** | 30 tests | See class breakdown below |

### FP-7C Test Class Summary

| Class | Tests | Coverage |
|---|:---:|---|
| `TestNoneBehaviourPreserved` | 4 | Default None: positional call, kwarg=None identical, stale data returned, empty store |
| `TestFreshFeatureReturned` | 2 | Fresh value preserved, fresh as_of column preserved |
| `TestBoundaryBehaviour` | 2 | Exactly at boundary = NOT stale (strict `>`); 1s over = stale |
| `TestStaleFeatureExcluded` | 3 | Stale value → NaN; stale as_of → NaN; symbol row preserved |
| `TestMultipleSymbolsIndependent` | 3 | Fresh/stale per symbol independently; both fresh; both stale |
| `TestMultipleFeaturesHandled` | 2 | One fresh + one stale per request; both fresh |
| `TestMissingFeatureHandled` | 2 | Missing feature absent without TTL; absent without error with TTL |
| `TestMalformedAsOfHandling` | 1 | NaN/NaT as_of treated as stale |
| `TestTimezoneAwareHandling` | 3 | TZ-aware UTC fresh; naive normalised to UTC (fresh); naive old (stale) |
| `TestOutputContractUnchanged` | 3 | Schema intact without TTL; schema intact with TTL; one row per symbol |
| `TestFeatureStoreQueryLatestUnchanged` | 3 | IFeatureStore no max_age; FeatureStore no max_age; store returns stale without filter |
| `TestSingleReferenceTime` | 2 | Consistent classification within one call; source code single now() |

---

## 9. EXACT TEST COMMANDS AND RESULTS

### FP-7C Focused Tests
```bash
pytest research_platform/tests/test_sprint004_fp7c_staleness.py -v --tb=short
```
**Result: 30/30 PASSED (100%)**

### FP-7C + FP-7B + FP-7A + FP-6 + FP-5 + FP-3D + FP-2 + FP-1 + Feature Platform + Position Sizing + Exit Engine
```bash
pytest \
  research_platform/tests/test_sprint004_fp7c_staleness.py \
  research_platform/tests/test_sprint004_fp7b_query_api.py \
  research_platform/tests/test_sprint004_fp7a_correctness.py \
  research_platform/tests/test_sprint004_fp6_eventbus_wiring.py \
  research_platform/tests/test_sprint004_fp5_determinism.py \
  research_platform/tests/test_sprint004_fp3d_annualized_vol.py \
  research_platform/tests/test_sprint004_fp2_public_api_boundary.py \
  research_platform/tests/test_sprint004_fp1_registration_lifecycle.py \
  research_platform/tests/test_feature_platform.py \
  research_platform/tests/test_position_sizing.py \
  research_platform/tests/test_exit_engine.py \
  -v --tb=short
```
**Result: 168 PASSED, 1 FAILED (`test_position_sizing_e2e_pipeline` — pre-existing baseline failure, identical to FP-7A and FP-7B regressions). Zero regressions introduced by FP-7C.**

---

## 10. FROZEN CONTRACTS VERIFIED

| # | Contract | Preserved | Evidence |
|---|---|:---:|---|
| 1 | ADR-001 canonical ATR ownership (`PriceActionOrchestrator.get_atr()`) | ✅ | Not modified |
| 2 | `query_realtime(names, symbols)` existing caller behaviour (no TTL) | ✅ | All 4 production callers pass identical keyword-free call; `max_age_seconds=None` preserves exact pre-FP-7C behaviour. Verified by FP7C-1 tests (4 tests). |
| 3 | `annualized_vol` formula: `sample_std(log_return, 1440) * sqrt(525600)` | ✅ | Not modified |
| 4 | `SizingConfig` defaults | ✅ | Not modified |
| 5 | ND-1b: `effective_time = as_of` | ✅ | Not modified. FP-5 suite passes. |
| 6 | FP-6 EventBus Option A | ✅ | Not modified. FP-6 suite passes. |
| 7 | Feature DAG mathematical formulas | ✅ | Not modified |
| 8 | FeatureStore key schema `(name, version, symbol)` | ✅ | Not modified |
| 9 | `IFeatureStore.query_historical()` abstract interface | ✅ | Not modified |
| 10 | `IFeatureStore.query_latest()` abstract interface signature | ✅ | Not modified. Verified by `test_ifeaturestore_has_no_max_age_seconds`. |
| 11 | `FeatureStore.query_latest()` concrete implementation | ✅ | Not modified. Verified by `test_feature_store_query_latest_returns_stale_data`. |
| 12 | FP-7B canonical `query_historical()` / compat `query_history()` | ✅ | Not modified. FP-7B suite passes. |

---

## 11. KNOWN RISKS

| Risk | Severity | Description | Evidence |
|---|:---:|---|:---:|
| **Closure-in-loop variable capture** | LOW | `_is_stale` closure defined inside a `for name in names` loop. Python closures capture by reference, but `_is_stale` only captures `now_utc`, `max_age_td`, and `as_of_val` (argument) — not `name`. No variable-capture bug. | **PROVEN** — verified by test |
| **`pd.isna()` on non-null timestamps** | LOW | `pd.isna(valid_Timestamp)` returns `False` — safe. Verified by test execution. | **PROVEN** |
| **Callers upgrading to `max_age_seconds`** | INFO | Production callers wanting staleness protection must opt in by adding `max_age_seconds=N`. Currently zero callers use it. This is by design (opt-in). | **PROVEN** — zero callers |
| **`as_of` column dtype shift on NaN assignment** | INFO | When stale features set to `float("nan")`, Pandas converts datetime column values to `NaT`. Downstream callers must guard with `pd.isna()` not `math.isnan()`. Existing callers use `.empty` check — not affected. | **PROVEN** |

---

## 12. REMAINING FP-7 SCOPE

| Sub-Stage | Description | Status |
|---|---|:---:|
| **FP-7A** | Semantic version sort + runtime `annualized_vol` | **CERTIFIED PASS** |
| **FP-7B** | Query API naming standardization | **CERTIFIED PASS** |
| **FP-7C** | `query_realtime(max_age_seconds=None)` staleness hardening | **COMPLETE** |
| **FP-7D** | Runtime feature set centralization; remove `query_history` compat alias | NOT STARTED |

---

## 13. CONCLUSION

```
╔════════════════════════════════════════════════════════════════════════════════╗
║                                                                                ║
║   SPRINT-004 FP-7C: IMPLEMENTATION COMPLETE                                    ║
║                                                                                ║
║   API Change:      query_realtime(..., max_age_seconds=None) — additive only  ║
║   Freshness Owner: FeaturePlatformOrchestrator (orchestrator layer only)       ║
║   IFeatureStore:   UNCHANGED                                                   ║
║   FeatureStore:    UNCHANGED                                                   ║
║   Production callers: ALL 4 continue with exact pre-FP-7C behaviour           ║
║                                                                                ║
║   FP-7C Focused Suite:    30/30 PASSED                                         ║
║   Full Predecessor Suite: 168/169 PASSED (1 pre-existing baseline)            ║
║   Frozen Contracts:       ALL 12 VERIFIED                                      ║
║   Production Files Changed: 1 (orchestrator.py only)                          ║
║   Test Files Created:     1 (30 tests)                                         ║
║                                                                                ║
╚════════════════════════════════════════════════════════════════════════════════╝
```

---

**STOP — FP-7C Complete. Awaiting CTO decision on FP-7D scope.**
