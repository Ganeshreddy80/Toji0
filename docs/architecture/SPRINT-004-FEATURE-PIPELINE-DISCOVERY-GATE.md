# SPRINT 004 — FEATURE PIPELINE DISCOVERY GATE
## Architecture Audit: Price Action → Feature Pipeline Integration Boundary

**Author:** TOJI CTO / Lead Architect  
**Date:** 2026-08-11  
**Governance:** Master Architecture Governance — Sprint 004 / Feature Pipeline Discovery  
**Predecessor:** `SPRINT-003-PA5-GATE.md` — **PASS** (Empirical Performance Baseline Certified)  
**Stage:** DISCOVERY / ARCHITECTURE AUDIT ONLY — Zero production code changes  

---

## 1. CURRENT ARCHITECTURE OVERVIEW

The platform contains two logically distinct systems that currently operate in a partial integration:

### Layer 1 — Price Action Engine (`research_platform/price_action/`)
The canonical, Sprint 003-certified tick-to-bar engine.

| Component | File | Purpose |
|---|---|---|
| `PriceActionOrchestrator` | `orchestrator.py` | Processes ticks → OHLC bars, swing detection, FVG, BOS/CHOCH, ATR, VWAP |
| `IPriceActionOrchestrator` | `interfaces.py` | Public contract: `process_tick()`, `get_bars()`, `get_atr()`, `get_vwap()`, `get_swings()`, `get_structure_changes()`, `get_blocks()`, `get_gaps()` |
| `PriceActionRepository` | `repository.py` | In-memory storage for swings, gaps, blocks, structure changes (per symbol) |
| `StructureDetected` | `events.py` | Event published on swing point, BOS, or CHOCH detection |
| `ImbalanceDetected` | `events.py` | Event published on Fair Value Gap (FVG) detection |
| `SessionUpdated` | `events.py` | Defined but **never published** by `PriceActionOrchestrator` |

### Layer 2 — Feature Platform (`research_platform/feature_platform/`)
An institutional DAG-based indicator computation, validation, and lifecycle management system.

| Component | File | Purpose |
|---|---|---|
| `FeaturePlatformOrchestrator` | `orchestrator.py` | Central coordinator: registration, DAG compute, PIT store, validation |
| `FeaturePipeline` | `feature_pipeline.py` | Executes topological-ordered transformer DAG against a DataFrame input |
| `DependencyGraph` | `dependency_graph.py` | Topological sort engine, cycle detection, impact analysis |
| `FeatureStore` | `feature_store.py` | Point-In-Time offline + online versioned feature storage |
| `FeatureRegistry` | `registry.py` | Thread-safe in-memory registry of `FeatureRecord` definitions |
| `FeatureRepository` | `repository.py` | Persistence layer for feature definition records |
| `FeatureValidator` | `validators.py` | Lookahead bias, NaN ratio, stationarity, and drift checks |
| `FeatureCache` | `cache.py` | Hash-keyed in-memory cache for intermediate results |
| `IFeaturePipeline` etc. | `interfaces.py` | 13 abstract interfaces (Registry, Store, Pipeline, Validator, Cache, Scheduler, etc.) |
| `FeatureRecord` etc. | `models.py` | 11 Pydantic frozen models |
| `FeaturePlatformPlugin` | `plugin.py` | DI container integration |
| `FeatureRegistered`, `FeatureCalculated` etc. | `events.py` | 16 platform-internal lifecycle events |
| Transformers (18 total) | `transformers.py` | CloseTransformer, LogReturnTransformer, AtrTransformer, EmaTransformer, RsiTransformer, SupportTransformer, ResistanceTransformer, BreakoutTransformer, TrendDirectionTransformer, etc. |

---

## 2. CURRENT DATA FLOW

