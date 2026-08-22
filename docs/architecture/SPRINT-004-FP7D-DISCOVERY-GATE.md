# SPRINT-004 FP-7D — DISCOVERY GATE

**Author:** TOJI Senior Staff Engineer / Principal Architect  
**Date:** 2026-08-18  
**Governance:** Master Architecture Governance — Sprint 004 / FP-7D  
**Stage:** DISCOVERY COMPLETE — CTO DECISION REQUIRED  
**Predecessors:** FP-7A CERTIFIED PASS · FP-7B CERTIFIED PASS · FP-7C CERTIFIED PASS — ALL FROZEN  

---

## 1. DISCOVERY SCOPE

### 1.1 Search Coverage

All files in repository searched for:
- `query_history(` — all `.py`, `.md`
- `query_historical(` — all `.py`
- `query_realtime(` — all `.py`
- `DEFAULT_FEATURE_DEFINITIONS` — all `.py`
- `register_default_features(` — all `.py`
- `features_to_compute` — all `.py`
- `feature_names` — all `.py`
- `list_all()` — registry usage
- Hard-coded feature-name lists — all `.py`
- Runtime consumer integrations — scripts, live_trading, backtesting, e2e

### 1.2 Files Read for Evidence

| File | Purpose |
|---|---|
| `research_platform/feature_platform/orchestrator.py` | `DEFAULT_FEATURE_DEFINITIONS` (L61–185), `register_default_features` (L254–258), `query_history` (L363–374), `query_realtime` (L376+) |
| `research_platform/feature_platform/feature_pipeline.py` | Transformer registry (21 features), `compute()` |
| `research_platform/feature_platform/dependency_graph.py` | `topological_sort`, `get_execution_plan` |
| `scripts/run_paper_trading.py` | `features_to_compute` list (L293–302) |
| `research_platform/live_trading/plugin.py` | `features_to_compute` list (L218–227) |
| `backtesting/engine.py` | `features_to_compute` list (L54–57), dependency dict (L29–45) |
| `research_platform/runtime/strategy_loop.py` | `feature_names` resolution (L28–33), `query_realtime` (L34) |
| `research_platform/ai_signal/signal_generator.py` | 10-feature `query_realtime` call (L76–78) |
| `research_platform/position_sizing/orchestrator.py` | `["annualized_vol"]` query (L130, 173) |
| `research_platform/exit_engine/orchestrator.py` | `["normalized_atr", "risk_score"]` query (L146) |
| `research_platform/trade_journal/orchestrator.py` | 9-feature `query_realtime` call (L202–204) |
| `tests/e2e/test_signal_lifecycle.py` | 14-feature `features_to_compute` (L52–55) |
| `tests/e2e/test_end_to_end_trading_verification.py` | 14-feature `features_to_compute` (L312–315) |

---

## 2. PART A — QUERY_HISTORY CALLER INVENTORY

### 2.1 Complete Caller Table

| Location | File | Type | Calls `query_history` | Classification |
|---|---|---|:---:|:---:|
| `FeaturePlatformOrchestrator.query_history` | `orchestrator.py:363` | **DEFINITION** (compat alias) | — | **PROVEN** |
| `test_sprint004_fp7b_query_api.py` — `TestCompatAlias` | Test file | **TEST** (verifies alias exists and delegates) | ✅ 3 test methods call it | **PROVEN** |
| All scripts | `scripts/*` | Script | ❌ None | **PROVEN** |
| All live trading | `research_platform/live_trading/*` | Production | ❌ None | **PROVEN** |
| All paper trading | `research_platform/paper_trading/*` `paper_trading/*` | Production | ❌ None | **PROVEN** |
| All e2e tests | `tests/e2e/*` | E2E test | ❌ None | **PROVEN** |
| All backtesting | `backtesting/` `backtesting_engine/` | Library | ❌ None | **PROVEN** |
| Documentation | `docs/architecture/*.md` | Docs | Reference only (no code calls) | **PROVEN** |
| All other production | All remaining `.py` | Production | ❌ None | **PROVEN** |

### 2.2 Summary

