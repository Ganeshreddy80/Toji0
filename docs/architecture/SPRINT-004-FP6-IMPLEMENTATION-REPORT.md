# SPRINT-004 FP-6 — EVENTBUS OBSERVABILITY SUBSCRIBER WIRING
## Implementation Report & Gate Certification

**Author:** TOJI Senior Staff Engineer / Principal Architect  
**Date:** 2026-08-15  
**Sprint:** 004  
**Stage:** FP-6 (Option A — Observability Subscribers Only)  
**Status:** IMPLEMENTED & VERIFIED — CERTIFIED PASS  
**Predecessors:** FP-1, FP-2, FP-3D, FP-4, FP-5 — **ALL CERTIFIED PASS (FROZEN)**  

---

## 1. CTO AUTHORIZATION

CTO Decision on OQ-FP6-1:
- **Verdict:** `InMemoryEventBus.publish()` is **SYNCHRONOUS**. Handlers execute in-line on the publishing thread in registration order before `publish()` returns.
- **Authorized Option:** **OPTION A — OBSERVABILITY SUBSCRIBERS ONLY**.
- **Authorized Production Files:**
  1. `research_platform/feature_platform/plugin.py`
  2. `research_platform/feature_platform/orchestrator.py` (FP6-N-1 defensive isolation)

---

## 2. SCOPE OF IMPLEMENTATION

### Authorized (Implemented)
1. **Subscription Lifecycle in `FeaturePlatformPlugin`:**
   - `initialize()`: Subscribes `_log_event` to `"system.feature_calculated"` and `"system.feature_validated"`.
   - `shutdown()`: Unsubscribes exact handlers registered during `initialize()`.
   - Idempotent and clean teardown pattern matching existing platform conventions.
2. **Observability-Only Handlers:**
   - Handlers emit `logger.debug()` only with concise metadata (`name`, `version`, `symbol`, `approved`).
   - Zero DataFrame processing, zero store writes, zero recursive publish, zero blocking calls.
3. **EventBusError Isolation (FP6-N-1):**
   - Wrapped `FeatureValidated` and `FeatureCalculated` publish sites in `FeaturePlatformOrchestrator.compute_and_store()` with `try/except EventBusError`.
   - Subscriber dispatch errors are isolated, logged as `logger.warning()`, and do NOT abort feature calculations or tick processing.
   - Specific exception isolation (catches `EventBusError` only; does not swallow domain calculation or store errors).

### Strictly Excluded / Forbidden
- Option B (Freshness evaluation via subscriber): Explicitly deferred.
- Option D (StructureDetected -> compute_and_store): Explicitly rejected (deadlock & double computation risk).
- Governance runtime wiring (promotion, importance): Deferred.
- FeatureScheduler background loop startup: Deferred.
- EventBus / FeatureStore architectural modifications: Prohibited.

---

## 3. PRODUCTION FILES CHANGED

### 1. `research_platform/feature_platform/plugin.py`
- Added subscriptions in `initialize()` for `"system.feature_calculated"` and `"system.feature_validated"`.
- Added symmetric `unsubscribe()` logic in `shutdown()`.
- Added `_log_event()` handler logging concise event metadata at `DEBUG` level.

### 2. `research_platform/feature_platform/orchestrator.py`
- Imported `EventBusError` from `toji_platform.core.errors`.
- Added `try/except EventBusError` blocks around `FeatureValidated` and `FeatureCalculated` publish calls inside `compute_and_store()`.

---

## 4. SUBSCRIPTION LIFECYCLE & HANDLER BEHAVIOR

```
[Container Boot]
       │
       ▼
FeaturePlatformPlugin.initialize()
       ├── orchestrator.register_default_features()
       ├── container.register(FeaturePlatformOrchestrator, ...)
       ├── event_bus.subscribe("system.feature_calculated", _log_event)
       └── event_bus.subscribe("system.feature_validated", _log_event)
       │
       ▼  (Runtime Tick Flow)
orchestrator.compute_and_store()
       ├── pipeline.compute()
       ├── validator.validate()
       ├── try: publish(FeatureValidated) ──► _log_event() [DEBUG log]
       │   except EventBusError: logger.warning(...)
       ├── store.save_features()
       └── try: publish(FeatureCalculated) ──► _log_event() [DEBUG log]
           except EventBusError: logger.warning(...)
       │
       ▼
FeaturePlatformPlugin.shutdown()
       ├── event_bus.unsubscribe("system.feature_calculated", _log_event)
       └── event_bus.unsubscribe("system.feature_validated", _log_event)
```

---

## 5. TEST SUITE & VERIFICATION EVIDENCE

### 5.1 New Dedicated FP-6 Test Suite
**File:** `research_platform/tests/test_sprint004_fp6_eventbus_wiring.py` (20 tests, all passing)