```
                    Exchange WebSocket
                          │
                          ▼
               ┌─────────────────────┐
               │  Market Gateway     │
               │  (Tick Arrival)     │
               └─────────┬───────────┘
                          │  process_tick(symbol, price, ts, vol)
                          ▼
               ┌─────────────────────┐
               │ PriceActionOrch.    │  ── publishes ──► StructureDetected (EventBus)
               │  - Tick History     │  ── publishes ──► ImbalanceDetected (EventBus)
               │  - 1m OHLC Bars     │  (SessionUpdated: DEFINED but NEVER published)
               │  - VWAP / ATR       │
               └─────────┬───────────┘
                          │  get_bars(symbol)  [public contract]
                          ▼
               ┌─────────────────────┐
               │  pd.DataFrame       │  ← Manual per-tick inline construction
               │  (bars_list → df)   │
               └─────────┬───────────┘
                          │  compute_and_store(features, symbol, df)
                          ▼
               ┌─────────────────────┐
               │ FeaturePlatformOrch │
               │  - DAG Pipeline     │
               │  - Validation       │  ── publishes ──► FeatureCalculated (EventBus)
               │  - PIT Feature Store│  ── publishes ──► FeatureValidated  (EventBus)
               └─────────┬───────────┘
                     ┌────┴────┐
                     │         │
                     ▼         ▼
           query_latest()    store.query_latest()
                     │         │
           ┌─────────┘         └──────────────┐
           │                                  │
           ▼                                  ▼
    AISignalGenerator            ExitEngine / PositionSizing
    ConfluenceScoringEngine      TradeJournal
    StrategyComposer
```

---

## 3. COMPONENT INVENTORY

### 3.1 Price Action Public API (Certified in Sprint 003)

| Method | Signature | Consumers |
|---|---|---|
| `process_tick` | `(symbol, price, ts, vol) → None` | `run_paper_trading.py`, `live_trading/plugin.py`, E2E tests |
| `get_bars` | `(symbol) → List[Dict]` | `run_paper_trading.py`, `live_trading/plugin.py`, `backend/main.py`, E2E tests |
| `get_atr` | `(symbol) → float` | `run_paper_trading.py`, `ai_signal/signal_generator.py`, `confluence/scoring_engine.py` |
| `get_vwap` | `(symbol) → float` | `run_paper_trading.py`, `ai_signal/signal_generator.py`, `confluence/scoring_engine.py` |
| `get_swings` | `(symbol) → List[SwingPoint]` | `confluence/scoring_engine.py` |
| `get_structure_changes` | `(symbol) → List[MarketStructureChange]` | `confluence/scoring_engine.py` |
| `get_blocks` | `(symbol) → List[BlockStructure]` | `confluence/scoring_engine.py` |
| `get_gaps` | `(symbol) → List[ImbalanceGap]` | `confluence/scoring_engine.py` |

### 3.2 Feature Platform Public API

| Method | Signature | Consumers |
|---|---|---|
| `register_feature` | `(record: FeatureRecord) → None` | `run_paper_trading.py`, `live_trading/plugin.py`, E2E tests (inline per-tick) |
| `compute_and_store` | `(names, symbol, df) → pd.DataFrame` | `run_paper_trading.py`, `live_trading/plugin.py`, E2E tests |
| `query_realtime` | `(names, symbols) → pd.DataFrame` | NOT called from production code |
| `store.query_latest` | `(names, symbols) → pd.DataFrame` | `ai_signal/signal_generator.py`, `exit_engine/orchestrator.py`, `position_sizing/orchestrator.py`, `trade_journal/orchestrator.py` |
| `store.query_historical` | `(names, symbols, start, end) → pd.DataFrame` | Not observed in production callers |
| `evaluate_promotion` | `(name, df) → FeatureApprovalReport` | Not wired to any production caller |
| `evaluate_freshness` | `(name, last_update) → FeatureFreshnessMetrics` | Not wired to any production caller |
| `calculate_importance` | `(name, values, returns) → FeatureImportanceMetrics` | Not wired to any production caller |

### 3.3 Feature Transformer Registry (18 transformers in `FeaturePipeline`)

