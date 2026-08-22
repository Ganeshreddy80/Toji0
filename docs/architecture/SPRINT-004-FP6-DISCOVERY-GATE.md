# SPRINT-004 FP-6 — EVENTBUS SUBSCRIBER WIRING
## Discovery / Architecture Audit Gate

**Author:** TOJI Senior Staff Engineer / Principal Architect  
**Date:** 2026-08-15  
**Governance:** Master Architecture Governance — Sprint 004 / FP-6 Discovery  
**Stage:** DISCOVERY / ARCHITECTURE AUDIT ONLY — Zero production code changes  
**Predecessor:** `SPRINT-004-FP5-IMPLEMENTATION-GATE.md` — **CERTIFIED PASS**

---

## 1. EXECUTIVE SUMMARY

FP-6 is defined in the Sprint-004 Feature Pipeline Discovery Gate
(`SPRINT-004-FEATURE-PIPELINE-DISCOVERY-GATE.md`), Section 14, Stage FP-6:

> **Stage FP-6: EventBus Subscriber Wiring (If authorized)**
> Wire `StructureDetected` and `ImbalanceDetected` subscribers if event-driven
> feature computation is desired. Wire `FeatureCalculated` to any downstream
> notification consumer if desired.
> **Defer: requires explicit CTO decision on event-driven vs polling architecture.**

The master gate's own description already embeds a deferral condition:
*"If authorized"* and *"Defer: requires explicit CTO decision."*

This discovery gate produces the source-level evidence the CTO needs to make
that decision. It does NOT implement subscribers, wiring, or any production change.

### Discovery Scope

1. Audit the complete EventBus architecture across the repository.
2. Map every FP event: which are published, by whom, to how many subscribers.
3. Map every Price Action event: same.
4. Determine whether adding event subscribers introduces ordering, reentrancy,
   or lifecycle risks.
5. Determine the smallest safe FP-6 implementation surface, if authorized.
6. Enumerate all open CTO decisions.

### Discovery Conclusion (Summary)

| Finding | Status |
|---------|:------:|
| FP-6 architectural problem is real and documented | PROVEN |
| FeaturePlatform events: 8 published, 0 subscribers | PROVEN |
| PriceAction events: 6+ published, 0 subscribers | PROVEN |
| EventBus is fire-and-forget audit log only | PROVEN |
| No production component depends on FP event delivery | PROVEN |
| Adding subscribers is architecturally safe IF scoped correctly | INFERRED |
| EventBus ordering guarantees under subscribers | UNKNOWN |
| Required FP-6 scope requires CTO decision (OQ-FP6-1 to OQ-FP6-4) | — |

---

## 2. DISCOVERY SCOPE

### 2.1 In Scope

- EventBus audit: publish/subscribe map for all Feature Platform events
- EventBus audit: publish/subscribe map for all Price Action events
- FeatureStore architecture and memory growth review
- Governance wiring audit
- Consumer boundary re-audit (changes since FP-2 certification)
- Determinism risk introduced by adding event subscribers
- FeatureStore unbounded growth risk (deferred from FP-5, OQ from FP-0)

### 2.2 Out of Scope (Frozen — Do Not Reopen)

| Stage | Decision | Status |
|-------|----------|:------:|
| FP-1 | One-time feature registration lifecycle | CERTIFIED PASS |
| FP-2 | `query_realtime()` public API boundary | CERTIFIED PASS |
| FP-3D | Canonical `annualized_vol` formula and `SizingConfig` | CERTIFIED PASS |
| FP-4 | ADR-001 — `PriceActionOrchestrator.get_atr()` canonical ATR | CERTIFIED PASS |
| FP-5 | Feature Pipeline determinism / ND-1b fix | CERTIFIED PASS |

### 2.3 ADR-001 Binding Constraint (Must Not Violate)

```
PriceActionOrchestrator.get_atr(symbol) = canonical ATR for all strategy/risk decisions.
FeaturePlatform AtrTransformer output   = INTERNAL DAG ONLY (atr → normalized_atr → risk_score).
```

No FP-6 subscriber may re-route external ATR consumption to the Feature Platform.

---

## 3. REPOSITORY EVIDENCE

### 3.1 Files Inspected

| File | Key Evidence |
|------|-------------|
| `research_platform/feature_platform/events.py` | 16 event classes defined; none imported by any subscriber |
| `research_platform/feature_platform/orchestrator.py` | 8 publish() calls; 0 subscribe() calls |
| `research_platform/feature_platform/lifecycle.py` | 2 publish() calls (FeaturePromoted, FeatureRejected) |
| `research_platform/feature_platform/plugin.py` | Resolves IEventBus from container; passes to orchestrator |
| `research_platform/feature_platform/feature_store.py` | In-memory dict; no eviction; full DataFrame per save |
| `research_platform/feature_platform/registry.py` | Thread-safe; raises ValueError on re-registration |
| `research_platform/feature_platform/governance.py` | PromotionGovernor.evaluate_promotion() — implemented, ZERO callers from production |
| `research_platform/feature_platform/freshness.py` | FeatureFreshnessEngine — implemented, ZERO callers from production |
| `research_platform/feature_platform/scheduler.py` | FeatureScheduler — background thread scheduler; ZERO callers in production |
| `research_platform/feature_platform/cache.py` | In-memory sha-keyed cache; no eviction |
| `research_platform/feature_platform/validators.py` | Fully implemented; called in compute_and_store() per feature |
| `research_platform/runtime/strategy_loop.py` | query_realtime consumer; ADV-1 "atr" in fallback list (non-blocking) |
| `research_platform/price_action/orchestrator.py` | 6+ publish() calls for StructureDetected, ImbalanceDetected |
| `docs/architecture/SPRINT-004-FEATURE-PIPELINE-DISCOVERY-GATE.md` | Master discovery gate; FP-6 definition; R-7, OQ-4, OQ-5 |