| Question | Answer | Classification |
|---|---|:---:|
| Zero external production callers of `query_history()`? | **YES — zero external callers** | **PROVEN** |
| Any external/public compatibility surface (API, SDK, integration)? | **None found** — internal only | **PROVEN** |
| Docs/examples/scripts still reference it functionally? | Docs reference by name (history only) — no code call | **PROVEN** |
| Tests reference it? | **YES** — `test_sprint004_fp7b_query_api.py` explicitly tests the compat alias as per FP-7B spec | **PROVEN** |
| Would removing the alias break production? | **NO** — zero callers | **PROVEN** |
| Would removing the alias break tests? | **YES** — FP-7B test class `TestCompatAlias` (3 tests) explicitly verify the alias exists | **PROVEN** |
| Is `query_historical()` universally available? | **YES** — canonical on both orchestrator and store since FP-7B | **PROVEN** |

### 2.3 FP-7B Test Impact Analysis

The FP-7B test suite (`test_sprint004_fp7b_query_api.py`) contains a dedicated class that:
1. Verifies `query_history` exists and is callable on the orchestrator.
2. Verifies it returns a DataFrame.
3. Verifies it delegates to `query_historical` (source inspection).
4. Verifies it does NOT directly call `self._store` (source inspection).

**If `query_history` is removed, 4 tests in `TestCompatAlias` must also be updated or removed.**  
These are FP-7B certification tests that verified the compat alias — they would become obsolete.

### 2.4 Removal Risk

| Risk | Severity | Description | Classification |
|---|:---:|---|:---:|
| Production breakage | **NONE** | Zero external callers | **PROVEN** |
| Test breakage | **CONTROLLED** | 4 FP-7B alias tests; update/remove is intentional | **PROVEN** |
| Documentation update | **MINIMAL** | Gate docs mention alias lifecycle; update docs only | **PROVEN** |
| Future caller via dynamic dispatch | **LOW** | No dynamic string-based resolution of `query_history` found | **INFERRED** |

---

## 3. PART B — RUNTIME FEATURE SET INVENTORY

### 3.1 Sites Where the System Decides "These Features Required at Runtime"

| # | Site | File | Location | Feature Set | Static/Dynamic | Mechanism |
|---|---|---|---|---|:---:|---|
| **S-1** | Paper Trading compute | `scripts/run_paper_trading.py` | L293–302 | 21 features (base 15 + FP-7A 6) | **STATIC** | Hard-coded list per tick |
| **S-2** | Live Trading compute | `research_platform/live_trading/plugin.py` | L218–227 | 21 features (base 15 + FP-7A 6) | **STATIC** | Hard-coded list per tick |
| **S-3** | StrategyLoop query | `research_platform/runtime/strategy_loop.py` | L28–33 | (A) from context, (B) `registry.list_all()`, (C) 14-feature fallback | **DYNAMIC with fallback** | Priority chain |
| **S-4** | AI Signal query | `research_platform/ai_signal/signal_generator.py` | L76–78 | 10 named features | **STATIC** | Hard-coded query list |
| **S-5** | Position Sizing query | `research_platform/position_sizing/orchestrator.py` | L130, 173 | `["annualized_vol"]` | **STATIC** | Single feature |
| **S-6** | Exit Engine query | `research_platform/exit_engine/orchestrator.py` | L146 | `["normalized_atr", "risk_score"]` | **STATIC** | Two features |
| **S-7** | Trade Journal query | `research_platform/trade_journal/orchestrator.py` | L202–204 | 9 named features | **STATIC** | Hard-coded query list |
| **S-8** | Backtesting engine | `backtesting/engine.py` | L54–57 | 14 features (base set, no FP-7A extras) | **STATIC** | Hard-coded; own dep graph |
| **S-9** | E2E test lifecycle | `tests/e2e/test_signal_lifecycle.py` | L52–55 | 14 features (base set only) | **STATIC** | Hard-coded (test only) |
| **S-10** | E2E trading verify | `tests/e2e/test_end_to_end_trading_verification.py` | L312–315 | 14 features (base set only) | **STATIC** | Hard-coded (test only) |

### 3.2 Exact Feature Lists by Site

**S-1 / S-2 — Paper + Live Trading compute (`features_to_compute`):**
```
open, high, low, close, ema9, ema21, ema50,
rsi, atr, volume, volume_change, support, resistance, breakout, trend,
log_return, rolling_std, annualized_vol, normalized_atr, risk_score, signal
```
(21 features — matches `DEFAULT_FEATURE_DEFINITIONS` exactly, by name) **PROVEN**