| Technical Name | Transformer Class | Dependencies |
|---|---|---|
| `close` | `CloseTransformer` | — |
| `open` | `OpenTransformer` | — |
| `high` | `HighTransformer` | — |
| `low` | `LowTransformer` | — |
| `volume` | `VolumeTransformer` | — |
| `log_return` | `LogReturnTransformer` | `close` |
| `rolling_std` | `RollingStdTransformer` | `log_return` |
| `atr` | `AtrTransformer` (FP) | `high`, `low`, `close` |
| `normalized_atr` | `NormalizedAtrTransformer` | `atr`, `close` |
| `risk_score` | `RiskScoreTransformer` | `normalized_atr` |
| `signal` | `SignalTransformer` | `risk_score` |
| `ema9` | `EmaTransformer(9)` | `close` |
| `ema21` | `EmaTransformer(21)` | `close` |
| `ema50` | `EmaTransformer(50)` | `close` |
| `rsi` | `RsiTransformer` | `close` |
| `volume_change` | `VolumeChangeTransformer` | `volume` |
| `support` | `SupportTransformer` | `low` |
| `resistance` | `ResistanceTransformer` | `high` |
| `breakout` | `BreakoutTransformer` | `close`, `resistance`, `support` |
| `trend` | `TrendDirectionTransformer` | `ema9`, `ema21` |

---

## 4. EVENT FLOW AUDIT

### 4.1 Price Action Events — Publisher / Subscriber Map

| Event | Publisher | Registered Subscribers |
|---|---|---|
| `StructureDetected` | `PriceActionOrchestrator` (4 call sites) | **NONE** registered in production code |
| `ImbalanceDetected` | `PriceActionOrchestrator` (2 call sites) | **NONE** registered in production code |
| `SessionUpdated` | **NEVER published** by `PriceActionOrchestrator` | **NONE** registered anywhere |

> **Critical Finding:** `StructureDetected` and `ImbalanceDetected` are published on every bar close (~26% of ticks based on PA-5 evidence, ≈261 events per 1,000 ticks), but **zero subscribers exist** in the research_platform production code. The Feature Pipeline does not subscribe to these events. All feature computation is triggered synchronously per-tick via direct `compute_and_store()` calls, not via event subscription.

### 4.2 Feature Platform Events — Publisher / Subscriber Map

| Event | Publisher | Registered Subscribers |
|---|---|---|
| `FeatureRegistered` | `FeaturePlatformOrchestrator.register_feature()` | **NONE** |
| `FeatureCalculated` | `FeaturePlatformOrchestrator.compute_and_store()` | **NONE** |
| `FeatureValidated` | `FeaturePlatformOrchestrator.compute_and_store()` | **NONE** |
| `FeatureRejected` | `FeaturePlatformOrchestrator.compute_and_store()` | **NONE** |
| `FeatureFreshnessUpdated` | `FeaturePlatformOrchestrator.evaluate_freshness()` | **NONE** |
| `FeatureImportanceCalculated` | `FeaturePlatformOrchestrator.calculate_importance()` | **NONE** |
| `FeatureVersionCreated` | `FeaturePlatformOrchestrator.register_version()` | **NONE** |
| `FeaturePromoted` | `FeaturePlatformOrchestrator.evaluate_promotion()` | **NONE** |

> **Finding:** All 16 Feature Platform events are published into the EventBus but have zero registered subscribers in any production module. The event bus is functioning as a fire-and-forget audit log, not an active integration bus.

### 4.3 Duplicate `SessionUpdated` Event Definition

Two separate `SessionUpdated` event classes exist in the repository:
- `research_platform/price_action/events.py` (line 20) — imported in `PriceActionOrchestrator` but never published
- `market_intelligence/core/events.py` (line 152) — published by `market_intelligence/core/analysis/session.py`

These are structurally separate classes with no shared base (beyond `BaseEvent`). No subscriber exists for either.

### 4.4 Duplicate `BreakOfStructureDetected` vs `StructureDetected`

- `market_intelligence/core/events.py` defines `BreakOfStructureDetected`
- `market_intelligence/core/analysis/breakout.py` publishes `BreakOfStructureDetected`
- `research_platform/price_action/events.py` defines `StructureDetected`
- `research_platform/price_action/orchestrator.py` publishes `StructureDetected`