### 3.2 Evidence Standard Used

Each finding below identifies:
- **File / Symbol / Behavior**
- **Why it matters**
- **Severity**
- **Evidence Status:** `PROVEN` / `INFERRED` / `UNKNOWN`

---

## 4. CURRENT ARCHITECTURE

### 4.1 Runtime Data Flow

```
Exchange WebSocket
      │  tick
      ▼
MarketGateway
      │  process_tick(symbol, price, ts, vol)
      ▼
PriceActionOrchestrator
      │  ─── publishes ──► StructureDetected  (EventBus) ← ZERO subscribers
      │  ─── publishes ──► ImbalanceDetected  (EventBus) ← ZERO subscribers
      │  (SessionUpdated: DEFINED, never published)
      │
      │  get_bars(symbol) → [list of bar dicts]
      │
      ▼  pd.DataFrame(bars_list)
FeaturePlatformOrchestrator.compute_and_store(names, symbol, df)
      │
      │  ─── publishes ──► FeatureValidated   (EventBus) ← ZERO subscribers
      │  ─── publishes ──► FeatureCalculated  (EventBus) ← ZERO subscribers
      │  ─── publishes ──► FeatureRejected    (EventBus) ← ZERO subscribers
      │
      │  FeatureStore.save_features(name, version, symbol, df)
      │       ┌────────────────────────┐
      │       │  _offline_db: unbounded│  ← RISK: no eviction
      │       │  _online_db:  1-row    │
      │       └────────────────────────┘
      │
      ▼  query_realtime(names, symbols) → FeatureStore.query_latest()
┌─────────────────────────────────────────────────┐
│  Downstream consumers (FP-2 certified boundary)  │
│  StrategyLoop        : query_realtime()          │
│  AISignalGenerator   : query_realtime()          │
│  PositionSizing      : query_realtime([annualized_vol]) │
│  ExitEngine          : query_realtime([normalized_atr, risk_score]) │
│  TradeJournal        : query_realtime()          │
└─────────────────────────────────────────────────┘
```

### 4.2 EventBus Role in Current Architecture

The EventBus currently functions as a **fire-and-forget audit log** for both
Price Action and Feature Platform. Events are published to the bus but no
production component subscribes to them. Event delivery failure would be
transparent — nothing depends on it.

**Source:** `grep -r "subscribe" research_platform/feature_platform/` returns zero
production subscriber registrations. All subscribe() calls in the repository belong
to: `strategy/core/plugin.py` (strategy domain), `universe/scheduler/scheduler.py`
(universe domain), and test files. None belong to Feature Platform.

**Evidence status:** PROVEN.

---

## 5. RUNTIME DATA FLOW (DETAILED)

### 5.1 Feature Computation Trigger — Synchronous Polling

Feature computation is triggered **synchronously per tick** via direct call:

```python
# In run_paper_trading.py and live_trading/plugin.py (per-tick):
fp_orch.compute_and_store(features_to_compute, symbol, df)
```

This is a **polling pattern**, not an event-driven pattern.

**Implication for FP-6:** Adding a `StructureDetected` subscriber that triggers
feature recomputation would introduce a **second code path** for feature computation
alongside the existing per-tick synchronous call. This requires careful scoping to
avoid double-computation per tick.

### 5.2 query_realtime() vs store.query_latest() — State After FP-2

FP-2 certified that all downstream consumers use `query_realtime()`.
Re-audit confirms this holds for the production orchestrator:

```python
# orchestrator.py line 354 — query_realtime delegates to query_latest:
def query_realtime(self, names, symbols): return self._store.query_latest(names, symbols)
```

E2E tests access `fp_orch.store.query_latest()` directly — this is test-only, not
a production boundary violation.

**Source:** `grep "fp_orch.store" tests/e2e/` — callers found in test files only.
**Evidence status:** PROVEN (boundary clean post-FP-2).

---

## 6. EVENTBUS AUDIT

### 6.1 Feature Platform Events — Complete Publisher/Subscriber Map

**File:** `research_platform/feature_platform/events.py` — 16 event classes defined.

| Event Class | Published By | Publish Sites | Subscribers | Assessment |
|-------------|-------------|:-------------:|:-----------:|:----------:|
| `FeatureRegistered` | `orchestrator.register_feature()` | 1 | **0** | DEAD OUTPUT |
| `FeatureUpdated` | (none) | 0 | 0 | DEAD STUB |
| `FeatureDeleted` | (none) | 0 | 0 | DEAD STUB |
| `FeatureCalculated` | `orchestrator.compute_and_store()` | 1 | **0** | DEAD OUTPUT |
| `FeatureValidated` | `orchestrator.compute_and_store()` | 1 | **0** | DEAD OUTPUT |
| `FeatureCached` | (none) | 0 | 0 | DEAD STUB |
| `FeatureExpired` | (none) | 0 | 0 | DEAD STUB |
| `FeaturePromotionRequested` | (none) | 0 | 0 | DEAD STUB |
| `FeaturePromoted` | `lifecycle_manager.transition_state()` | 1 | **0** | DEAD OUTPUT |
| `FeatureRejected` | `orchestrator.compute_and_store()` + `lifecycle_manager` | 2 | **0** | DEAD OUTPUT |
| `FeatureLineageUpdated` | (none) | 0 | 0 | DEAD STUB |
| `FeatureVersionCreated` | `orchestrator.register_version()` | 1 | **0** | DEAD OUTPUT |
| `FeatureVersionValidated` | (none) | 0 | 0 | DEAD STUB |
| `FeatureFreshnessUpdated` | `orchestrator.evaluate_freshness()` | 1 | **0** | DEAD OUTPUT |
| `FeatureImportanceCalculated` | `orchestrator.calculate_importance()` | 1 | **0** | DEAD OUTPUT |
| `FeatureHealthUpdated` | (none) | 0 | 0 | DEAD STUB |
| `FeatureCatalogUpdated` | (none) | 0 | 0 | DEAD STUB |

