# SPRINT-004 FP-6 OQ-FP6-1 — EVENTBUS SEMANTICS RESOLUTION
## Source-Level Evidence Audit

**Author:** TOJI Senior Staff Engineer / Principal Architect  
**Date:** 2026-08-15  
**Governance:** Master Architecture Governance — Sprint 004 / FP-6 OQ-1 Resolution  
**Stage:** SOURCE AUDIT ONLY — Zero production code changes  
**Predecessor:** `SPRINT-004-FP6-DISCOVERY-GATE.md`

**Purpose:** Resolve OQ-FP6-1: *"Is IEventBus.publish() synchronous or asynchronous?"*

---

## 1. EXECUTIVE SUMMARY

**OQ-FP6-1 VERDICT: SYNCHRONOUS**

`IEventBus.publish()` as implemented by the sole production concrete class
`InMemoryEventBus` is **fully synchronous**. Subscriber handlers are called
**in registration order**, **on the publishing thread**, **before `publish()` returns**.

There is **no queue**. There is **no worker thread**. There is **no async dispatch**.
There is no `asyncio` involvement. Handlers execute in the body of the `for` loop
inside `publish()`.

Handler exceptions are **caught per-handler**, collected, and re-raised as
`EventBusError` **after all handlers have executed**. The publisher receives the
exception after `publish()` returns.

The bus uses `threading.RLock()` — a **re-entrant lock** — meaning a handler
executing on the publishing thread **can safely call `publish()` recursively**
without deadlocking on the bus lock itself.

However: `FeatureStore` uses `threading.Lock()` (non-reentrant). A handler that
calls a FeatureStore write method while the publisher holds a FeatureStore lock
**will deadlock**. Since the current publish() call path does NOT hold the
FeatureStore lock during dispatch, this risk is only relevant if a reentrant
`compute_and_store()` or `save_features()` call is triggered from within a handler.

**FP6-R-1 status: RESOLVED — SYNCHRONOUS.**

---

## 2. EVENTBUS IMPLEMENTATION LOCATION

**Sole production implementation:**

| Artifact | Path | Type |
|----------|------|------|
| `IEventBus` (interface) | `toji_platform/core/event_bus/interfaces.py:42` | ABC |
| `InMemoryEventBus` (concrete) | `toji_platform/core/event_bus/bus.py:33` | Concrete class |
| `BaseEvent` (event base class) | `toji_platform/core/event_bus/events.py:18` | Frozen dataclass |
| `EventBusBootloader` | `research_platform/platform/eventbus_boot.py:9` | Factory — returns `InMemoryEventBus()` |
| EventBus package `__init__` | `toji_platform/core/event_bus/__init__.py` | Exports `InMemoryEventBus` as default |
| README | `toji_platform/core/event_bus/README.md:19` | Documents: *"synchronous, single-process bus"* |

**No other concrete implementation exists in the repository.**

A Redis Pub/Sub implementation is mentioned in the module docstring of `bus.py`
(line 4–6) as a future swap-in possibility, but **it does not exist** — it is
purely a design note.

**Evidence status: PROVEN.**

---

## 3. IEVENTBUS INTERFACE

**File:** `toji_platform/core/event_bus/interfaces.py`

```python
# Line 30-31
EventHandler = Callable[[IEvent], None]
"""Signature for synchronous event handlers."""   # ← explicitly "synchronous"

# Line 42-74
class IEventBus(abc.ABC):
    """Central publish/subscribe bus for the Toji kernel."""

    @abc.abstractmethod
    def publish(self, event: IEvent) -> None:
        """Broadcast *event* to all matching subscribers."""

    @abc.abstractmethod
    def subscribe(self, event_type: str, handler: EventHandler | IEventHandler) -> None:
        """Register *handler* for events of *event_type*.
        Use '*' as event_type to receive ALL events."""

    @abc.abstractmethod
    def unsubscribe(self, event_type: str, handler: EventHandler | IEventHandler) -> None:
        """Remove a previously registered handler."""

    @abc.abstractmethod
    def has_subscribers(self, event_type: str) -> bool:

    @abc.abstractmethod
    def clear(self) -> None:
```

**Key interface-level evidence:**
- `EventHandler` type alias is explicitly docstring-annotated: `"Signature for synchronous event handlers."` (line 31)
- The interface returns `None` — no `Future`, no `Task`, no `Coroutine`
- No `async def` anywhere in the interface

**Evidence status: PROVEN — interface explicitly declares synchronous handlers.**

---

## 4. CONCRETE EVENTBUS IMPLEMENTATION — FULL ANALYSIS