These are parallel, non-integrated event systems for the same conceptual domain (structure break detection). No consumer subscribes to either.

---

## 5. PUBLIC CONTRACTS & OWNERSHIP BOUNDARIES

### 5.1 Price Action Ownership (Sprint 003-Certified)

**Owner:** `research_platform/price_action/`  
**Public API surface:** `IPriceActionOrchestrator` → `get_bars()`, `get_atr()`, `get_vwap()`, `get_swings()`, `get_structure_changes()`, `get_blocks()`, `get_gaps()`  
**Boundary rule (certified):** No external code may access `pa_orch._bars` directly. All access through public contract.

### 5.2 Feature Platform Ownership

**Owner:** `research_platform/feature_platform/`  
**Public API surface (currently used by production callers):**
- `register_feature(record)` — DI-resolvable, publicly accessible
- `compute_and_store(names, symbol, df)` — primary computation entry point
- `.store.query_latest(names, symbols)` — queried directly (bypasses `query_realtime()`)

**Boundary issues:**
1. Callers access `feature_platform.store` (internal property) directly instead of `feature_platform.query_realtime()`. This is a minor ownership leak — `.store` is exposed as a public property but bypasses the orchestrator's `query_realtime()` method.
2. `register_feature()` is called **per-tick inline** in both `run_paper_trading.py` and `live_trading/plugin.py`. The registry raises `ValueError` on duplicate registration; callers suppress it silently with `except ValueError: pass`. This is an idempotency workaround rather than a designed re-entrant API.

---

## 6. INTEGRATION BOUNDARY ANALYSIS

### 6.1 Current Integration Pattern (Synchronous Polling)

```
per-tick handler:
    pa_orch.process_tick(symbol, price, ts, vol)
    bars_list = pa_orch.get_bars(symbol)
    df = pd.DataFrame(bars_list)
    feature_platform.compute_and_store(features_to_compute, symbol, df)
```

**Problems with this pattern:**
1. **Registration per-tick:** `register_feature()` is called on every tick (15 features × every tick). Suppressed `ValueError` is load-bearing correct behavior by accident, not design.
2. **DataFrame rebuild per-tick:** `pd.DataFrame(bars_list)` reconstructs the full bar DataFrame from scratch on every tick. At 10 symbols × 200 bars this is 2,000-row DataFrame construction per tick.
3. **No event-driven coordination:** Feature computation is not triggered by `StructureDetected` or `ImbalanceDetected` events. The event bus carries these signals but nothing acts on them.
4. **VWAP and ATR duplication:** `pa_orch.get_atr()` produces an ATR value. `FeaturePipeline` also independently computes `atr` via `AtrTransformer`. Both are derived from the same bars but computed separately. Callers in `run_paper_trading.py` inject `pa_orch.get_atr()` into `indicators` dict, then the feature pipeline also computes `atr` into the same dict. They may diverge in edge cases.
5. **Feature platform `query_realtime()` unused:** The orchestrator exposes `query_realtime()` but callers use `feature_platform.store.query_latest()` directly.

### 6.2 Downstream Consumers of Feature Store

| Consumer | Feature Queries Used | Pattern |
|---|---|---|
| `ai_signal/signal_generator.py` | `rsi, ema9, ema21, ema50, atr, trend, support, resistance, breakout, volume_change` | `store.query_latest()` |
| `exit_engine/orchestrator.py` | `atr, normalized_atr, risk_score` | `store.query_latest()` via `_feature_store` property |
| `position_sizing/orchestrator.py` | `volatility` | `store.query_latest()` (note: `volatility` transformer does NOT exist in `FeaturePipeline` registry) |
| `trade_journal/orchestrator.py` | (feature list; query_latest) | `store.query_latest()` |
| `confluence/scoring_engine.py` | `get_atr()`, `get_vwap()`, `get_swings()` etc. | Queries `PriceActionOrchestrator` directly (NOT Feature Store) |
| `runtime/strategy_loop.py` | Calls `extract_features()` on `FeaturePlatformOrchestrator` | **Method does not exist** on `FeaturePlatformOrchestrator` |