**S-3 — StrategyLoop `query_realtime` fallback:**
```
open, high, low, close, ema9, ema21, ema50,
rsi, atr, volume, volume_change, support, resistance, breakout, trend
```
(14 features — base set without FP-7A additions)

**S-4 — AI Signal `query_realtime`:**
```
rsi, ema9, ema21, ema50, atr, trend, support, resistance, breakout, volume_change
```
(10 features — subset; intentionally excludes raw OHLCV, vol chain, risk chain)

**S-5 — Position Sizing `query_realtime`:**
```
annualized_vol
```
(1 feature — sole consumer; FP-3D canonical vol)

**S-6 — Exit Engine `query_realtime`:**
```
normalized_atr, risk_score
```
(2 features — explicit FP internal risk features; excludes ATR which comes from PA per ADR-001)

**S-7 — Trade Journal `query_realtime`:**
```
rsi, ema9, ema21, ema50, trend, support, resistance, breakout, volume_change
```
(9 features — near-identical to AI Signal set, minus `atr`)

**S-8 — Backtesting engine `features_to_compute` + dep graph:**
```
open, high, low, close, volume, ema9, ema21, ema50,
rsi, atr, volume_change, support, resistance, breakout, trend
```
(15 features — does NOT use `FeaturePlatformOrchestrator`; builds own `DependencyGraph` + `FeaturePipeline` directly. Excludes all FP-7A vol chain. Independent from Feature Platform architecture.)

---

## 4. RUNTIME CONSUMER MATRIX

| Consumer | Features Requested | Direct/Derived | DAG Deps Auto-Resolved? | Order Matters? | Intentional Exclusions |
|---|---|---|:---:|:---:|---|
| **Paper Trading** (compute) | All 21 | Both | ✅ Yes — `compute_and_store` calls `FeaturePipeline.compute` which runs DAG | No (topological) | None — computes everything |
| **Live Trading** (compute) | All 21 | Both | ✅ Yes | No | None |
| **StrategyLoop** (query) | Up to all registered | Both | ❌ No — queries already-computed | No | Excludes if not computed |
| **AI Signal** (query) | 10 derived/signal features | Derived | ❌ No — queries already-computed | No | Excludes raw OHLCV, vol chain |
| **Position Sizing** (query) | `annualized_vol` | Derived | ❌ No | No | All others; has NaN fallback |
| **Exit Engine** (query) | 2 risk features | Derived | ❌ No | No | All others; has exception fallback |
| **Trade Journal** (query) | 9 signal features | Derived | ❌ No | No | OHLCV, vol chain, risk chain |
| **Backtesting** (compute) | 14 base features | Both | ✅ Yes — own FeaturePipeline | No | All FP-7A additions (annualized_vol, rolling_std, etc.) |

### 4.1 DAG Dependency Chain (PROVEN from `DEFAULT_FEATURE_DEFINITIONS` and `FeaturePipeline`)

```
Level 0 (Raw OHLCV):     open, high, low, close, volume
Level 1 (Direct):        log_return(close), atr(h,l,c), ema9(c), ema21(c), ema50(c),
                         rsi(c), volume_change(vol), support(low), resistance(high)
Level 2 (Derived):       rolling_std(log_return), normalized_atr(atr,close),
                         annualized_vol(log_return), breakout(c,r,s), trend(ema9,ema21)
Level 3 (Derived):       risk_score(normalized_atr)
Level 4 (Signal):        signal(risk_score)
```

**Total in DEFAULT_FEATURE_DEFINITIONS: 21 features across 5 levels.**  
**Total in FeaturePipeline transformer registry: 21 features.** (Confirmed match) **PROVEN**

---

## 5. DEPENDENCY-RESOLUTION ANALYSIS

### 5.1 Compute Sites (S-1, S-2) — Auto-Resolved

Both paper trading and live trading call `compute_and_store(features_to_compute, symbol, df)`. This delegates to `FeaturePipeline.compute(names, df)` which:
1. Calls `DependencyGraph.get_execution_plan(names)`.
2. `get_execution_plan` calls `topological_sort(target_nodes=names)`.
3. Topological sort computes the transitive closure of dependencies automatically.

**Result: Requesting `["annualized_vol"]` automatically causes `log_return` and `close` to be computed first.** No manual ordering needed. **PROVEN**

### 5.2 Query Sites (S-3 through S-7) — Not Auto-Resolved