| Test ID / Method | Verified Assertion | Result |
|------------------|--------------------|:------:|
| `test_feature_calculated_has_subscriber` | `FeatureCalculated` subscribed on init | **PASSED** |
| `test_plugin_state_is_running_after_initialize` | Module state `RUNNING` | **PASSED** |
| `test_feature_validated_has_subscriber` | `FeatureValidated` subscribed on init | **PASSED** |
| `test_feature_calculated_subscriber_removed_on_shutdown` | `FeatureCalculated` unsubscribed on shutdown | **PASSED** |
| `test_feature_validated_subscriber_removed_on_shutdown` | `FeatureValidated` unsubscribed on shutdown | **PASSED** |
| `test_plugin_state_is_stopped_after_shutdown` | Module state `STOPPED` | **PASSED** |
| `test_handler_does_not_call_compute_and_store` (Calc) | Calc handler triggers 0 computes | **PASSED** |
| `test_handler_does_not_raise` (Calc) | Calc handler error-free execution | **PASSED** |
| `test_handler_logs_debug` (Calc) | Calc handler emits DEBUG with feature name | **PASSED** |
| `test_handler_does_not_call_compute_and_store` (Val) | Val handler triggers 0 computes | **PASSED** |
| `test_handler_does_not_raise` (Val) | Val handler error-free execution | **PASSED** |
| `test_handler_logs_debug` (Val) | Val handler emits DEBUG with feature name | **PASSED** |
| `test_subscriber_error_does_not_propagate_from_compute_and_store` | Bad subscriber doesn't abort compute | **PASSED** |
| `test_subscriber_error_is_logged_as_warning` | Bad subscriber logs `WARNING` | **PASSED** |
| `test_output_identical_with_and_without_subscriber` | DataFrame identical with observers | **PASSED** |
| `test_no_stale_subscriptions_after_reinitialize` | Re-init does not duplicate subscribers | **PASSED** |
| `test_shutdown_without_initialize_does_not_raise` | Safe un-initialized shutdown | **PASSED** |
| `test_handler_executes_before_publish_returns` | Synchronous execution proof | **PASSED** |
| `test_registration_order_preserved` | Registration order guaranteed | **PASSED** |
| `test_all_handlers_execute_even_if_one_raises` | All handlers run before exception | **PASSED** |

### 5.2 Full Feature Platform & Selected Regression Verification
- **FP-6 Dedicated Suite:** `test_sprint004_fp6_eventbus_wiring.py` -> **20/20 PASSED**
- **FP-5 Determinism + FP-6 Wiring:** `test_sprint004_fp5_determinism.py` + `test_sprint004_fp6_eventbus_wiring.py` -> **25/25 PASSED**
- **Feature Platform Focused Suite:** `test_feature_platform.py` + FP-1 + FP-2 + FP-3D + FP-5 + FP-6 -> **78/78 PASSED**
- **Selected Sprint-003/004 + EventBus Regression Suite:** PA-1 + PA-3 + PA-4 + PA-5 + FP-1 + FP-2 + FP-3D + FP-5 + FP-6 + `test_event_bus.py` -> **145/145 PASSED**

---

## 6. PERFORMANCE & THREADING CONSIDERATIONS

1. **Lightweight Observer Execution:**
   - Observer handlers are intentionally lightweight: DEBUG-only logging with concise metadata and no blocking I/O, feature computation, FeatureStore access, or recursive publication.
2. **Locking & Deadlock Safety:**
   - `EventBus` uses `threading.RLock()`.
   - Dispatch occurs outside the lock on a snapshot of handlers.
   - `FeatureStore` lock is released before `publish()` is called in `compute_and_store()`.
   - Zero deadlock risk.

---

## 7. EXPLICITLY DEFERRED & REJECTED ITEMS

| Item | Classification | Reason |
|------|:--------------:|--------|
| Option B (Freshness tracking via subscriber) | **DEFERRED** | Unnecessary per-tick repository write overhead; deferred to future platform governance sprint. |
| Option D (StructureDetected recomputation) | **REJECTED** | Reentrancy, double computation per tick, and missing DataFrame context in event payload. |
| Governance Promotion / Importance wiring | **DEFERRED** | Explicitly out of scope for Feature Pipeline core execution. |
| FeatureScheduler startup | **DEFERRED** | Polling model remains standard; scheduler loop unneeded for per-tick flow. |

---

## 8. REPOSITORY AUDIT & FINAL VERIFICATION

- **Production Python files modified:** 2 (`research_platform/feature_platform/plugin.py`, `research_platform/feature_platform/orchestrator.py`)
- **Test files added:** 1 (`research_platform/tests/test_sprint004_fp6_eventbus_wiring.py`)
- **Documentation files created/updated:** 
  - `docs/architecture/SPRINT-004-FP6-IMPLEMENTATION-REPORT.md`
  - `docs/architecture/SPRINT-004-FP6-IMPLEMENTATION-GATE.md`
- **Unrelated modifications:** 0

---

## 9. CONCLUSION

FP-6 Option A has been implemented and certified under Master Architecture Governance.