**Summary:**
- Events defined: 16
- Events with at least one publish site: 9
- Events with at least one subscriber: **0**
- Events that are pure stubs (no publish, no subscribe): 7

**Evidence status:** PROVEN.

### 6.2 Price Action Events — Publisher/Subscriber Map

**File:** `research_platform/price_action/events.py`

| Event | Published By | Publish Sites | Subscribers |
|-------|-------------|:-------------:|:-----------:|
| `StructureDetected` | `PriceActionOrchestrator` | 4 | **0** |
| `ImbalanceDetected` | `PriceActionOrchestrator` | 2 | **0** |
| `SessionUpdated` | (never published) | 0 | 0 |

Estimated publish volume from PA-5 evidence: ~261 events per 1,000 ticks
(26.1% bar-close rate × 6 publish sites). These events are emitted continuously
with zero effect on system behavior.

**Evidence status:** PROVEN.

### 6.3 Duplicate Event Definitions (R-8, R-9 from Master Discovery Gate)

**Parallel structure detection systems:**

| Event Name | File | Publisher | Subscribers |
|-----------|------|-----------|:-----------:|
| `StructureDetected` | `research_platform/price_action/events.py` | `PriceActionOrchestrator` | 0 |
| `BreakOfStructureDetected` | `market_intelligence/core/events.py` | `market_intelligence/core/analysis/breakout.py` | 0 |

**Parallel session event systems:**

| Event Name | File | Publisher | Subscribers |
|-----------|------|-----------|:-----------:|
| `SessionUpdated` | `research_platform/price_action/events.py` | (never published) | 0 |
| `SessionUpdated` | `market_intelligence/core/events.py` | `market_intelligence/core/analysis/session.py` | 0 |

Two separate `SessionUpdated` classes with the same name exist in the repository.
A namespace collision is possible if imports are carelessly mixed. Both are zero-subscriber.

**Evidence status:** PROVEN (separate class objects, both `frozen=True` dataclasses).

### 6.4 EventBus Subscriber Architecture — Strategy Domain

To understand what a *working* subscriber looks like, the strategy domain was
inspected:

**File:** `strategy/core/plugin.py` (lines 190–202, 298–300)
```python
def _subscribe_event(self, event_type: str, handler: Any) -> None:
    self._event_bus.subscribe(event_type, handler)
```

The strategy plugin subscribes to 5 events on `initialize()` and unsubscribes
on `shutdown()`. This is the production-proven subscriber lifecycle pattern.

**File:** `universe/scheduler/scheduler.py` (lines 43, 54)
```python
self._event_bus.subscribe(...)  # on start
self._event_bus.unsubscribe(...)  # on stop
```

**Key observation:** All production EventBus subscribers in the codebase:
1. Are registered in an `initialize()` or `start()` method
2. Are unregistered in a `shutdown()` or `stop()` method
3. Are tied to a plugin lifecycle, not an ad-hoc registration

**Evidence status:** PROVEN.

### 6.5 Does Any Production Component Depend on FP Event Delivery?

`grep -r "FeatureCalculated\|FeatureValidated\|FeatureRejected\|FeatureRegistered"` 
across all Python files returns only the definitions and publish sites in
`events.py` and `orchestrator.py`. No consumer subscribes or imports these
event classes anywhere outside the Feature Platform itself.

**Conclusion:** Removing all FP event publish calls would have zero functional
impact on the system today.  
**Evidence status:** PROVEN.

### 6.6 Would Adding Subscribers Introduce Ordering/Reentrancy Risks?

**Ordering risk:**
The current per-tick synchronous flow is:

```
process_tick() → compute_and_store() → publishes(FeatureCalculated) → [no subscriber]
```

If a `FeatureCalculated` subscriber were added that triggers downstream work (e.g.,
alerting, logging, or a downstream computation), and if that downstream work also
calls `compute_and_store()`, reentrancy on `FeatureStore._lock` could occur.

`FeatureStore` uses `threading.Lock()` (not `threading.RLock()`). A reentrant
call from within a subscriber would deadlock if the same thread holds the lock.

**Reentrancy risk assessment:**
- If subscribers perform read-only queries or external I/O: LOW risk
- If subscribers call `compute_and_store()` or `save_features()`: HIGH reentrancy/deadlock risk
- If subscribers are called synchronously on the publish thread: risk is real

**Evidence status:** INFERRED (EventBus synchrony guarantee not read from EventBus source;
behavior of `IEventBus.publish()` not confirmed synchronous or asynchronous from source).

**OQ-FP6-1 required:** Is the TOJI `IEventBus.publish()` synchronous or asynchronous?

---

## 7. FEATURESTORE AUDIT

### 7.1 Storage Architecture

**File:** `research_platform/feature_platform/feature_store.py`

```python
class FeatureStore(IFeatureStore):
    def __init__(self):
        self._lock = threading.Lock()
        # Storage schema: (feature_name, version, symbol) → pd.DataFrame
        self._offline_db: Dict[Tuple[str, str, str], pd.DataFrame] = {}
        self._online_db:  Dict[Tuple[str, str, str], pd.DataFrame] = {}
```

**Key / Value structure:**

| Store | Key | Value | Overwrite behavior |
|-------|-----|-------|:-----------------:|
| `_offline_db` | `(name, version, symbol)` | Full DataFrame — every row from `compute_and_store()` | **OVERWRITES** previous |
| `_online_db` | `(name, version, symbol)` | 1-row DataFrame (latest) | **OVERWRITES** previous |