`query_realtime` and `query_latest` only return features that were **already computed and stored** in `_online_db`. If the compute site omitted a feature from `features_to_compute`, the feature will be absent from `_online_db`, and `query_realtime` will return no value for it. **PROVEN**

**Critical dependency:** Query sites are consumers of compute-site outputs. They do not trigger computation. The compute-site feature list determines what is available to all query-site consumers.

### 5.3 Completeness Gap (PROVEN)

**S-3 StrategyLoop fallback** (14 features) is a subset of S-1/S-2 (21 features):
- Missing from StrategyLoop fallback: `log_return`, `rolling_std`, `annualized_vol`, `normalized_atr`, `risk_score`, `signal`
- These FP-7A additions are correctly computed at S-1/S-2 level but the StrategyLoop query fallback does not request them.
- This is not a bug — the features exist in `_online_db` when StrategyLoop runs; they are simply not in the query list. If StrategyLoop needs them, it must expand its fallback list.
- **Classification: Design gap — not a defect.** **PROVEN**

**Backtesting engine (S-8)** has a separate, independent copy of the dependency graph that **does not use `FeaturePlatformOrchestrator`** and **does not include the FP-7A vol chain features**:
- Missing: `log_return`, `rolling_std`, `annualized_vol`, `normalized_atr`, `risk_score`, `signal`
- This is a **significant divergence** — backtesting cannot reproduce the live annualized_vol-based sizing.
- **Classification: Architecture gap (out of FP-7D scope — separate concern).** **PROVEN**

---

## 6. DUPLICATION ANALYSIS

### 6.1 Feature List Duplication

| Site | Is Duplicate of `DEFAULT_FEATURE_DEFINITIONS`? | Duplication Type | Risk |
|---|:---:|---|:---:|
| `run_paper_trading.py` features_to_compute | ✅ YES — 21 features, exact name match | **Full copy by string name** | HIGH |
| `live_trading/plugin.py` features_to_compute | ✅ YES — 21 features, exact name match | **Full copy by string name** | HIGH |
| `strategy_loop.py` fallback list | PARTIAL — 14 of 21 names | Subset copy | MEDIUM |
| `backtesting/engine.py` dep dict + feature list | PARTIAL — 14 of 21, plus own dep dict | Full copy of deps | HIGH (diverged) |
| `ai_signal/signal_generator.py` query list | SUBSET — 10 of 21 | Intentional subset | LOW |
| `exit_engine/orchestrator.py` query list | SUBSET — 2 of 21 | Intentional subset | LOW |
| `position_sizing/orchestrator.py` query list | SUBSET — 1 of 21 | Intentional subset | LOW |
| `trade_journal/orchestrator.py` query list | SUBSET — 9 of 21 | Intentional subset | LOW |

**HIGH-RISK DUPLICATION:** `run_paper_trading.py` and `live_trading/plugin.py` both maintain verbatim copies of the 21-feature name list. If a feature is added to `DEFAULT_FEATURE_DEFINITIONS`, it must also be manually added to both locations. **PROVEN**

### 6.2 Registry Availability

`FeaturePlatformOrchestrator.registry.list_all()` returns all registered `FeatureRecord` objects, each with `.name`. After `register_default_features()`, this yields all 21 feature names. **PROVEN** (FP-1 test asserts `len == 21`).

`StrategyLoop` already uses this for its primary resolution path:
```python
feature_names = context.get("feature_names") or [f.name for f in fp_orch.registry.list_all()]
```

This is the only runtime site that **already consults the registry dynamically.** **PROVEN**

---

## 7. CANDIDATE ARCHITECTURE OPTIONS

### Option A — One Hard-Coded Canonical List

**Description:** Extract the 21-feature list into a single module-level constant (e.g., `CANONICAL_COMPUTE_FEATURES` in `orchestrator.py` alongside `DEFAULT_FEATURE_DEFINITIONS`) and replace all hard-coded copies with an import.

**Evidence supporting:**
- The list is already well-defined in `DEFAULT_FEATURE_DEFINITIONS`. The feature names are directly extractable: `[r.name for r in DEFAULT_FEATURE_DEFINITIONS]`.
- Two high-risk copy sites (paper trading, live trading) would collapse to one import.
- No change to API, store, pipeline, transformers, or interface.
- `FeaturePipeline.compute()` already accepts any list and resolves dependencies via DAG.