---

## 7. IDENTIFIED RISKS, CONTRADICTIONS & VIOLATIONS

### R-1 CRITICAL — Missing Feature: `volatility`
`position_sizing/orchestrator.py` calls `store.query_latest(["volatility"], [symbol])`.  
`FeaturePipeline` has **no `volatility` transformer** registered. `query_latest()` will return an empty DataFrame silently. Position sizing will operate on null volatility data.

### R-2 HIGH — `StrategyLoop.extract_features()` Method Does Not Exist
`runtime/strategy_loop.py` calls `feature_store.extract_features()` on `FeaturePlatformOrchestrator`. This method does not exist. The call is inside a `try/except` block that silently swallows the `AttributeError`.

### R-3 HIGH — `SessionUpdated` Never Published by Price Action
`SessionUpdated` is imported in `PriceActionOrchestrator` but the orchestrator contains no logic to publish it. No session boundary detection (London open, NY open, Asia session) exists in the Price Action engine. The event is a stub.

### R-4 HIGH — ATR Duplication / Divergence Risk
Two independent ATR computations coexist:
- `PriceActionOrchestrator._calculate_atr()` (simple moving average, 14 bars)
- `FeaturePipeline` `AtrTransformer` (rolling mean of True Range, 14 bars)

Both are applied to the same bar data but are computed independently. Downstream callers may use either source. Paper trading injects `pa_orch.get_atr()` into `indicators` (line 390) while the feature pipeline separately computes `atr` (via `compute_and_store`). Any numerical divergence between them is undocumented and untested.

### R-5 MEDIUM — Per-Tick `register_feature()` Pattern is Fragile
Registering all 15 features on every tick, suppressing `ValueError` silently, is not a designed idempotency pattern. The registry's `register()` method explicitly raises `ValueError` on re-registration. This pattern is correct by accident and will break if the registry's behavior is ever changed.

### R-6 MEDIUM — `store.query_latest()` Bypasses Public Orchestrator Interface
Production callers (`ai_signal`, `exit_engine`, `position_sizing`, `trade_journal`) access `feature_platform.store.query_latest()` directly rather than `feature_platform.query_realtime()`. This couples downstream consumers to the storage layer internal structure, bypassing any future caching, validation, or middleware the orchestrator could insert.

### R-7 MEDIUM — No EventBus Subscriber for `StructureDetected` or `ImbalanceDetected`
These events are published ~261 times per 1,000 ticks but are consumed by no production subscriber. If future Feature Pipeline stages are intended to react to structure changes (e.g., feature recompute on regime shift), the subscription infrastructure does not exist.

### R-8 LOW — Duplicate `SessionUpdated` Class Naming Collision
Two classes named `SessionUpdated` exist in different modules. A future import that accidentally mixes namespaces (`from research_platform.price_action.events import SessionUpdated` vs `from market_intelligence.core.events import SessionUpdated`) would silently use the wrong class without error.

### R-9 LOW — `BreakOfStructureDetected` vs `StructureDetected` Parallel Systems
`market_intelligence/` has a separate price action detection stack (`breakout.py`, `session.py`) that publishes its own events. These are never integrated with `research_platform/price_action/`. Ownership of "structure detection" is split across two subsystems.

### R-10 LOW — Feature Platform Governance Features Are Unwired
`evaluate_promotion()`, `evaluate_freshness()`, `calculate_importance()`, `check_collinearity()` — all implemented in `FeaturePlatformOrchestrator` — are never called from any production path. They are implemented but functionally unreachable from the live pipeline.

---

## 8. EXISTING TEST COVERAGE ASSESSMENT

### 8.1 Feature Platform Unit Tests (`test_feature_platform.py`)