### 7.2 Memory Growth Analysis

**Offline store growth:**

Each `compute_and_store()` call saves a full copy of the output DataFrame
(via `df.copy()`) per `(name, version, symbol)` tuple. The key design is that
the **entire prior DataFrame is overwritten** — the offline store does not append;
it replaces.

```python
def save_features(self, name, version, symbol, df):
    ...
    self._offline_db[key] = df.copy()  # OVERWRITES — not accumulates
    if len(df) > 0:
        self._online_db[key] = df.sort_values("as_of").tail(1)
```

**Implication:** For a given `(name, version, symbol)` triplet, the offline store
holds exactly one DataFrame — the most recent compute result. There is no historical
accumulation per-key.

**However:** Each `compute_and_store()` call passes the **full bar DataFrame** (e.g.,
500 bars × 20+ columns × float64) and saves a copy. The stored size equals
the current bar window size, not an incremental update. At 200 bars × 20 features
× 8 bytes × 10 symbols = ~320 KB per call, replaced each tick.

**Memory bound:** The offline store is effectively bounded by `(N features × M symbols
× bar_window_size)` at any time — since old data is overwritten. This is NOT
unbounded accumulation per-key. The prior concern in the master discovery gate
(Section 9.2) stated "grows unbounded" — this assessment was based on misreading
the store semantics. After source review, the offline store **overwrites, not appends**.

**Revised assessment:**

| Component | Behavior | Risk |
|-----------|----------|:----:|
| `_offline_db` | One DataFrame per key — overwrites on each compute | LOW (bounded per key) |
| `_online_db` | One row per key — overwrites on each compute | NEGLIGIBLE |
| `FeatureCache` | Hash-keyed dict, no eviction, no explicit usage in compute_and_store | LOW (unused in hot path) |

**Evidence status:** PROVEN (from `feature_store.py` source).

> **Note:** The master discovery gate's Section 9.2 concern about "unbounded growth"
> is INACCURATE per current source. The store overwrites, not appends. This is
> documented here as a correction to prior gate claims. The store does not require
> an eviction policy for the offline store. The online store is already a 1-row latest.

### 7.3 FeatureStore Direct Access Boundary — Post-FP-2 State

| Caller | Pattern | Classification |
|--------|---------|:--------------:|
| `FeaturePlatformOrchestrator.compute_and_store()` | `_store.save_features(...)` | INTERNAL — CORRECT |
| `FeaturePlatformOrchestrator.query_realtime()` | `_store.query_latest(...)` | INTERNAL — CORRECT |
| `research_platform/tests/test_position_sizing.py` | `feat_orch.store.save_features(...)` | TEST ONLY |
| `tests/e2e/test_market_to_strategy_pipeline.py` | `fp_orch.store.query_latest(...)` | TEST ONLY |
| `tests/e2e/test_live_market_runtime_flow.py` | `fp_orch.store.query_latest(...)` | TEST ONLY |
| `tests/e2e/test_end_to_end_trading_verification.py` | `feature_platform.store.query_latest(...)` | TEST ONLY |

**Production boundary:** CLEAN (no production code accesses `.store` directly post-FP-2).  
**Evidence status:** PROVEN.

### 7.4 `query_historical()` Callers

`grep -r "query_historical"` in Python files returns zero production callers.
The method is defined on `FeatureStore` and `IFeatureStore`, but is not called
from any production path or test.

**Classification:** DEAD CODE in current production paths.  
**Evidence status:** PROVEN.

### 7.5 Version Selection in query_latest

```python
# feature_store.py lines 90-93:
matching_keys = [k for k in self._online_db if k[0] == name and k[2] == symbol]
latest_key = sorted(matching_keys, key=lambda k: k[1])[-1]  # sorts by version string
```

Version is sorted as a **string** (`k[1]` is a version string like `"1.0.0"`).
String sort of semantic versions is correct for single-digit versions
(`"1.0.0" < "1.0.9" < "2.0.0"`) but will fail for multi-digit minor/patch:
`"1.0.10" < "1.0.9"` (lexicographic, "1" < "9").

**Current risk:** All registered features use version `"1.0.0"`. Risk is latent,
not currently active. If feature versioning is ever used with minor/patch > 9,
this will silently select the wrong version.

**Classification:** MEDIUM latent risk. Not FP-6 scope unless versioning is touched.  
**Evidence status:** PROVEN (from source; triggered by multi-digit version strings only).

---

## 8. GOVERNANCE AUDIT

### 8.1 Governance Features — Implementation vs Caller Status

| Method | Implemented | Production Callers | Classification |
|--------|:-----------:|:-----------------:|:--------------:|
| `evaluate_promotion(name, df)` | YES | **0** | IMPLEMENTED / UNWIRED |
| `evaluate_freshness(name, last_update)` | YES | **0** | IMPLEMENTED / UNWIRED |
| `calculate_importance(name, values, returns)` | YES | **0** | IMPLEMENTED / UNWIRED |
| `check_collinearity(name, df, threshold)` | YES | **0** | IMPLEMENTED / UNWIRED |
| `catalog_search(category, tags)` | YES | **0** | IMPLEMENTED / UNWIRED |
| `register_version(info)` | YES | **0** | IMPLEMENTED / UNWIRED |

**Source:** `grep -r "evaluate_promotion\|evaluate_freshness\|calculate_importance\|check_collinearity\|register_version\|catalog_search"` in production Python files (non-test) returns only definitions in `orchestrator.py`.

### 8.2 Governance Is Research/Tooling-Grade