**File:** `toji_platform/core/event_bus/bus.py`
**Class:** `InMemoryEventBus(IEventBus)` — lines 33–170
**Docstring line 38:** *"Handlers are called synchronously in registration order."*

### 4.1 Internal Data Structures

```python
# Lines 41-46
def __init__(self) -> None:
    self._handlers: dict[str, list[_NormHandler]] = defaultdict(list)
    self._timeline: deque[dict[str, Any]] = deque(maxlen=100)
    import threading
    self._lock = threading.RLock()           # ← RLock (RE-ENTRANT)
    self.exception_count = 0
```

| Field | Type | Purpose |
|-------|------|---------|
| `_handlers` | `dict[str, list[callable]]` | Subscribers keyed by event_type; ordered list per type |
| `_timeline` | `deque(maxlen=100)` | Last 100 dispatch audit records |
| `_lock` | `threading.RLock()` | Guards `_handlers` and `_timeline` mutations |

**Critical observation: `threading.RLock()` not `threading.Lock()`.**
RLock allows the same thread to acquire the lock multiple times. A handler
executing on the publishing thread that calls `publish()` recursively will
**not deadlock on this lock**.

**Evidence status: PROVEN.**

---

## 5. PUBLISH() EXECUTION TRACE

**File:** `toji_platform/core/event_bus/bus.py`, lines 57–121

```python
def publish(self, event: IEvent) -> None:
    event_type = event.event_type

    # Step 1: Snapshot handlers under lock — O(n) copy
    with self._lock:
        handlers = list(self._handlers.get(event_type, []))
        handlers.extend(self._handlers.get(_WILDCARD, []))

    # Step 2: Dispatch SYNCHRONOUSLY — no queue, no thread
    start_time = time.perf_counter()
    errors = []
    for handler in handlers:            # ← sequential, registration order
        try:
            handler(event)              # ← BLOCKS on this thread until handler returns
        except Exception as exc:
            self.exception_count += 1
            logger.error(...)
            errors.append(exc)          # ← collects, does NOT re-raise here

    # Step 3: Record to timeline (under lock)
    latency_ms = (time.perf_counter() - start_time) * 1000.0
    with self._lock:
        self._timeline.append({...})

    # Step 4: Re-raise collected errors AFTER all handlers have run
    if errors:
        if len(errors) == 1:
            raise EventBusError(...) from errors[0]
        else:
            raise EventBusError(...)
```

### Step-by-Step Analysis

| Step | What Happens | Thread |
|------|-------------|--------|
| Lock acquired | `_handlers` dict is snapshot-copied into local `handlers` list | Publishing thread |
| Lock released | After copy — handlers run OUTSIDE the lock | Publishing thread |
| `handler(event)` | Called synchronously, one at a time | Publishing thread |
| Exception caught | Logged; appended to `errors`; loop CONTINUES | Publishing thread |
| Timeline written | Under lock; after all handlers complete | Publishing thread |
| Errors re-raised | `EventBusError` raised after ALL handlers ran | Publishing thread |

**Critical behavior:** The lock is released BEFORE handlers are called.
Handlers execute outside the RLock critical section. This means:
- Handlers can call `publish()` again without acquiring the RLock twice
  (the RLock would allow it anyway)
- Handlers cannot be pre-empted by concurrent subscribe/unsubscribe
  (the snapshot approach ensures a stable handler list for this dispatch)

**Evidence status: PROVEN from source.**

---

## 6. SUBSCRIBE() EXECUTION TRACE

**File:** `toji_platform/core/event_bus/bus.py`, lines 128–139

```python
def subscribe(self, event_type: str, handler: EventHandler | IEventHandler) -> None:
    normalised = self._normalise(handler)
    with self._lock:
        if normalised not in self._handlers[event_type]:
            self._handlers[event_type].append(normalised)   # ← appends to list
        else:
            logger.debug("InMemoryEventBus: Handler already registered to '%s'", event_type)
    logger.debug("Subscribed handler to '%s'", event_type)
```

**Key behaviors:**
- Handler appended to list (preserves registration order)
- Duplicate check: same handler registered twice → silently ignored (idempotent)
- Lock held only during list mutation — not during any callback
- **Class-based `IEventHandler` is normalized** to `handler.handle` bare callable via `_normalise()`

**Evidence status: PROVEN.**

---

## 7. UNSUBSCRIBE() EXECUTION TRACE

**File:** `toji_platform/core/event_bus/bus.py`, lines 142–159

```python
def unsubscribe(self, event_type: str, handler: EventHandler | IEventHandler) -> None:
    normalised = self._normalise(handler)
    with self._lock:
        if event_type in self._handlers:
            handlers = self._handlers[event_type]
            try:
                handlers.remove(normalised)
            except ValueError:
                logger.warning("Handler not found for event type '%s'", event_type)
            if not handlers:
                del self._handlers[event_type]   # ← cleans up empty lists
```