**Evidence against:**
- The list is static. Adding a feature requires updating `DEFAULT_FEATURE_DEFINITIONS` AND the constant list would auto-update (good), but also auto-compute the new feature in production without explicit testing (risk).
- No provision for per-consumer subset configuration.
- Backtesting engine uses its own `DependencyGraph` and `FeaturePipeline` — it cannot consume this constant without architectural refactoring of the backtesting engine.

**Modification risk:** LOW — two files change, no interface changes.

---

### Option B — Registry-Derived Resolver

**Description:** The canonical compute list is derived at runtime from `registry.list_all()` after `register_default_features()` is called. The compute sites call `[r.name for r in fp_orch.registry.list_all()]` instead of a hard-coded list.

**Evidence supporting:**
- Registry is authoritative and already has all 21 features post-`register_default_features()`.
- `StrategyLoop` already uses exactly this pattern for `query_realtime` (L28 — **PROVEN**).
- Adding a new feature to `DEFAULT_FEATURE_DEFINITIONS` + `register_default_features()` auto-activates it in all compute sites.
- Eliminates the paper/live trading hard-coded copies.

**Evidence against:**
- `FeaturePipeline.compute()` only computes features that have registered transformers in `_transformers` dict. If a feature is in the registry but not in `_transformers`, `compute()` raises `KeyError`. Registering a new feature without adding its transformer to `FeaturePipeline._transformers` would cause a runtime failure.
- The query sites (AI Signal, Exit Engine, Position Sizing, Trade Journal) use intentional **subsets** — not the full registry list. They cannot use registry resolution without filtering logic.
- `StrategyLoop` uses `registry.list_all()` for query, not compute — it queries already-stored values; the risk of missing transformer is absent there.
- **Order matters for understanding but not execution** — DAG resolves order. However, passing all 21 to `compute_and_store` when only a subset is needed incurs computation cost for features with no downstream query consumer.

**Modification risk:** MEDIUM — two compute sites change; need transformer-registry consistency guarantee.

---

### Option C — Named Feature Profiles Resolved Centrally

**Description:** Introduce a `FeatureProfile` concept (e.g., `COMPUTE_PROFILE`, `AI_SIGNAL_PROFILE`, `SIZING_PROFILE`, `EXIT_PROFILE`) as named, centrally-stored lists in `orchestrator.py`. Each consumer references its profile by name.

**Evidence supporting:**
- Addresses the intentional subset issue — consumers can name their specific view.
- Still centralized — one place to update.

**Evidence against:**
- No existing infrastructure for profiles — new abstraction.
- Increases orchestrator complexity.
- Query consumers (AI Signal, Exit Engine etc.) request **exact** feature subsets for efficiency; defining profiles just moves the copy to a different location.
- Adds cognitive overhead without reducing defect risk significantly.
- **INFERRED** — no evidence this pattern is anticipated by existing architecture.

**Modification risk:** MEDIUM-HIGH — new abstraction, multiple files.

---

### Option D — Derive Compute List from Registry Names (Existing Code Observation)

**Description:** This is essentially Option B but explicitly tied to the `DEFAULT_FEATURE_DEFINITIONS` as the source of truth without runtime registry lookup. Specifically: at the module level in `orchestrator.py`, define:
```python
DEFAULT_COMPUTE_NAMES: List[str] = [r.name for r in DEFAULT_FEATURE_DEFINITIONS]
```
This constant is computed once at import time from the existing authoritative source. Compute sites import and use `DEFAULT_COMPUTE_NAMES`.

**Evidence supporting:**
- `DEFAULT_FEATURE_DEFINITIONS` already exists and is authoritative (FP-1 certified). **PROVEN**
- The derivation `[r.name for r in DEFAULT_FEATURE_DEFINITIONS]` is deterministic and always consistent.
- No new concepts — just a derived constant.
- Eliminates paper/live hard-coded lists with a single import.
- Zero interface changes, zero store changes, zero pipeline changes.
- Tests already import `DEFAULT_FEATURE_DEFINITIONS` directly — this follows the same pattern.

**Evidence against:**
- Same transformer-registry consistency risk as Option B (new features must also have transformers).
- Backtesting engine uses its own separate architecture — cannot be unified without backtesting refactoring (out of scope).
- Query subsets remain hard-coded (intentional by design — each consumer explicitly requests only what it needs for performance).