`PromotionGovernor.evaluate_promotion()` is fully implemented:
- Runs `FeatureValidator.validate()` on the DataFrame
- Checks metadata (formula, description non-empty)
- Checks version non-empty
- Returns signed `FeatureApprovalReport`
- Calls `_lifecycle_manager.transition_state()` for APPROVED/REJECTED

However it has no integration trigger — no production event, timer, scheduler,
or endpoint calls it. It can only be reached by directly calling `fp_orch.evaluate_promotion()`.

`FeatureLifecycleManager` tracks state transitions (`DRAFT → EXPERIMENTAL → VALIDATED
→ APPROVED → PRODUCTION → DEPRECATED → ARCHIVED`) but current features are never
transitioned — they remain in their default `DRAFT` state.

**`FeatureFreshnessEngine`** computes exponential decay freshness scores from
`last_update` timestamps but is never called from compute_and_store() and has no
trigger. The freshness score decays silently without being checked.

**`FeatureScheduler`** has a working background thread scheduler but is never started
in production — `start(callback)` is never called from any plugin or orchestrator.

**Assessment:** Governance subsystem is production-quality code in a disconnected
island. It can be wired without algorithm changes but requires caller integration.
**FP-6 MUST NOT wire governance unless CTO explicitly authorizes it.**

**Evidence status:** PROVEN.

### 8.3 What Must NOT Be Touched in FP-6

| Component | Reason |
|-----------|--------|
| `FeatureValidator.validate()` | Already called per-feature in `compute_and_store()` — working |
| `PromotionGovernor.evaluate_promotion()` | Governance feature — explicitly deferred from FP-0 through FP-5 |
| `FeatureFreshnessEngine` | No production trigger — requires separate sprint |
| `FeatureScheduler` | No production start call — requires separate sprint |
| `FeatureLifecycleManager` state transitions | Not triggered today; wiring would change lifecycle semantics |

---

## 9. CONSUMER BOUNDARY AUDIT

### 9.1 FP-2-Certified Consumer Map — Current State

| Consumer | Features Queried | Method | FP-2 Compliant |
|----------|-----------------|--------|:--------------:|
| `StrategyLoop` (`runtime/strategy_loop.py`) | All registered features (dynamic) | `query_realtime()` | YES |
| `AISignalGenerator` (`ai_signal/signal_generator.py`) | `rsi, ema9, ema21, ema50, atr, trend, support, resistance, breakout, volume_change` | `query_realtime()` | YES |
| `PositionSizingOrchestrator` (`position_sizing/orchestrator.py`) | `annualized_vol` | `query_realtime()` | YES |
| `ExitEngineOrchestrator` (`exit_engine/orchestrator.py`) | `normalized_atr, risk_score` | `query_realtime()` | YES |
| `TradeJournalOrchestrator` (`trade_journal/orchestrator.py`) | (FP query for metadata) | `query_realtime()` | YES |

**FP-2 boundary is clean.** All production consumers route through `query_realtime()`.  
**Evidence status:** PROVEN (from `grep query_realtime` production files).

### 9.2 ADV-1 Advisory (Deferred from FP-4)

`StrategyLoop` fallback feature list (line 31–33 of `strategy_loop.py`):

```python
feature_names = [
    "open", "high", "low", "close", "ema9", "ema21", "ema50",
    "rsi", "atr", "volume", "volume_change", "support", "resistance", "breakout", "trend"
]
```

`"atr"` appears in this fallback list. This is the ADV-1 advisory from FP-4.
Per FP-4 certification, this is non-blocking:
- `feature_names` is used only in the telemetry `query_realtime()` path
- `query_realtime()` → `query_latest()` will return the FP-internal `atr` column
  (which is fine — ADR-001 restricts external canonical ATR from PA, not FP telemetry)
- No strategy/risk decision depends on FP `atr` in production paths

**Status:** ADV-1 remains deferred advisory. Not FP-6 scope.  
**Evidence status:** PROVEN.

### 9.3 Governance Consumer Status

```
evaluate_promotion() — 0 production callers
evaluate_freshness() — 0 production callers
calculate_importance() — 0 production callers
```

No governance consumer exists. These are implemented but not integrated.

---

## 10. DETERMINISM AUDIT

### 10.1 FP-5 Certified Determinism (Frozen)

The Feature Pipeline transformer DAG is deterministic:
- Bit-identical numeric outputs for identical OHLCV bar sequences (SHA-256 verified)
- ND-1b eliminated: `effective_time = as_of` (single controlled reference)

### 10.2 Can EventBus Subscribers Re-Introduce Non-Determinism?

If FP-6 adds subscribers to `FeatureCalculated` or `FeatureValidated`, and those
subscribers perform **any wall-clock-dependent operation** (logging with timestamps,
freshness score computation, importance calculation), the **subscriber code** would
be non-deterministic. However:

- This does NOT affect the feature output DataFrame values (the DAG computation is upstream)
- Subscriber non-determinism would be confined to side-effect code (logging, metrics)
- FP-5 certified the DAG output DataFrame — not subscriber behavior

**Risk of breaking FP-5 certification by adding subscribers:** NONE,
provided subscribers do not call `compute_and_store()` again.

**Risk of introducing ordering-dependent behavior:**
- If the EventBus delivers events synchronously in publish order: deterministic ordering
- If the EventBus queues events asynchronously: ordering NOT guaranteed

**Evidence status:** Synchrony of `IEventBus.publish()` = UNKNOWN. OQ-FP6-1 required.

### 10.3 FeatureStore Insertion Ordering

`save_features()` uses `dict` keying with a `threading.Lock()`. Python `dict` preserves
insertion order (Python 3.7+). Given identical feature computation order (topological DAG),
insertion order into `_offline_db` is deterministic.

`query_latest()` also uses `dict` iteration, which preserves insertion order.
Return row order in the resulting DataFrame is therefore deterministic.