| Test | Scope | Coverage |
|---|---|---|
| `test_feature_registry_and_dependency_checks` | Registration, duplicate rejection, missing dependency rejection | ✅ |
| `test_dependency_graph_cycle_detection` | Cycle detection, topological sort failure | ✅ |
| `test_dependency_graph_sorting` | Topological ordering, reverse dependency mapping | ✅ |
| `test_pipeline_calculations` | Full DAG compute through signal (close→log_return→rolling_std→atr→normalized_atr→risk_score→signal) | ✅ |
| `test_feature_validator` | Lookahead bias detection, healthy data approval | ✅ |
| `test_feature_cache` | Hash key generation, set/get/clear | ✅ |

### 8.2 E2E Feature Pipeline Tests

| Test File | Scope |
|---|---|
| `tests/e2e/test_end_to_end_trading_verification.py` | Full PA→Feature→Strategy→OMS loop; `compute_and_store`, `query_latest` |
| `tests/e2e/test_signal_lifecycle.py` | Feature + AI signal + trade decision E2E |
| `tests/e2e/test_real_pipeline.py` | Full pipeline integration |
| `tests/e2e/test_market_to_strategy_pipeline.py` | Feature platform + strategy pipeline |
| `tests/e2e/test_live_market_runtime_flow.py` | Live market runtime feature flow |

### 8.3 Coverage Gaps

| Gap | Risk |
|---|---|
| No test for `volatility` feature missing from pipeline registry | R-1 (CRITICAL) |
| No test for ATR numerical divergence (PA vs Feature Platform) | R-4 (HIGH) |
| No test for `extract_features()` AttributeError in StrategyLoop | R-2 (HIGH) |
| No test for `SessionUpdated` publication from Price Action | R-3 (HIGH) |
| No test for per-tick `register_feature()` idempotency behavior | R-5 (MEDIUM) |
| No test verifying `store.query_latest()` vs `query_realtime()` parity | R-6 (MEDIUM) |
| No test for `StructureDetected` / `ImbalanceDetected` subscriber behavior | R-7 (MEDIUM) |
| No test for `evaluate_promotion()`, `evaluate_freshness()`, `calculate_importance()` in live paths | R-10 (LOW) |

---

## 9. PERSISTENCE & STORAGE BOUNDARIES

### 9.1 In-Memory Only (All Repositories)

All storage in both Price Action and Feature Platform is currently **in-memory only**:
- `PriceActionRepository`: swings, gaps, blocks, structure changes (per symbol, unbounded)
- `FeatureRepository`: feature definitions (FeatureRecord registry)
- `FeatureStore`: PIT offline + online stores (grows unbounded per session)
- `FeatureVersionRepository`, `FeatureFreshnessRepository`, `FeatureImportanceRepository`, `FeatureApprovalRepository`: all in-memory

**Implication:** All feature history is lost on restart. No persistence layer exists for computed feature values.

### 9.2 PIT Store Unbounded Growth Risk

`FeatureStore._offline_db` stores a full copy of every `compute_and_store()` invocation's output DataFrame per `(name, version, symbol)` key. With 15 features × N ticks per session, this grows without any eviction policy. No equivalent to the PA engine's 200-bar or 1,000-tick caps exists in the feature store.

---

## 10. DETERMINISM REQUIREMENTS

### 10.1 PA-Certified Determinism (Inherited Baseline)
`PriceActionOrchestrator` is certified deterministic in PA-4 (SHA-256 canonical fingerprint verified). The `get_bars()` output for a given tick sequence is reproducible.

### 10.2 Feature Pipeline Determinism Status
The `FeaturePipeline` transformers are stateless pure functions applied to DataFrames. Given the same DataFrame input, transformer outputs are deterministic. However:
- No determinism test exists for the Feature Pipeline comparable to the PA-4 replay test.
- `compute_and_store()` uses `datetime.now(timezone.utc)` as the `as_of` timestamp when one is not provided, introducing a non-deterministic timestamp component into the stored data.
- `FeatureRecord.created_time` and `updated_time` use `datetime.utcnow` (non-deterministic wall clock).

---

## 11. PERFORMANCE CONSTRAINTS (FROM PA-5 BASELINE)