**Modification risk:** LOW — `orchestrator.py` gets one new constant; two compute sites import it.

---

## 8. EVIDENCE FOR/AGAINST EACH OPTION

| Criterion | Option A | Option B | Option C | Option D |
|---|:---:|:---:|:---:|:---:|
| Eliminates high-risk copy sites (paper/live) | ✅ | ✅ | ✅ | ✅ |
| Consistent with existing code patterns | ✅ | PARTIAL | ❌ | ✅ |
| Requires new abstraction | ❌ | ❌ | ✅ | ❌ |
| Auto-derives from authoritative source | PARTIAL | ✅ | PARTIAL | ✅ |
| Registry-registry consistency risk | LOW | MEDIUM | MEDIUM | LOW |
| Number of files changed | 3 | 3 | 5+ | 3 |
| Transformer consistency guaranteed | ❌ | ❌ | ❌ | ❌ (same for all) |
| Addresses query-site intentional subsets | ❌ | ❌ | ✅ | ❌ |
| Backtesting divergence resolved | ❌ | ❌ | ❌ | ❌ |
| Risk of unintended auto-compute | LOW | MEDIUM | MEDIUM | LOW |

---

## 9. RECOMMENDED ARCHITECTURE

### Recommendation: **Option D** — `DEFAULT_COMPUTE_NAMES` constant derived from `DEFAULT_FEATURE_DEFINITIONS`

**Rationale:**

1. **Authoritative source already exists.** `DEFAULT_FEATURE_DEFINITIONS` is the canonical registry of all features, certified by FP-1. Deriving `DEFAULT_COMPUTE_NAMES = [r.name for r in DEFAULT_FEATURE_DEFINITIONS]` at module level is a zero-cost, zero-drift derivation. **PROVEN pattern — consistent with how test files already use it.**

2. **Minimum blast radius.** Only 3 files change: `orchestrator.py` (add constant), `run_paper_trading.py` (import and replace list), `live_trading/plugin.py` (import and replace list). No interface changes, no store changes, no pipeline changes, no existing test changes required (other than FP-7B compat alias tests if `query_history` removal proceeds simultaneously).

3. **Consistent with existing pattern.** `test_sprint004_fp3d_annualized_vol.py` already imports `DEFAULT_FEATURE_DEFINITIONS` and derives names. `test_sprint004_fp1_registration_lifecycle.py` uses `{f.name for f in DEFAULT_FEATURE_DEFINITIONS}`. The new constant follows the same convention.

4. **Query subsets remain intentional.** AI Signal, Exit Engine, Position Sizing, and Trade Journal query only the features they need. This is correct by design — they should not query everything. The centralization effort targets **compute sites** (which must compute all features), not **query sites** (which should remain specific).

5. **`query_history` removal is independent and safe.** With zero external callers (PROVEN), the alias can be deleted from `orchestrator.py` after updating the 4 FP-7B compat alias tests.

### What the Recommendation Does NOT Change

- Feature formulas, transformers, FeatureRecord definitions.
- `DEFAULT_FEATURE_DEFINITIONS` structure.
- `FeatureStore` key schema, query APIs.
- `query_realtime()` / `query_historical()` / FP-7C staleness semantics.
- EventBus behaviour.
- Position sizing / exit engine mathematics.
- AI signal semantics.
- All query-site consumer feature subsets — **intentional, remain as-is.**

---

## 10. COMPATIBILITY / REMOVAL RISK

### 10.1 `query_history()` Removal

| Item | Outcome | Classification |
|---|---|:---:|
| Production callers | Zero — no breakage | **PROVEN** |
| External API surface | None — internal only | **PROVEN** |
| FP-7B compat alias tests (4 tests) | Must be updated/removed — **controlled, intentional** | **PROVEN** |
| Documentation | Mention in gate docs (historical reference) — docs-only update | **PROVEN** |

**Conclusion:** Safe to remove. Only impact is 4 FP-7B tests that explicitly verified the alias (they will be removed as the alias lifecycle is complete).

### 10.2 `DEFAULT_COMPUTE_NAMES` Centralization