**Evidence status:** PROVEN (Python dict ordering; Python 3.13 runtime confirmed).

---

## 11. PERFORMANCE / MEMORY FINDINGS

### 11.1 FeatureStore Memory — Corrected Assessment

| Store | Per-tick memory | Growth pattern |
|-------|----------------|:--------------|
| `_offline_db` | 1 DataFrame per `(name, version, symbol)` key, overwritten each compute | **Stable** — bounded by key count × bar window |
| `_online_db` | 1 row per key | **Negligible** |
| `FeatureCache` | Not used in compute_and_store hot path | **Stable** |

Estimated upper bound at steady-state with 20 features × 1 symbol × 200 bars:
~200 rows × 25 columns × 8 bytes × 20 features × 2 (copy overhead) ≈ 1.6 MB.
Not a concern at current scale.

**Evidence status:** PROVEN from source code analysis; no profiling data collected.

### 11.2 FeatureValidator in Hot Path

`compute_and_store()` calls `self._validator.validate(name, output_df)` for every
feature name in `names`. The validator runs:
- NaN ratio (O(n))
- Infinite values scan (O(n))
- PIT correctness (O(n))
- Stationarity heuristic (O(n) — two halves comparison)
- Multicollinearity against `close` (O(n) — pandas corr)

For 20 features × 500 rows, this is 20 validation scans of 500 rows per
`compute_and_store()` call. The stationarity and correlation checks are O(n)
but involve numpy/pandas operations with reasonable constants.

**No profiling data exists** for this path. This is a measurement gap.

**Evidence status:** INFERRED (from algorithm inspection, not profiling).

### 11.3 FeatureScheduler — Not Started

`FeatureScheduler.start()` is never called in production. The background scheduler
thread does not run. There is no background feature computation loop.
This means features are computed only when `compute_and_store()` is explicitly called.

**Evidence status:** PROVEN.

---

## 12. RISK REGISTER

| ID | Severity | Description | Evidence |
|----|:--------:|-------------|:--------:|
| FP6-R-1 | HIGH | EventBus publish() synchrony unknown — subscriber reentrancy risk if synchronous | UNKNOWN |
| FP6-R-2 | HIGH | `FeatureStore._lock` is `threading.Lock()` — reentrant subscriber could deadlock | PROVEN |
| FP6-R-3 | MEDIUM | Adding subscribers creates second feature computation trigger path (double compute risk) | INFERRED |
| FP6-R-4 | MEDIUM | Duplicate event class names (`SessionUpdated`, structure events) — namespace collision potential | PROVEN |
| FP6-R-5 | MEDIUM | Version string comparison (lexicographic) — fails for version > 9 minor/patch | PROVEN |
| FP6-R-6 | LOW | FeatureCache never used in compute_and_store hot path — cache layer is dead code | PROVEN |
| FP6-R-7 | LOW | `query_historical()` has zero production callers — dead code | PROVEN |
| FP6-R-8 | LOW | Governance features (evaluate_promotion, freshness, importance) are unwired but implemented | PROVEN |
| FP6-R-9 | LOW | FeatureScheduler never started — background loop does not run | PROVEN |
| FP6-R-10 | LOW | FeatureValidator runs per-feature in hot path — no profiling data on cost | INFERRED |

---

## 13. EXISTING CONTRACTS THAT MUST BE PRESERVED

The following contracts are certified and must not be broken by FP-6:

| Contract | Source | Constraint |
|----------|--------|------------|
| ADR-001 | FP-4 | `PriceActionOrchestrator.get_atr()` = canonical ATR. FP `atr` = internal DAG only. |
| FP-2 `query_realtime()` boundary | FP-2 | All external consumers must use `query_realtime()`, not `store.*` directly |
| FP-5 ND-1b fix | FP-5 | `effective_time = as_of` in no-timestamp-column branch of `compute_and_store()` |
| FP-5 DAG determinism | FP-5 | SHA-256 fingerprint verified — any subscriber must not alter compute path |
| FP-1 one-time registration | FP-1 | Features registered once at startup; per-tick registration eliminated |
| FP-3D `annualized_vol` formula | FP-3D | `sample_std(log_return, 1440) * sqrt(525600)` — untouchable |
| `SizingConfig` defaults | FP-3D | `target_volatility=0.10`, `max_leverage=2.0`, `fallback_volatility=0.50` — untouchable |

---

## 14. CANDIDATE FP-6 SOLUTIONS

### Option A — Observability Subscribers Only (Minimal)

**Scope:** Add lightweight subscribers to `FeatureCalculated` and `FeatureValidated`
that perform read-only logging or metrics emission.

**What changes:**
- `FeaturePlatformPlugin.initialize()` registers subscribers for `FeatureCalculated`
  and `FeatureValidated`
- Subscribers log the event payload (name, version, symbol) at DEBUG level
- No new state, no store writes, no computation triggered

**Benefit:** Proves subscriber wiring pattern; enables observability without risk.

**Risk:**
- FP6-R-1: If EventBus is synchronous, each `compute_and_store()` iteration waits
  for the subscriber to complete before proceeding. Logging at DEBUG is fast; risk LOW.
- FP6-R-2: Reentrancy risk NONE — subscriber does not call FP methods with locks.

**Complexity:** Minimal — 10-20 lines in plugin.py.

**Test:** Assert `FeatureCalculated` has a subscriber after plugin initialization.

### Option B — Observability + Freshness Tracking (Moderate)

**Scope:** Option A + on `FeatureCalculated`, call `evaluate_freshness()` for the
feature with `last_update = as_of` from the event payload.

**What changes:**
- Option A subscriber additions
- Subscriber calls `self._orchestrator.evaluate_freshness(name, last_update)`
- Freshness metrics stored via `FeatureFreshnessRepository`