From the PA-5 empirical baseline:

| Metric | Measured Value |
|---|---|
| `process_tick()` p50 latency | 0.71–0.96 μs |
| `process_tick()` p99 latency | 58–107 μs |
| `process_tick()` throughput | 70,000–118,000 ticks/sec |

Any Feature Pipeline integration that is called on every tick must not materially degrade this baseline. Key considerations:
- `pd.DataFrame(bars_list)` construction currently runs per-tick, on top of PA processing — this is the dominant feature pipeline latency contributor.
- `compute_and_store()` runs a validator (`FeatureValidator`) per feature name, which includes stationarity checks (ADF test or rolling statistics) that are computationally non-trivial.

---

## 12. EXISTING IMPLEMENTATION REUSE OPPORTUNITIES

| Asset | Reuse Status | Notes |
|---|---|---|
| 20 transformers in `feature_pipeline.py` | ✅ Reusable | All stateless, pure-DataFrame functions. Well-tested. |
| `DependencyGraph` (topological sort, cycle detection) | ✅ Reusable | Production-quality. Cycle detection and impact analysis built in. |
| `FeatureStore` PIT infrastructure | ✅ Reusable | PIT query, offline/online split is correct architecture |
| `FeatureValidator` (lookahead, NaN, stationarity) | ✅ Reusable | Functional validation with well-tested pass/fail logic |
| `FeaturePlatformOrchestrator` `register_feature()` | ⚠️ Partially | Registry + DI integration works. Per-tick registration pattern is broken. |
| `FeaturePlatformOrchestrator.compute_and_store()` | ⚠️ Partially | Core compute works. `as_of` timestamp is non-deterministic. Validator cost needs profiling. |
| `FeaturePlatformOrchestrator.evaluate_promotion()` etc. | ❌ Unreachable | Governance features implemented but no callers. |
| `SessionUpdated` event | ❌ Stub | Defined and imported but never published. Requires session boundary detection logic. |

---

## 13. RECOMMENDED INTEGRATION BOUNDARY

### 13.1 Canonical Integration Contract

The Feature Pipeline should receive its OHLCV data exclusively through the public `get_bars()` contract. The integration boundary should be:

```
PriceActionOrchestrator
    └─ get_bars(symbol)  →  [list of dicts]  →  pd.DataFrame
                                                    └─ FeaturePlatformOrchestrator.compute_and_store()
```

The DataFrame passed to `compute_and_store()` must include columns: `timestamp`, `open`, `high`, `low`, `close`, `volume`.

### 13.2 Boundary Violations to Eliminate

1. **`store.query_latest()` direct access** — should route through `query_realtime()`.
2. **Per-tick `register_feature()` inline** — features should be registered once at startup/initialization, not per-tick.
3. **ATR duplication** — architectural decision needed: is PA-ATR or Feature-Platform-ATR the canonical source? Document and consolidate.

### 13.3 Missing Boundaries Requiring Decision

1. **`StructureDetected` → Feature recompute path** — does a structure break trigger feature recomputation? If yes, a subscriber must be wired. If no, the events remain advisory-only fire-and-forget audit signals.
2. **`SessionUpdated` publication** — is session boundary detection within Price Action scope or a separate subsystem concern? Currently neither publishes a meaningful session event in the research platform.

---

## 14. PROPOSED STAGED IMPLEMENTATION PLAN

> **Important:** This plan is subject to CTO authorization before any code changes. Each sub-stage requires explicit CTO gate.

### Stage FP-1: Feature Registration Lifecycle (No production algorithm changes)
- Create a `FeatureBootstrap` utility that registers all 15 production features once at container startup, eliminating per-tick `register_feature()` calls.
- Add idempotent `register_feature_if_absent()` method to `FeaturePlatformOrchestrator` or use startup bootstrap.
- Tests: prove features are registered exactly once; tick handler no longer registers.

### Stage FP-2: `query_realtime()` Enforcement (Interface cleanup)
- Route all `store.query_latest()` callers to `query_realtime()`.
- No algorithmic changes — pure re-routing through the existing orchestrator public interface.
- Affected: `ai_signal`, `exit_engine`, `position_sizing`, `trade_journal`.