| Item | Outcome | Classification |
|---|---|:---:|
| Paper trading feature-computation set | Same canonical 21 names via `DEFAULT_COMPUTE_NAMES` | **PROVEN** |
| Live trading feature-computation set | Same canonical 21 names via `DEFAULT_COMPUTE_NAMES` | **PROVEN** |
| Feature computation output | Same list, same DAG, same transformer pipeline | **PROVEN** |
| Downstream consumers | Unaffected — they query `_online_db` which has same features | **PROVEN** |
| New feature addition workflow | Simpler — add to `DEFAULT_FEATURE_DEFINITIONS`, compute sites auto-update | **INFERRED** |
| Transformer-registry gap risk | If new feature added to definitions without adding transformer → `KeyError` at compute | **PROVEN risk — exists today too** |

> [!IMPORTANT]
> **Scope clarification:** FP-7D-2 establishes feature-computation parity only.
> It does NOT establish end-to-end paper/live trading behavioral parity.
> Position sizing, exit handling, OMS execution, and other runtime-path
> differences remain outside FP-7D-2 scope.

---

## 11. EXACT FILES THAT WOULD NEED MODIFICATION

### FP-7D — Part A: `query_history()` Removal

| File | Change | Risk |
|---|---|:---:|
| `research_platform/feature_platform/orchestrator.py` | Remove `query_history()` method (lines 363–374) | LOW |
| `research_platform/tests/test_sprint004_fp7b_query_api.py` | Remove or update `TestCompatAlias` class (4 tests) | LOW |

### FP-7D — Part B: Compute Site Centralization

| File | Change | Risk |
|---|---|:---:|
| `research_platform/feature_platform/orchestrator.py` | Add `DEFAULT_COMPUTE_NAMES: List[str] = [r.name for r in DEFAULT_FEATURE_DEFINITIONS]` at module level | LOW |
| `scripts/run_paper_trading.py` | Replace hard-coded `features_to_compute` list with `from ... import DEFAULT_COMPUTE_NAMES; features_to_compute = DEFAULT_COMPUTE_NAMES` | LOW |
| `research_platform/live_trading/plugin.py` | Same as above | LOW |

---

## 12. FILES TO REMAIN FROZEN

| File | Reason |
|---|---|
| `research_platform/feature_platform/interfaces.py` | No change — `IFeatureStore.query_latest()` unchanged |
| `research_platform/feature_platform/feature_store.py` | No change — storage unchanged |
| `research_platform/feature_platform/feature_pipeline.py` | No change — transformer registry unchanged |
| `research_platform/feature_platform/dependency_graph.py` | No change |
| `research_platform/feature_platform/transformers.py` | No change — formulas frozen (FP-3D, FP-5) |
| `research_platform/feature_platform/validators.py` | No change |
| `research_platform/feature_platform/plugin.py` | No change |
| `research_platform/ai_signal/signal_generator.py` | Query subset is intentional — no change |
| `research_platform/position_sizing/orchestrator.py` | Query subset `["annualized_vol"]` is intentional — no change |
| `research_platform/exit_engine/orchestrator.py` | Query subset is intentional — no change |
| `research_platform/trade_journal/orchestrator.py` | Query subset is intentional — no change |
| `research_platform/runtime/strategy_loop.py` | Already uses registry dynamic resolution (correct) — no change |
| `backtesting/engine.py` | Independent architecture — out of scope |
| `tests/e2e/*` | E2E tests are integration tests; their feature lists are intentionally isolated |
| All frozen predecessors (FP-1 through FP-7C) | Already certified — DO NOT TOUCH |

---

## 13. TEST STRATEGY

### If FP-7D is Authorized

#### Part A — `query_history` Removal Tests

| Test | Strategy |
|---|---|
| Remove `TestCompatAlias` class from `test_sprint004_fp7b_query_api.py` (4 tests) | Remove entirely — alias deleted; tests are obsolete |
| Add test asserting `query_history` does NOT exist on `FeaturePlatformOrchestrator` | 1 new test in FP-7D suite (mirrors existing `test_interface_does_not_have_query_history`) |
| Regression: Full predecessor suite | Run full regression to confirm no breakage |

#### Part B — `DEFAULT_COMPUTE_NAMES` Centralization Tests

| Test | Strategy |
|---|---|
| `DEFAULT_COMPUTE_NAMES` has exactly the same names as `[r.name for r in DEFAULT_FEATURE_DEFINITIONS]` | 1 test |
| `DEFAULT_COMPUTE_NAMES` has 21 entries (lock count) | 1 test |
| `run_paper_trading.py` uses `DEFAULT_COMPUTE_NAMES` (source inspection) | 1 test (AST grep) |
| `live_trading/plugin.py` uses `DEFAULT_COMPUTE_NAMES` (source inspection) | 1 test (AST grep) |
| Regression: paper trading and live trading compute same features as before | Verified via existing FP-7A test that checks `annualized_vol` inclusion |