**Key behaviors:**
- Unsubscribing a handler not registered → `ValueError` caught, `logger.warning` emitted — **does NOT raise**
- Empty list after removal → key deleted from `_handlers` dict (clean)
- Safe to call from `shutdown()` — does not affect in-flight dispatches

**Thread safety with concurrent publish:** If `publish()` is mid-dispatch when
`unsubscribe()` is called on another thread:
- `publish()` already holds a snapshot copy of handlers (taken under lock before dispatch)
- `unsubscribe()` modifies `_handlers` under its own lock
- The in-flight dispatch loop uses the snapshot — the unsubscribed handler **will still run
  for the current dispatch** but will not run for subsequent ones

This is the standard snapshot/copy-on-dispatch pattern. Safe, no data corruption.

**Evidence status: PROVEN.**

---

## 8. THREADING MODEL

### 8.1 Summary

| Property | Value | Evidence |
|----------|-------|----------|
| Dispatch thread | **Publishing thread (caller's thread)** | `handler(event)` called in-line in `publish()` |
| Worker thread | **None** | No `threading.Thread` in `bus.py` |
| Thread pool | **None** | No `concurrent.futures` |
| Asyncio | **None** | No `async def`, no `asyncio.create_task()` |
| Queue | **None** | No `queue.Queue` or `asyncio.Queue` |
| Lock type | `threading.RLock()` | Line 45 of `bus.py` — **re-entrant** |

### 8.2 Multi-Thread Safety

The `InMemoryEventBus` is thread-safe for concurrent `subscribe()` / `unsubscribe()`
and `publish()` calls across different threads, with the snapshot-copy approach
ensuring dispatch list stability per publish invocation.

**However:** If thread A is in the middle of a `publish()` dispatch loop and
thread B calls `publish()` for the same or different event type, both sets of
handlers execute on their respective caller threads concurrently. No global
serialization of handler execution exists.

**In the TOJI research platform runtime:** The per-tick call path is single-threaded
(tick handler → `process_tick()` → `compute_and_store()` → `publish()`). There
is no concurrent producer of FP events in the current production architecture.

**Evidence status: PROVEN (bus source); PROVEN (single-threaded tick path).**

---

## 9. QUEUE / WORKER MODEL

There is no queue. There is no worker thread or thread pool. Confirmed by full
inspection of `toji_platform/core/event_bus/bus.py`:

```
Imports in bus.py:
  import time
  import logging
  from collections import defaultdict, deque
  from datetime import datetime, timezone
  from typing import Callable, Any
  from toji_platform.core.errors import EventBusError
  from toji_platform.core.event_bus.interfaces import EventHandler, IEvent, IEventBus, IEventHandler
  (+ import threading inside __init__)
```

**No `queue`, `asyncio`, `concurrent.futures`, `multiprocessing`, or `threading.Thread`
at module level.** `threading` is imported only for `threading.RLock()`.

The `deque(maxlen=100)` (`_timeline`) is a ring buffer for audit purposes only —
not a dispatch queue. Events are never enqueued for later delivery.

**Evidence status: PROVEN.**

---

## 10. ORDERING GUARANTEES

| Guarantee | Status |
|-----------|--------|
| Handlers called in registration order (per event_type list) | **GUARANTEED** — list preserves insertion order |
| Type-specific handlers called BEFORE wildcard handlers | **GUARANTEED** — `handlers.extend(wildcards)` appended after |
| Handler A finishes before handler B starts | **GUARANTEED** — sequential `for` loop |
| Event 1 dispatch completes before event 2 dispatch starts (same thread) | **GUARANTEED** — synchronous call chain |
| Event ordering across threads | **NOT GUARANTEED** — each publishing thread runs independently |

**Evidence status: PROVEN.**

---

## 11. EXCEPTION SEMANTICS

**File:** `toji_platform/core/event_bus/bus.py`, lines 66–121

```python
errors = []
for handler in handlers:
    try:
        handler(event)
    except Exception as exc:
        self.exception_count += 1
        logger.error("Handler %s failed for event %s: %s", handler, event_type, exc)
        errors.append(exc)       # ← collected, NOT re-raised immediately

# ... timeline write ...

if errors:
    if len(errors) == 1:
        raise EventBusError(f"Handler failed for {event_type}: {errors[0]}") from errors[0]
    else:
        raise EventBusError(f"Multiple handlers failed for {event_type}: {errors}")
```

### Exception Behavior Summary

| Scenario | Behavior |
|----------|----------|
| Handler A raises exception | Exception caught, logged, appended to `errors`; **Handler B still runs** |
| All handlers run regardless of failures | YES — exception in handler N does not skip handler N+1 |
| `publish()` raises `EventBusError` | **YES — after ALL handlers complete**, if any raised |
| `EventBusError` chained from original | YES — single exception: `from errors[0]` |
| Publisher receives exception | YES — `EventBusError` propagates to `publish()` caller |
| `exception_count` incremented | YES — one increment per failed handler |

**Critical implication for FP-6:** If a `FeatureCalculated` subscriber raises an
exception (e.g., logging failure, network error), `compute_and_store()` will
receive an `EventBusError` from `publish()`. Unless `compute_and_store()` wraps
the `publish()` call in a `try/except`, the exception will propagate up through
the per-tick call stack, potentially aborting the tick processing.

**Current state of production `compute_and_store()` publish calls:**

```python
# orchestrator.py lines 317-324:
self._event_bus.publish(FeatureValidated(payload={...}))   # NO try/except
# orchestrator.py lines 330-333:
self._event_bus.publish(FeatureCalculated(payload={...})) # NO try/except
```

Neither publish call in `compute_and_store()` is wrapped in `try/except`.
If a subscriber raises, `EventBusError` will propagate up through
`compute_and_store()` and potentially abort the per-tick processing.

**Evidence status: PROVEN. This is a material constraint for FP-6 Option A.**

---

## 12. REENTRANCY SEMANTICS

### 12.1 EventBus Lock — RLock (Reentrant)

```python
# bus.py line 45
self._lock = threading.RLock()
```

`threading.RLock` allows the **same thread** to acquire the lock multiple times.
Combined with the snapshot pattern (handlers copied under lock, then lock released
before dispatch), a handler calling `publish()` from within a handler will:

1. Enter `publish()` on the same thread
2. Attempt `with self._lock` → **succeeds** (same thread; RLock allows reentry)
3. Take a snapshot of handlers for the nested event
4. Release lock
5. Dispatch nested handlers

This is **safe** — no deadlock at the EventBus level.

**Evidence status: PROVEN.**

### 12.2 FeatureStore Lock — Non-Reentrant Lock

```python
# feature_store.py lines 15-17
import threading
self._lock = threading.Lock()  # ← NON-REENTRANT
```

`threading.Lock()` is **NOT** reentrant. If the same thread attempts to acquire
it twice, it will **deadlock**.

**Current call chain for `publish()` in `compute_and_store()`:**

```
compute_and_store()
    ├── self._store.save_features(...)
    │       └── with self._lock: ...   ← FeatureStore lock ACQUIRED, then RELEASED
    │                                    (save_features completes before publish)
    └── self._event_bus.publish(FeatureCalculated(...))
                                       ← FeatureStore lock NOT held at this point
```

**Source evidence:** In `orchestrator.py`, `save_features()` is called (line 329)
and **completes before** `publish(FeatureCalculated)` (line 330). The FeatureStore
lock is **not held** when `publish()` is called.

**Therefore:** A `FeatureCalculated` subscriber that calls `query_realtime()`
(which calls `query_latest()` on the store) will:
1. Enter `query_latest()`
2. Attempt `with self._lock` on FeatureStore → **succeeds** (lock not held by publisher)

A `FeatureCalculated` subscriber that calls `save_features()` directly will:
1. Enter `save_features()`
2. Attempt `with self._lock` on FeatureStore → **succeeds** (lock not held by publisher)

**Reentrancy deadlock risk ONLY applies if:**
- The publisher holds the FeatureStore lock AND
- A subscriber tries to acquire the same FeatureStore lock on the same thread

Given the current `compute_and_store()` structure, this condition does **NOT** exist.
The lock is acquired and released within `save_features()`, then `publish()` is called
after `save_features()` returns.

**FP6-R-2 (FeatureStore non-reentrant lock risk): RESOLVED — NO DEADLOCK RISK
under current call structure.**

**Evidence status: PROVEN from source analysis of `compute_and_store()` call order.**

---

## 13. EXISTING SUBSCRIBER BEHAVIOR

### 13.1 Strategy Plugin (`strategy/core/plugin.py`)

**Subscriber lifecycle:**

```
initialize() called
    └── _subscribe_event("system.market_state_updated", self._on_market_state_updated)
    └── _subscribe_event("system.pattern_updated", self._on_pattern_updated)
    └── _subscribe_event("system.pattern_quality_updated", self._on_pattern_quality_updated)
    └── _subscribe_event("system.confluence_updated", self._on_confluence_updated)
    └── _subscribe_event("system.confluence_completed", self._on_confluence_completed)

publish("system.market_state_updated", event)
    └── [synchronous, on publishing thread]
         └── _on_market_state_updated(event)
              └── _process_event_state(event)
                   └── self._orchestrator.process_strategy(symbol, timeframe)  ← substantial work
                   └── self._new_strategy_engine.execute_all([scan])            ← shadow mode

shutdown() called
    └── self._event_bus.unsubscribe(event_type, handler) for each in _active_subscriptions
```

**Observation:** Strategy plugin handlers perform **substantial synchronous work**
(strategy evaluation, shadow engine execution) inside the handler body — all on the
publishing thread. This is the established pattern for real handlers in this codebase.

**Evidence status: PROVEN.**

### 13.2 Universe Scheduler (`universe/scheduler/scheduler.py`)

```
start() called
    └── self._event_bus.subscribe("system.scheduler_tick", self._on_tick)

publish("system.scheduler_tick", event)
    └── [synchronous, on publishing thread]
         └── _on_tick(event)
              └── datetime.now(UTC)          ← wall-clock call (non-deterministic)
              └── self._execute_scan()
                   └── self._scan_callback() ← full universe scan

stop() called
    └── self._event_bus.unsubscribe("system.scheduler_tick", self._on_tick)
```

**Observation:** Universe scheduler handler calls `self._scan_callback()` — a full
universe scan — synchronously on the publishing thread inside the handler.

**Evidence status: PROVEN.**

---

## 14. FP6-R-1 RESOLUTION

**Finding from FP-6 Discovery Gate:** "EventBus publish() synchrony unknown — subscriber
reentrancy risk if synchronous."

**Resolution:**

`IEventBus.publish()` is **SYNCHRONOUS**. Handlers execute on the publishing thread
before `publish()` returns.

**Prior status:** `UNKNOWN`  
**Resolved status:** `PROVEN — SYNCHRONOUS`

**Implications:**
1. Subscribers added by FP-6 will execute on the per-tick call thread
2. Handlers must return promptly to avoid tick processing latency
3. Handler exceptions will propagate as `EventBusError` to `compute_and_store()`
   callers unless guarded

---

## 15. FP6-R-2 IMPACT — FEATURESTORE NON-REENTRANT LOCK

**Finding from FP-6 Discovery Gate:** "`FeatureStore._lock` is `threading.Lock()` —
reentrant subscriber could deadlock."

**Revised assessment after source analysis:**

The FeatureStore lock is **not held when `publish()` is called** in `compute_and_store()`.
The call sequence is:

```
save_features()  → acquires FeatureStore lock → saves → releases lock
publish()        → calls handlers              ← FeatureStore lock is FREE at this point
```

A subscriber calling `query_realtime()` or `save_features()` will successfully
acquire the FeatureStore lock — **no deadlock**.

**Deadlock would only occur if:**
- `compute_and_store()` were restructured to hold the FeatureStore lock across the
  `publish()` call (it does not do this)
- OR a subscriber called `compute_and_store()` which then called `save_features()`
  which then tried to acquire FeatureStore lock while the outer handler held it

For the current code structure: **NO DEADLOCK RISK.**

**Prior status:** `HIGH risk (INFERRED)`  
**Revised status:** `LOW risk (PROVEN — no deadlock under current call structure)`

---

## 16. FP6-R-3 IMPACT — DOUBLE COMPUTATION

**Finding from FP-6 Discovery Gate:** "Adding subscribers creates second feature
computation trigger path (double compute risk)."

**Revised assessment:**

This risk is only relevant for **Option D** (StructureDetected → compute_and_store).
For **Option A** (observability-only subscribers to FeatureCalculated/FeatureValidated):
- The subscriber fires AFTER `compute_and_store()` has already completed
- The subscriber performs logging only — no computation triggered
- No second computation path is created

**For Option A: FP6-R-3 does NOT apply.**  
**For Option D: FP6-R-3 remains a HIGH risk.**

**Prior status:** `MEDIUM risk (INFERRED)`  
**Revised status (Option A):** `NOT APPLICABLE (PROVEN)`  
**Revised status (Option D):** `HIGH risk (PROVEN)`

---

## 17. OPTION A SAFETY ANALYSIS

**Option A:** Add `FeatureCalculated` and `FeatureValidated` subscribers in
`FeaturePlatformPlugin.initialize()` that perform DEBUG logging only.

### Handler Safety Classification

| Hypothetical Handler | Classification | Reasoning |
|----------------------|:--------------:|-----------|
| `FeatureCalculated` → `logger.debug(...)` only | **SAFE** | No locks acquired; no FP methods called; near-zero latency |
| `FeatureValidated` → `logger.debug(...)` only | **SAFE** | Same as above |
| `FeatureCalculated` → read-only metrics (counter increment) | **SAFE** | Atomic read; no FP lock contention |
| `FeatureCalculated` → `compute_and_store()` | **UNSAFE** | Triggers recomputation on same tick; double computation; potential reentrancy chain |
| `FeatureCalculated` → `save_features()` | **SAFE WITH CONSTRAINTS** | FeatureStore lock is free at publish time; but direct write bypasses orchestrator |
| `FeatureCalculated` → `query_realtime()` | **SAFE** | FeatureStore lock is free; read-only; adds latency on tick thread |

### Option A End-to-End Safety Verification

**Call chain with Option A subscriber:**

```
process_tick()
    └── compute_and_store(names, symbol, df)
         ├── _pipeline.compute(...)
         ├── _validator.validate(...)
         ├── _store.save_features(...)          ← FeatureStore lock acquired + released
         └── _event_bus.publish(FeatureCalculated)
              └── [SYNCHRONOUS on this thread]
                   └── fp_plugin._on_feature_calculated(event)
                        └── logger.debug(       ← FAST, no locks
                             "FeatureCalculated: %s", event.payload)
              [returns]
         ← publish() returns None (no error from DEBUG-only handler)
    ← compute_and_store() returns output_df
```

**Latency impact:** `logger.debug()` is effectively a no-op when DEBUG logging is
disabled (which it is in production). Logger level check is O(1).
**Estimated added latency per publish: <1 μs.**

**Exception safety:** `logger.debug()` does not raise under normal conditions.
If the logging system itself fails, the exception would be caught by the EventBus
and re-raised as `EventBusError` to `compute_and_store()`. This is a negligible
risk in practice but is **not guarded by `compute_and_store()` currently**.

**Recommendation for Option A implementation:** Wrap publish calls in `compute_and_store()`
with `try/except EventBusError` to prevent subscriber failures from aborting tick processing.
This is a one-line addition per publish site and should be part of the FP-6 implementation
if subscribers are added.

**Option A overall verdict: SAFE.** The DEBUG-logging subscriber poses no reentrancy,
deadlock, double-computation, or ordering risk.

---

## 18. OPTION B SAFETY ANALYSIS

**Option B:** Option A + on `FeatureCalculated`, call
`orchestrator.evaluate_freshness(name, last_update)`.

**`evaluate_freshness()` source** (`orchestrator.py` lines 356-363):
```python
def evaluate_freshness(self, name: str, last_update: datetime) -> FeatureFreshnessMetrics:
    metrics = self._freshness_engine.calculate_freshness(name, last_update)
    self._freshness_repo.save_freshness(metrics)
    self._event_bus.publish(
        FeatureFreshnessUpdated(payload={...})
    )
    return metrics
```

**`evaluate_freshness()` calls `publish(FeatureFreshnessUpdated)`.**

**Recursive publish chain with Option B:**

```
compute_and_store()
    └── publish(FeatureCalculated)
         └── handler: evaluate_freshness()
              └── publish(FeatureFreshnessUpdated)  ← nested publish
                   └── [no subscriber for FeatureFreshnessUpdated currently]
                       → publish() returns immediately
```

Since `FeatureFreshnessUpdated` currently has zero subscribers, the nested publish
is a no-op. This is safe today. However:

1. `evaluate_freshness()` calls `self._freshness_repo.save_freshness(metrics)` which
   acquires `FeatureFreshnessRepository._lock`. This lock is separate from `FeatureStore._lock`
   — no contention.

2. `evaluate_freshness()` calls `datetime.now(timezone.utc)` via `calculate_freshness()`
   — this is a wall-clock call (ND-8, deferred advisory). It does not affect DAG output.

3. The nested `publish(FeatureFreshnessUpdated)` uses the same synchronous bus.
   Since no subscriber exists for it, the for-loop in publish() is empty and returns
   immediately.

4. RLock allows the reentrant `with self._lock` in the nested publish snapshot.

**Option B verdict: SAFE WITH CONSTRAINTS.** Safe today (zero FeatureFreshnessUpdated
subscribers). Would require re-evaluation if `FeatureFreshnessUpdated` ever gains
subscribers. Each `FeatureCalculated` event (one per feature name in `names`) triggers
one `evaluate_freshness()` call — at 20 features per `compute_and_store()` call, this
is 20 additional repository writes per tick. Latency is measurable.

---

## 19. OPTION C — DEFER

**Option C:** No subscribers added. EventBus remains fire-and-forget audit log.

**Safety verdict: ZERO RISK.**

No production change. No new failure modes. No implementation required.

Rationale: The EventBus is fully functional as-is. No current business requirement
depends on subscriber delivery of Feature Platform events. Deferral has no system
impact.

---

## 20. OPTION D REJECTION — CONFIRMED

**Option D:** Subscribe to `StructureDetected` → trigger `compute_and_store()`.

**StructureDetected is published inside `process_tick()` via `PriceActionOrchestrator`.**

**Trace:**

```
process_tick(symbol, price, ts, vol)
    └── [detect swing] → publish(StructureDetected)
         └── [Option D handler: compute_and_store(names, symbol, df)]
              └── save_features()         ← requires bars_list → df construction
              └── publish(FeatureCalculated)
                   └── [possibly more handlers...]
```

**Problems:**

1. **`df` (bar DataFrame) not available inside the subscriber.** The subscriber
   receives only the `StructureDetected` event payload. The bar DataFrame must be
   reconstructed from `pa_orch.get_bars(symbol)` — this is a full O(n) rebuild.

2. **Double computation.** The per-tick synchronous flow already calls
   `compute_and_store()` after every `process_tick()`. Adding a `StructureDetected`
   subscriber would trigger a SECOND `compute_and_store()` on structure-detected ticks
   (~26% of ticks based on PA-5 data). Features would be computed twice on those ticks.

3. **Stack depth.** The call stack becomes:
   `process_tick()` → `publish()` → handler → `compute_and_store()` → `publish()` →
   potentially more handlers. This is a deep synchronous call chain on the tick thread.

4. **Not needed.** Features are already computed synchronously after every tick.
   Structure detection events add no new information about whether features need recomputing.

**Option D rejection confirmed: REJECTED — double computation, missing DataFrame context,
excessive stack depth.**

**Evidence status: PROVEN.**

---

## 21. CTO RECOMMENDATION

### Primary Recommendation: **Option A**

**Rationale from source evidence:**

1. `InMemoryEventBus` is synchronous — handlers execute on the publishing thread.
   This is safe for logging-only handlers.
2. FP6-R-1 (synchrony unknown) is **RESOLVED** — SYNCHRONOUS, well-documented.
3. FP6-R-2 (FeatureStore deadlock) is **RESOLVED** — NO DEADLOCK RISK under current structure.
4. The EventBus `_lock` is `threading.RLock()` — safe for reentrant publish calls.
5. Handler exceptions are collected and re-raised as `EventBusError` — publish call
   sites in `compute_and_store()` should be wrapped in `try/except` as part of the
   FP-6 implementation.
6. `FeaturePlatformPlugin.initialize()` already resolves `IEventBus` from the container
   (line 46 of `plugin.py`) — no new wiring infrastructure needed.
7. Only 1 production file changes: `plugin.py`.
8. Test footprint: 5 new tests.

### Option A — Exact Implementation Safety Contract

| Item | Verified Safe |
|------|:------------:|
| Handler body: `logger.debug(...)` only | YES |
| FeatureStore lock contention | NONE |
| EventBus lock deadlock | NONE (RLock + snapshot pattern) |
| Double computation | NONE (observability-only handler) |
| Reentrancy | NONE (no FP methods called from handler) |
| Exception propagation risk | LOW — mitigated by wrapping publish() in try/except |
| Tick latency impact | NEGLIGIBLE (<1 μs at DEBUG-disabled level) |

### Required Addition to FP-6 Option A Scope

**One additional constraint** identified by this audit:

The current `publish()` calls in `compute_and_store()` are not wrapped in
`try/except`. Once real subscribers exist, a subscriber failure will raise
`EventBusError` from `publish()`, which will propagate up through
`compute_and_store()` and abort tick processing.

**Required defensive guard (if Option A is authorized):**

```python
# In orchestrator.py compute_and_store() — wrap each publish:
try:
    self._event_bus.publish(FeatureCalculated(payload={...}))
except EventBusError as exc:
    logger.warning("FeatureCalculated publish failed: %s", exc)
```

**This is a minor defensive addition to `orchestrator.py`** (2 try/except wrappers),
not an algorithm change. It should be authorized as part of Option A if Option A
is approved.

> [!IMPORTANT]
> This changes `orchestrator.py` in addition to `plugin.py`. The FP-6 file
> change list must be updated if Option A is authorized:
> - `plugin.py` — subscriber registration/deregistration
> - `orchestrator.py` — defensive try/except around publish calls (2 sites)

---

## 22. EVIDENCE CLASSIFICATION SUMMARY

### Q1–Q14 Answers

| Q | Question | Answer | Evidence |
|---|----------|--------|:--------:|
| Q1 | Does publish() invoke handlers before returning? | **YES** — synchronous in-line dispatch | PROVEN |
| Q2 | What thread executes handlers? | **Publishing thread (caller's thread)** | PROVEN |
| Q3 | Is there a queue? | **NO** | PROVEN |
| Q4 | Is there a worker thread? | **NO** | PROVEN |
| Q5 | Is execution ordered? | **YES** — registration order | PROVEN |
| Q6 | Handlers sequential or concurrent? | **SEQUENTIAL** | PROVEN |
| Q7 | What if one handler raises? | Exception caught, logged, collected; loop continues; all handlers run; EventBusError raised after last handler | PROVEN |
| Q8 | Does publish() propagate handler exceptions to publisher? | **YES** — as `EventBusError` after ALL handlers complete | PROVEN |
| Q9 | Can a handler publish recursively? | **YES** — RLock allows reentry; snapshot prevents deadlock | PROVEN |
| Q10 | Can a handler call back into FeatureStore? | **YES** — FeatureStore lock is free when publish() is called | PROVEN |
| Q11 | Does subscribe() preserve registration order? | **YES** — list.append() | PROVEN |
| Q12 | Does unsubscribe() safely remove handlers during publishing? | **YES** — snapshot pattern; in-flight dispatch unaffected | PROVEN |
| Q13 | Are there locks around subscriber dispatch? | **NO** — lock released before dispatch; handlers run without lock | PROVEN |
| Q14 | Is EventBus lifecycle-controlled by plugin/container? | **YES** — `EventBusBootloader` creates singleton; plugins resolve from container | PROVEN |

### Risk Register Revision

| Risk | Original Status | Revised Status | Evidence |
|------|:---------------:|:--------------:|:--------:|
| FP6-R-1 EventBus synchrony unknown | UNKNOWN | **RESOLVED — SYNCHRONOUS** | PROVEN |
| FP6-R-2 FeatureStore non-reentrant lock | HIGH (INFERRED) | **LOW — NO DEADLOCK UNDER CURRENT CALL STRUCTURE** | PROVEN |
| FP6-R-3 Double computation | MEDIUM (INFERRED) | **NOT APPLICABLE for Option A; HIGH for Option D** | PROVEN |
| FP6-R-4 Duplicate event class names | MEDIUM (PROVEN) | **UNCHANGED — latent risk; out of FP-6 scope** | PROVEN |

### New Finding

| Finding | Severity | Description | Evidence |
|---------|:--------:|-------------|:--------:|
| FP6-N-1 | MEDIUM | `compute_and_store()` publish calls are unguarded — subscriber failure aborts tick processing | PROVEN |

---

## 23. VERIFICATION

```
git status --short
```

Result: `fatal: not a git repository`

**No git repository present. File-level verification used instead.**

**Files modified by this audit:**

| File | Type | Change |
|------|:----:|--------|
| `docs/architecture/SPRINT-004-FP6-OQ1-EVENTBUS-SEMANTICS.md` | NEW | This document |

**Production Python files modified:** 0  
**Test files modified:** 0  
**Configuration files modified:** 0  
**Documentation files created:** 1

---

## 24. FINAL CLASSIFICATION

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   OQ-FP6-1 RESOLUTION:                                                       ║
║                                                                              ║
║   InMemoryEventBus.publish() is SYNCHRONOUS.                                 ║
║   Handlers execute on the publishing thread, in registration order,          ║
║   before publish() returns.                                                  ║
║   No queue. No worker thread. No async.                                      ║
║                                                                              ║
║   Bus lock: threading.RLock() — RE-ENTRANT.                                  ║
║   FeatureStore lock: threading.Lock() — NON-REENTRANT.                       ║
║   Deadlock risk for Option A: NONE (FeatureStore lock free at publish time). ║
║                                                                              ║
║   Option A (observability only): SAFE.                                       ║
║   Option B (+ freshness):        SAFE WITH CONSTRAINTS.                      ║
║   Option C (defer):              ZERO RISK.                                  ║
║   Option D (StructureDetected):  REJECTED — double compute, missing context. ║
║                                                                              ║
║   New finding: compute_and_store() publish calls are unguarded.              ║
║   Recommended addition to FP-6 Option A scope:                               ║
║   Wrap publish() sites in orchestrator.py with try/except EventBusError.     ║
║   This adds orchestrator.py to the Option A change list.                     ║
║                                                                              ║
║   Production Python files modified in this audit: 0                         ║
║   Test files modified in this audit: 0                                       ║
║   Documentation files created: 1                                             ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

**STOP — OQ-FP6-1 resolved. Awaiting CTO authorization for FP-6 implementation.**