### Stage FP-3: `volatility` Feature Gap (Missing transformer)
- Audit whether `position_sizing` requires `volatility` as distinct from `normalized_atr` or `risk_score`.
- If yes: add `volatility` transformer. If no: update caller to query existing equivalent.
- Gate: explicit CTO decision on scope before implementation.

### Stage FP-4: ATR Canonical Source Decision
- Decide and document: is `pa_orch.get_atr()` or `feature_platform` ATR the canonical source?
- Eliminate the duplicate. Document in architecture boundary contract.

### Stage FP-5: Feature Pipeline Determinism Validation
- Comparable to PA-4 synthetic replay: run the Feature Pipeline twice over an identical bar sequence and assert identical output DataFrames.
- Fix the `datetime.now()` non-deterministic `as_of` timestamp in `compute_and_store()` (inject a `reference_time` parameter with default `None` → `datetime.now()`).

### Stage FP-6: EventBus Subscriber Wiring (If authorized)
- Wire `StructureDetected` and `ImbalanceDetected` subscribers if event-driven feature computation is desired.
- Wire `FeatureCalculated` to any downstream notification consumer if desired.
- Defer: requires explicit CTO decision on event-driven vs polling architecture.

---

## 15. OPEN QUESTIONS FOR CTO

1. **ATR canonical source:** Should `pa_orch.get_atr()` or the Feature Platform `AtrTransformer` be the single authoritative ATR for strategy and risk consumption?
2. **`volatility` feature:** Is `position_sizing`'s `volatility` query intentional or a bug? What is the expected computation?
3. **`SessionUpdated` scope:** Is session boundary detection (London/NY/Asia) within Price Action scope, or a separate market intelligence concern? Is it required in Sprint 004?
4. **EventBus subscriber pattern:** Is the Feature Pipeline to be event-driven (subscribing to `StructureDetected` → recompute) or remain synchronous/polling (called per-tick from tick handler)?
5. **FeatureStore eviction policy:** Should the `FeatureStore` offline store be bounded (like PA bars at 200), or should it grow unbounded per session?
6. **Governance features:** Should `evaluate_promotion()`, `evaluate_freshness()`, and `calculate_importance()` be wired in Sprint 004 or deferred to a later sprint?

---

## 16. PRODUCTION FILES MODIFIED IN DISCOVERY STAGE

**Zero.** This is an architecture audit and discovery report only.

```text
Production Python Files Modified: 0
New Test Files Created: 0
New Documentation Files Created: 1 (this document)
```

---

## 17. FINAL DISCOVERY GATE CLASSIFICATION

```text
╔════════════════════════════════════════════════════════════════════════════╗
║                                                                            ║
║   SPRINT-004 FEATURE PIPELINE DISCOVERY GATE:                              ║
║   COMPLETE — AWAITING CTO AUTHORIZATION FOR IMPLEMENTATION                 ║
║                                                                            ║
║   Architecture Status:                                                     ║
║   • Feature Platform: Implemented, partially integrated, sound core.       ║
║   • Integration boundary: Functional but architecturally fragile.          ║
║   • Critical gap: "volatility" feature missing from pipeline (R-1).        ║
║   • High risk: ATR duplication between PA and Feature Platform (R-4).      ║
║   • High risk: StrategyLoop.extract_features() method does not exist (R-2).║
║   • EventBus: All events published, zero subscribers in any module.        ║
║   • Persistence: In-memory only; no disk/DB layer; lost on restart.        ║
║   • Determinism: Feature Pipeline not yet replay-tested (gap vs PA-4).     ║
║                                                                            ║
║   Production files changed in this discovery stage: 0.                    ║
║   Awaiting CTO authorization before any implementation begins.             ║
║                                                                            ║
╚════════════════════════════════════════════════════════════════════════════╝
```

---

**STOP.** Discovery audit is complete. Returning gate document for CTO review and stage authorization.