**Total new tests: ~7 — small focused suite.**

---

## 14. UNKNOWNS / OPEN QUESTIONS

| # | Question | Classification |
|---|---|:---:|
| **OQ-1** | Should `DEFAULT_COMPUTE_NAMES` be in `orchestrator.py` (beside `DEFAULT_FEATURE_DEFINITIONS`) or in a separate constants module? | **DESIGN DECISION — CTO** |
| **OQ-2** | Should `StrategyLoop` fallback list also be updated to reference `DEFAULT_COMPUTE_NAMES`? Currently it has the old 14-feature subset; updating would cause it to query all 21 (including FP-7A additions) when used as fallback. This may be correct behaviour or may be out of scope. | **SCOPE DECISION — CTO** |
| **OQ-3** | Should the backtesting engine divergence (missing FP-7A vol chain, own dep graph) be addressed in FP-7D or a future sprint? This is a larger refactoring and is separate from the centralization objective. | **SCOPE DECISION — CTO** |
| **OQ-4** | Should FP-7D Part A (alias removal) and Part B (compute centralization) be implemented as one change or two sequential changes? They are independent. | **EXECUTION DECISION — CTO** |
| **OQ-5** | Is there a risk the StrategyLoop `registry.list_all()` path (primary resolution, not fallback) already effectively solves the centralization problem for query sites — meaning only the compute sites need changing? | **CONFIRMED YES by evidence — compute sites are the only ones with the problem** |

---

## 15. CTO DECISION REQUIRED

Discovery is complete. Implementation is NOT authorized until CTO decision is received.

### Decision Points

> [!IMPORTANT]
> **Decision 1 — `query_history` removal (Part A):**
> Authorize removal of `query_history()` compat alias from `orchestrator.py` and update of 4 FP-7B alias tests?
> - Evidence: Zero external callers. Alias is now historical only.
> - Risk: Controlled — test update only.

> [!IMPORTANT]
> **Decision 2 — Compute site centralization (Part B):**
> Authorize introducing `DEFAULT_COMPUTE_NAMES` constant and replacing hard-coded lists in `run_paper_trading.py` and `live_trading/plugin.py`?
> - Evidence: High-risk copy duplication exists at both sites; paper and live trading use the same canonical feature-computation set post-change.
> - Risk: Low — same feature list, same compute pipeline, no DAG or formula changes. Note: this establishes feature-computation parity only, not end-to-end trading behavioral parity.

> [!IMPORTANT]
> **Decision 3 — Open Questions OQ-2 and OQ-3:**
> Is StrategyLoop fallback list update and backtesting engine divergence in scope for FP-7D, or deferred to a separate sprint?

> [!NOTE]
> **Decision 4 — Sequence:**
> Should Part A and Part B be implemented together in one sub-stage or sequentially (FP-7D-1 then FP-7D-2)?

---

```
╔════════════════════════════════════════════════════════════════════════════════╗
║                                                                                ║
║   SPRINT-004 FP-7D: DISCOVERY COMPLETE                                         ║
║                                                                                ║
║   Part A — query_history() Removal:                                            ║
║     Production callers:   ZERO (PROVEN)                                        ║
║     Test impact:          4 FP-7B alias tests (controlled removal)             ║
║     Risk:                 NONE to production                                   ║
║                                                                                ║
║   Part B — Compute Site Centralization:                                        ║
║     High-risk copy sites: 2 (paper trading, live trading) — PROVEN             ║
║     Recommended solution: DEFAULT_COMPUTE_NAMES constant (Option D)            ║
║     Query sites intentional subsets: PRESERVED (no change)                    ║
║     Files to change:      3 (orchestrator.py + 2 compute sites)                ║
║     Interface changes:    ZERO                                                 ║
║     Formula changes:      ZERO                                                 ║
║     Store changes:        ZERO                                                 ║
║                                                                                ║
║   STOP — AWAITING CTO AUTHORIZATION                                            ║
║                                                                                ║
╚════════════════════════════════════════════════════════════════════════════════╝
```