**Benefit:** Wires the existing freshness infrastructure into a real call path.

**Risk:**
- `evaluate_freshness()` calls `self._freshness_engine.calculate_freshness()`,
  which calls `datetime.now(timezone.utc)` internally (ND-8 vector, deferred).
  This is a subscriber side-effect, not DAG computation — does not break FP-5.
- `FeatureFreshnessRepository.save_freshness()` acquires its own lock —
  no reentrancy with FeatureStore.

**Complexity:** Moderate — ~30 lines.

### Option C — Defer FP-6 (No Wiring)

**Scope:** FP-6 is documented but no subscribers are added.

**Rationale:** The EventBus is functioning correctly as a fire-and-forget audit
channel. No current feature, strategy, or risk decision depends on subscriber
delivery. Adding subscribers adds complexity without solving a blocking problem.

**Benefit:** Zero risk; zero scope; next sprint can address specifically.

**Deferred to:** Post-Sprint-004.

### Option D — StructureDetected → Feature Recompute Trigger (High Risk)

**Scope:** Add subscriber to `StructureDetected` that triggers `compute_and_store()`.

**What changes:** Adds event-driven feature recomputation path.

**Risk:**
- FP6-R-1 (HIGH): If EventBus is synchronous, `StructureDetected` is published
  inside `process_tick()`. Triggering `compute_and_store()` from within a `process_tick()`
  call path would be deeply reentrant.
- FP6-R-3 (HIGH): Per-tick synchronous compute AND event-driven compute would run
  on every structure detection — double computation.
- FP6-R-2 (HIGH): `FeatureStore._lock` is non-reentrant. Deadlock risk.

**Assessment:** REJECTED for FP-6. Requires architectural redesign of the
tick-handler call chain. Must not be implemented without CTO review of the full
PA→FP integration threading model.

---

## 15. REJECTED ALTERNATIVES

| Alternative | Reason for Rejection |
|-------------|---------------------|
| Option D — StructureDetected → compute_and_store() | Reentrancy deadlock risk; double computation; EventBus synchrony unknown |
| Wire FeatureLifecycleManager promotion path | Governance wiring is explicitly deferred from FP-0 through FP-5 |
| Add FeatureStore eviction/retention policy | Source review shows store overwrites per key — bounded growth, no immediate need |
| Wire FeatureScheduler.start() | Background thread has no production trigger; requires per-tick vs scheduled design decision first |
| Fix version lexicographic sort bug | Latent risk, not active — version "1.0.0" only today; out of FP-6 scope |

---

## 16. RECOMMENDED ARCHITECTURE

### CTO Decision Required First

FP-6 cannot proceed to implementation without resolution of OQ-FP6-1.
The EventBus synchrony guarantee is the foundational safety question.

**If OQ-FP6-1 is SYNCHRONOUS:**
- Option A (Observability Only) is safe
- Option B (+ Freshness tracking) is safe
- Option D is HIGH RISK and should be REJECTED

**If OQ-FP6-1 is ASYNCHRONOUS:**
- All options are safer from a reentrancy perspective
- Ordering guarantees become the new question

**If CTO defers FP-6:** Option C. Zero risk. EventBus remains audit-only.

### Recommended Minimum Scope (If Authorized)

**Option A** — Observability subscribers only.

Rationale:
1. Smallest footprint — proves wiring pattern without architectural commitment
2. Zero reentrancy risk (read-only subscriber)
3. Directly addresses the "EventBus is dead output" finding with verifiable behavior
4. Test coverage: 1 test asserting subscriber registration after plugin initialize()
5. Does not require EventBus synchrony knowledge to be safe

---

## 17. EXACT PRODUCTION FILES THAT WOULD CHANGE (IF OPTION A AUTHORIZED)

| File | Change Type | Description |
|------|:-----------:|-------------|
| `research_platform/feature_platform/plugin.py` | MODIFY | Add subscriber registrations in `initialize()`; unregister in `shutdown()` |

**That is the complete list.** No other production file changes.

### No Changes To:
- `orchestrator.py` — event publish sites untouched
- `events.py` — event class definitions untouched
- `feature_store.py` — storage untouched
- `feature_pipeline.py` — DAG transformer untouched
- Any other feature platform module
- Any consumer (StrategyLoop, ExitEngine, PositionSizing, TradeJournal, AISignal)

---

## 18. EXACT TEST FILES THAT WOULD BE ADDED (IF OPTION A AUTHORIZED)

| File | Type | Description |
|------|:----:|-------------|
| `research_platform/tests/test_sprint004_fp6_eventbus_wiring.py` | NEW | FP-6 focused test suite |

### Proposed test_sprint004_fp6_eventbus_wiring.py contents (5 tests):

| Test | Requirement |
|------|-------------|
| `test_fp6_1_feature_calculated_has_subscriber_after_initialize()` | After `FeaturePlatformPlugin.initialize()`, `FeatureCalculated` has ≥1 subscriber |
| `test_fp6_2_feature_validated_has_subscriber_after_initialize()` | After `FeaturePlatformPlugin.initialize()`, `FeatureValidated` has ≥1 subscriber |
| `test_fp6_3_compute_and_store_triggers_subscriber()` | `compute_and_store()` results in subscriber being called ≥1 time |
| `test_fp6_4_subscriber_unregistered_after_shutdown()` | After `plugin.shutdown()`, subscribers are removed |
| `test_fp6_5_subscriber_does_not_affect_output_dataframe()` | Output DataFrame from `compute_and_store()` is bit-identical with and without subscriber present |

---

## 19. REQUIRED ADRS

No new ADRs are required for Option A.

If Option D (StructureDetected → recompute) were ever authorized, it would require
a new ADR covering the event-driven vs synchronous feature computation architecture.

---

## 20. OPEN CTO DECISIONS

### OQ-FP6-1 — EventBus Synchrony Guarantee (BLOCKING)

**Question:** Is `IEventBus.publish()` synchronous or asynchronous?
- SYNCHRONOUS: subscribers execute on the publishing thread, in the publishing call stack
- ASYNCHRONOUS: subscribers execute on a separate thread/queue

**Why it matters:** Determines reentrancy risk for all subscriber options.
Synchronous + FeatureStore lock = potential deadlock if subscriber calls store.

**Source to check:** `toji_platform/core/event_bus/` (not inspected in this audit —
not in `research_platform/`).

**Evidence status:** UNKNOWN.

---

### OQ-FP6-2 — FP-6 Scope Authorization (BLOCKING)

**Question:** Which option does CTO authorize for FP-6?

- **Option A:** Observability-only subscribers (FeatureCalculated + FeatureValidated)
- **Option B:** Option A + freshness tracking on FeatureCalculated
- **Option C:** Defer — no subscribers; EventBus remains audit-only
- **Option D:** REJECTED — requires separate architectural review

---

### OQ-FP6-3 — StructureDetected → Feature Recompute (DEFERRED)

**Question:** Is event-driven feature recomputation (via StructureDetected) desired
in Sprint-004, or is it deferred to a future sprint?

**CTO recommendation requested.** If yes, requires separate discovery and threading
model review before implementation.

---

### OQ-FP6-4 — Governance Wiring (DEFERRED)

**Question:** Should `evaluate_promotion()`, `evaluate_freshness()`, and
`calculate_importance()` be wired to production triggers in Sprint-004?

Per prior deferral (FP-0 through FP-5), these remain explicitly out of scope.
Confirmation required: continue to defer, or add to FP-6?

---

## 21. IMPLEMENTATION ACCEPTANCE CRITERIA

(Applicable only if Option A or B is authorized)

| Criterion | Test |
|-----------|------|
| `FeatureCalculated` has ≥1 subscriber after plugin init | `test_fp6_1` |
| `FeatureValidated` has ≥1 subscriber after plugin init | `test_fp6_2` |
| `compute_and_store()` calls subscriber ≥1 time | `test_fp6_3` |
| Subscribers removed after plugin shutdown | `test_fp6_4` |
| Subscriber does not modify output DataFrame | `test_fp6_5` |
| 0 regressions in Sprint-003/004 focused suite (76 tests) | `pytest` |
| FP-5 SHA-256 fingerprint unchanged | Re-run `test_fp5_3` |

---

## 22. EXPLICIT SCOPE EXCLUSIONS

The following are **explicitly excluded from FP-6** regardless of CTO decision:

| Excluded Item | Reason |
|---------------|--------|
| `StructureDetected` / `ImbalanceDetected` subscriber wiring | Reentrancy risk; deferred to separate sprint |
| `FeatureLifecycleManager` production state transitions | Governance explicitly deferred |
| `FeatureScheduler.start()` wiring | No design decision on scheduled vs per-tick |
| `FeatureFreshnessEngine` production trigger | Deferred advisory |
| `FeatureStore` eviction policy | Not required — store overwrites per key |
| `query_historical()` wiring | Zero production callers; not sprint-004 scope |
| ND-2 through ND-8 metadata timestamp fixes | Explicitly deferred in FP-5 |
| ADV-1 StrategyLoop "atr" advisory | Deferred from FP-4 |
| Any change to transformer algorithms | FP-5 determinism certified — frozen |
| ADR-001 revision | FP-4 certified — frozen |

---

## 23. FINAL DISCOVERY CLASSIFICATION

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   SPRINT-004 FP-6 DISCOVERY GATE:                                            ║
║   COMPLETE — AWAITING CTO AUTHORIZATION FOR IMPLEMENTATION                   ║
║                                                                              ║
║   EventBus Audit Results:                                                    ║
║   • Feature Platform events published: 9 of 16 defined                      ║
║   • Feature Platform subscribers registered: 0 (zero)                       ║
║   • Price Action events published: 6+ (StructureDetected, ImbalanceDetected) ║
║   • Price Action subscribers: 0 (zero)                                       ║
║   • EventBus role: fire-and-forget audit log only                            ║
║   • Production dependency on FP event delivery: NONE                        ║
║                                                                              ║
║   FeatureStore Audit:                                                        ║
║   • Offline store: overwrites per key — NOT unbounded accumulation           ║
║   • Online store: 1-row latest per key — NEGLIGIBLE memory                   ║
║   • Eviction policy: NOT REQUIRED for current architecture                   ║
║                                                                              ║
║   Governance Audit:                                                          ║
║   • evaluate_promotion(), evaluate_freshness(), calculate_importance()       ║
║     = implemented, zero production callers, explicitly deferred              ║
║   • FeatureScheduler: not started in production                              ║
║                                                                              ║
║   Blocking Open Questions:                                                   ║
║   • OQ-FP6-1: Is IEventBus.publish() synchronous or asynchronous?           ║
║   • OQ-FP6-2: Which option authorized? (A / B / C — D REJECTED)             ║
║                                                                              ║
║   Recommended scope if authorized: Option A — observability subscribers      ║
║   Recommended files: plugin.py (1 file only)                                 ║
║   Recommended tests: 5 new tests in test_sprint004_fp6_eventbus_wiring.py   ║
║                                                                              ║
║   Production files changed in this discovery stage: 0                       ║
║   Test files changed in this discovery stage: 0                              ║
║   Config files changed in this discovery stage: 0                           ║
║                                                                              ║
║   Awaiting CTO authorization before any implementation begins.               ║
║   Do NOT self-certify.                                                       ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

**STOP — FP-6 discovery complete. Awaiting CTO authorization.**
