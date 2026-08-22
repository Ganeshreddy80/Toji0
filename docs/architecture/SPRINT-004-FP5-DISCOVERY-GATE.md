# SPRINT-004 FP-5 — FEATURE PIPELINE DETERMINISM VALIDATION
## Discovery / Architecture Audit Gate

**Author:** TOJI Senior Quant Architect / CTO Office
**Date:** 2026-08-14
**Governance:** Master Architecture Governance — Sprint 004 / FP-5 Discovery
**Stage:** DISCOVERY / ARCHITECTURE AUDIT ONLY — Zero production code changes
**Predecessor:** `SPRINT-004-FP4-IMPLEMENTATION-GATE.md` — **CERTIFIED PASS**

---

## 1. STAGE DEFINITION

### 1.1 Authoritative Source

FP-5 is defined in the Sprint-004 Feature Pipeline Discovery Gate
(`SPRINT-004-FEATURE-PIPELINE-DISCOVERY-GATE.md`), Section 14, Stage FP-5:

> **Stage FP-5: Feature Pipeline Determinism Validation**
> Comparable to PA-4 synthetic replay: run the Feature Pipeline twice over an
> identical bar sequence and assert identical output DataFrames.
> Fix the `datetime.now()` non-deterministic `as_of` timestamp in
> `compute_and_store()` (inject a `reference_time` parameter with default
> `None` -> `datetime.now()`).

### 1.2 Objective

Certify that the Feature Pipeline transformer DAG is **deterministic and
reproducible** under identical input bar sequences, using the same two-pass
replay methodology established for Price Action in PA-4.

This closes the determinism gap documented in the Sprint-004 Discovery Gate
(Section 10.2):

> "No determinism test exists for the Feature Pipeline comparable to the PA-4
> replay test."

---

## 2. CERTIFIED FOUNDATION (FROZEN — DO NOT REOPEN)

| Sprint | Stage | Status         | Gate Document                                          |
|--------|-------|----------------|--------------------------------------------------------|
| 003    | PA-4  | CERTIFIED PASS | `SPRINT-003-PA4-GATE.md`                               |
| 004    | FP-0  | CERTIFIED PASS | `SPRINT-004-FP0-CONTRACT-GATE.md`                      |
| 004    | FP-1  | CERTIFIED PASS | `SPRINT-004-FP1-IMPLEMENTATION-GATE.md`                |
| 004    | FP-2  | CERTIFIED PASS | `SPRINT-004-FP2-IMPLEMENTATION-GATE.md`                |
| 004    | FP-3  | CERTIFIED PASS | `SPRINT-004-FP3-OQ-RESOLUTION.md`                      |
| 004    | FP-3B | CERTIFIED PASS | `SPRINT-004-FP3B-CANONICAL-VOLATILITY-DISCOVERY-GATE.md` |
| 004    | FP-3C | CERTIFIED PASS | `SPRINT-004-FP3C-CANONICAL-VOLATILITY-CONTRACT-GATE.md`  |
| 004    | FP-3D | CERTIFIED PASS | `SPRINT-004-FP3D-IMPLEMENTATION-GATE.md`               |
| 004    | FP-4  | CERTIFIED PASS | `SPRINT-004-FP4-IMPLEMENTATION-GATE.md`                |

**ADR-001 (Canonical ATR Ownership) — BINDING:**

```
PriceActionOrchestrator.get_atr(symbol) = canonical ATR for all strategy/risk decisions.
FeaturePlatform AtrTransformer output   = INTERNAL DAG ONLY (atr -> normalized_atr -> risk_score).
```

---

## 3. REFERENCE: PA-4 DETERMINISM PATTERN

The PA-4 test suite (`test_sprint003_pa4_historical_validation.py`) established
the canonical determinism verification methodology for TOJI:

| Requirement                         | Test                              | Method                                                    |
|-------------------------------------|-----------------------------------|-----------------------------------------------------------|
| R1 — Extended replay executes cleanly | `test_1_historical_replay_execution` | 1,440-minute synthetic bar sequence, clean exit        |
| R2/R3 — Two-pass bit-identical output | `test_2_two_pass_deterministic_replay` | Two independent instances, same tick stream -> `==` assertion |
| R3 — SHA-256 canonical fingerprint  | `test_3_output_fingerprint_sha256` | JSON-serialized output -> `sha256.hexdigest()` must match |
| R4 — Event sequence identity        | `test_4_event_sequence_identity`  | EventBus publish call order and payloads identical        |
| R5 — 200-bar window consistency     | `test_5_bar_window_consistency`   | Retained window identical across runs                     |

**FP-5 must produce an equivalent suite for the Feature Pipeline.**

---

## 4. NON-DETERMINISM VECTOR AUDIT

### 4.1 Confirmed Non-Determinism Sites

The following wall-clock-dependent calls were identified across the Feature
Platform codebase. Each is a **non-determinism vector** that must be controlled
in the FP-5 test suite.

#### Vector ND-1 — `compute_and_store()` — CRITICAL

**File:** `research_platform/feature_platform/orchestrator.py`
**Lines:** 299, 306

```python
# Line 299
as_of = as_of_time or datetime.now(timezone.utc)      # ND-1a: wall clock -> output DataFrame

# Line 306
output_df["effective_time"] = datetime.now(timezone.utc)  # ND-1b: second wall clock call
```

**Impact on output:** Both `as_of` and `effective_time` columns of the output
DataFrame will differ between two independent `compute_and_store()` calls even
on identical input DataFrames. Direct `DataFrame.equals()` comparison will fail.

**Existing mitigation:** The `as_of_time: Optional[datetime] = None` parameter
exists at line 293. If a caller supplies a fixed `as_of_time`, ND-1a is
controlled. **ND-1b has no override path.**

---

#### Vector ND-2 — `FeatureRecord` model timestamps — MEDIUM

**File:** `research_platform/feature_platform/models.py`
**Lines:** 39–40

```python
created_time: datetime = Field(default_factory=datetime.utcnow)  # ND-2a
updated_time: datetime = Field(default_factory=datetime.utcnow)  # ND-2b
```

**Impact on output:** Zero. `FeatureRecord` metadata is not consumed by
`FeaturePipeline.compute()`. Impact is limited to registry-level object
comparisons in tests that inspect `FeatureRecord` instances directly.

---

#### Vector ND-3 — `FeatureValidationResult.timestamp` — LOW

**File:** `research_platform/feature_platform/models.py`
**Line:** 85

```python
timestamp: datetime = Field(default_factory=datetime.utcnow)  # ND-3
```

**Impact on output:** Zero. Validation metadata only.

---

#### Vector ND-4 — `FeatureVersionInfo.creation_time` — LOW

**File:** `research_platform/feature_platform/models.py`
**Line:** 115

```python
creation_time: datetime = Field(default_factory=datetime.utcnow)  # ND-4
```

**Impact on output:** Zero. Version metadata only.

---

#### Vector ND-5 — `FeatureImportanceMetrics` / `FeatureFreshnessMetrics` timestamps — LOW

**File:** `research_platform/feature_platform/models.py`
**Lines:** 169, 222

**Impact on output:** Zero. Governance metadata. Not in production execution path.

---

#### Vector ND-6 — `validators.py` `validation_id` UUID — LOW

**File:** `research_platform/feature_platform/validators.py`
**Line:** 106

```python
validation_id=str(uuid.uuid4()),  # ND-6
```

**Impact on output:** Zero. Validation ID is metadata only. Validator is called
inside `compute_and_store()` but produces no columns in the output DataFrame.

---

#### Vector ND-7 — `governance.py` `report_id` UUID / `timestamp` — LOW

**File:** `research_platform/feature_platform/governance.py`
**Lines:** 59, 71

**Impact on output:** Zero. `evaluate_promotion()` has zero production callers
(confirmed, Sprint-004 Discovery Gate R-10). Governance reporting path only.

---

#### Vector ND-8 — `freshness.py` `datetime.now()` — LOW

**File:** `research_platform/feature_platform/freshness.py`
**Line:** 32

**Impact on output:** Zero. `evaluate_freshness()` has zero production callers.

---

### 4.2 Non-Determinism Vector Summary Table

| Vector | File            | Line(s) | Scope                                          | Impact on Feature Output DataFrame        |
|--------|-----------------|---------|------------------------------------------------|-------------------------------------------|
| ND-1a  | `orchestrator.py` | 299   | `compute_and_store()` -> `as_of` column        | **CRITICAL — directly in output**         |
| ND-1b  | `orchestrator.py` | 306   | `compute_and_store()` -> `effective_time` col  | **CRITICAL — directly in output**         |
| ND-2a/b | `models.py`   | 39–40   | `FeatureRecord` metadata timestamps            | None (not consumed by DAG)                |
| ND-3   | `models.py`     | 85      | `FeatureValidationResult.timestamp`            | None                                      |
| ND-4   | `models.py`     | 115     | `FeatureVersionInfo.creation_time`             | None                                      |
| ND-5   | `models.py`     | 169,222 | Governance model timestamps                    | None                                      |
| ND-6   | `validators.py` | 106     | `validation_id` UUID                           | None (ID only, not a value column)        |
| ND-7   | `governance.py` | 59,71   | `report_id` UUID / timestamp                   | None                                      |
| ND-8   | `freshness.py`  | 32      | `datetime.now()` in freshness evaluation       | None                                      |

**Conclusion:** Only ND-1a and ND-1b affect the computed output DataFrame.
ND-1a is controllable via the existing `as_of_time` parameter.
ND-1b has **no current override path** and requires a minimal surgical fix.

---

## 5. FEATURE PIPELINE TRANSFORMER DAG — DETERMINISM ANALYSIS

### 5.1 Transformer Purity Audit

All 20 registered transformers in `research_platform/feature_platform/transformers.py`
were audited for internal state or non-determinism sources:

| Transformer              | Depends On                    | Non-Determinism Vectors | Verdict   |
|--------------------------|-------------------------------|-------------------------|-----------|
| `CloseTransformer`       | —                             | None                    | Pure      |
| `OpenTransformer`        | —                             | None                    | Pure      |
| `HighTransformer`        | —                             | None                    | Pure      |
| `LowTransformer`         | —                             | None                    | Pure      |
| `VolumeTransformer`      | —                             | None                    | Pure      |
| `LogReturnTransformer`   | `close`                       | None                    | Pure      |
| `RollingStdTransformer`  | `log_return`                  | None                    | Pure      |
| `AtrTransformer` (FP)    | `high`, `low`, `close`        | None                    | Pure      |
| `NormalizedAtrTransformer` | `atr`, `close`              | None                    | Pure      |
| `RiskScoreTransformer`   | `normalized_atr`              | None                    | Pure      |
| `SignalTransformer`      | `risk_score`                  | None                    | Pure      |
| `EmaTransformer(9)`      | `close`                       | None                    | Pure      |
| `EmaTransformer(21)`     | `close`                       | None                    | Pure      |
| `EmaTransformer(50)`     | `close`                       | None                    | Pure      |
| `RsiTransformer`         | `close`                       | None                    | Pure      |
| `VolumeChangeTransformer`| `volume`                      | None                    | Pure      |
| `SupportTransformer`     | `low`                         | None                    | Pure      |
| `ResistanceTransformer`  | `high`                        | None                    | Pure      |
| `BreakoutTransformer`    | `close`, `resistance`, `support` | None                 | Pure      |
| `TrendDirectionTransformer` | `ema9`, `ema21`            | None                    | Pure      |

**Result: All 20 transformers are pure stateless functions over DataFrames.
The transformer DAG itself is deterministic.** Non-determinism is isolated
entirely to the orchestrator-layer timestamp injection (ND-1a/b).

### 5.2 `FeaturePipeline.compute()` Determinism

`FeaturePipeline.compute()` (line 67, `feature_pipeline.py`) applies
transformers in topological order from the `DependencyGraph`. Topological
ordering is deterministic for a fixed DAG. No datetime or random calls exist
in `feature_pipeline.py` or `transformers.py`.

**Conclusion: `FeaturePipeline.compute()` is fully deterministic given
identical input DataFrames.** The non-determinism that must be controlled is
entirely in `compute_and_store()` at the orchestrator layer.

---

## 6. PROPOSED FP-5 SCOPE

### 6.1 Scope Boundary

FP-5 SHALL cover:

| In Scope                                                          | Out of Scope                                      |
|-------------------------------------------------------------------|---------------------------------------------------|
| `FeaturePipeline.compute()` two-pass determinism                  | EventBus subscriber wiring (FP-6 scope)           |
| `compute_and_store()` output DataFrame determinism (controlled timestamps) | FeatureStore eviction policy              |
| SHA-256 canonical fingerprint of numeric feature output columns   | Governance feature wiring (`evaluate_promotion`)  |
| Surgical fix for ND-1b (`effective_time` override path)           | `SessionUpdated` publication                      |
| FP-5 focused regression test file                                 | Changes to certified FP-1 through FP-4 implementations |

### 6.2 Determinism Scope — Numeric Columns Only

The canonical determinism assertion for FP-5 covers **numeric feature output
columns only**:

```
close, open, high, low, volume,
log_return, rolling_std,
atr (FP-internal), normalized_atr, risk_score, signal,
ema9, ema21, ema50,
rsi, volume_change,
support, resistance, breakout, trend
```

The `as_of` and `effective_time` timestamp columns are **excluded from the
SHA-256 fingerprint** — they must be controlled (fixed reference time injected)
rather than compared directly.

### 6.3 Synthetic Bar Sequence Requirements

The FP-5 test suite requires a **deterministic synthetic 1-minute OHLCV bar
sequence** — not ticks. This differs from PA-4 (which generated ticks):

- FP-5 input is a `pd.DataFrame` of OHLCV bars (matching `compute_and_store()`
  contract).
- The synthetic generator must be **seeded and reproducible** (no `random`,
  no wall-clock).
- Minimum sequence: **200 bars** (sufficient for all rolling-window transformers
  at their maximum look-back — EMA-50 requires 51 bars minimum).
- Recommended: **500 bars** (consistent with PA-4 scale intent; avoids
  warm-up edge effects in EMA-50 and RSI).

Transformer warm-up requirements:

| Transformer   | Look-back | Minimum bars needed |
|---------------|-----------|---------------------|
| ATR (FP)      | 14        | 15                  |
| RSI           | 14        | 15                  |
| EMA-9         | 9         | 10                  |
| EMA-21        | 21        | 22                  |
| EMA-50        | 50        | 51                  |
| RollingStd    | 14        | 15                  |

**Minimum absolute: 51 bars. Proposed canonical: 500 bars.**

---

## 7. PROPOSED IMPLEMENTATION PLAN

> **Important:** This plan is subject to CTO authorization before any code
> changes. Zero production code changes are made during this discovery stage.

### Phase 1 — Surgical Fix for ND-1b (Minimal Production Change)

**File:** `research_platform/feature_platform/orchestrator.py`
**Lines:** 302–306
**Change:** Route `effective_time` fallback through the already-injectable
`as_of` value, eliminating the second independent `datetime.now()` call.

Current (line 306):
```python
output_df["effective_time"] = datetime.now(timezone.utc)   # ND-1b: no override path
```

Proposed (line 306):
```python
output_df["effective_time"] = as_of   # use controlled as_of — eliminates ND-1b
```

**Rationale:** When `as_of_time` is supplied by the test, both `as_of` and
`effective_time` become deterministic. When `as_of_time` is `None` (production
default), behavior is unchanged: `as_of = datetime.now()` and
`effective_time = as_of`. The two timestamps remain correlated rather than
diverging between two separate `datetime.now()` calls.

**Risk:** MINIMAL. No algorithmic change. No behavioral change under
production. Existing tests unaffected.

### Phase 2 — FP-5 Determinism Test Suite

**New file:** `research_platform/tests/test_sprint004_fp5_determinism.py`

Required tests:

| Test                                   | Requirement                                                                        |
|----------------------------------------|------------------------------------------------------------------------------------|
| `test_fp5_1_synthetic_bar_replay_executes` | 500-bar synthetic sequence processes through `compute_and_store()` without error |
| `test_fp5_2_two_pass_numeric_determinism`  | Two independent orchestrator instances + identical bar sequence + fixed `as_of_time` -> numeric output columns bit-identical |
| `test_fp5_3_sha256_canonical_fingerprint`  | Numeric output columns (timestamp-excluded) -> JSON serialize -> SHA-256 must match between Run A and Run B |
| `test_fp5_4_pipeline_compute_direct_determinism` | `FeaturePipeline.compute()` called directly (bypassing orchestrator timestamps) -> DataFrames `equals()` exactly |
| `test_fp5_5_warm_up_edge_determinism`      | First 14 bars (ATR/RSI/EMA warm-up) -> NaN presence identical between runs        |

### Phase 3 — Regression Verification

After FP-5 implementation, run the full Sprint-003/004 focused regression suite:

```bash
python3 -m pytest \
  research_platform/tests/test_sprint004_fp1_registration_lifecycle.py \
  research_platform/tests/test_sprint004_fp2_public_api_boundary.py \
  research_platform/tests/test_sprint004_fp3d_annualized_vol.py \
  research_platform/tests/test_exit_engine.py \
  research_platform/tests/test_trade_journal.py \
  research_platform/tests/test_feature_platform.py \
  -v --tb=short
```

**Baseline:** 117 tests passing (Sprint-003/004 regression suite at FP-4 certification).
**FP-5 target:** 117 + 5 = **>=122 tests passing, 0 failures**.

---

## 8. OPEN QUESTIONS FOR CTO

### OQ-FP5-1 — Authorize ND-1b One-Line Fix

The ND-1b fix (replacing `datetime.now(timezone.utc)` at line 306 with `as_of`)
is a **one-line surgical change** to production code. It eliminates a latent
non-determinism vector and a secondary wall-clock call with zero algorithmic
impact.

**Question:** Is CTO authorization granted for this minimal one-line surgical
fix to `orchestrator.py` as part of FP-5 implementation?

**If NO:** The FP-5 test suite can still be written. Tests comparing output
DataFrame columns directly must exclude both `as_of` and `effective_time`.
The latent non-determinism in `effective_time` is documented as a deferred
advisory.

**If YES:** Implement Phase 1 as described in Section 7.

---

### OQ-FP5-2 — Confirm 500-Bar Synthetic Sequence Length

Minimum required: 51 bars (EMA-50 warm-up). Proposed: 500 bars.

**Question:** Is 500 bars accepted as the canonical FP-5 synthetic bar sequence
length, or does CTO prefer a different count?

---

### OQ-FP5-3 — Deferred Advisory for Model Metadata Timestamps

ND-2 through ND-8 (model metadata timestamps and validation UUIDs) have
**zero impact on computed feature output values** but would cause comparison
failures if tests compared model objects directly.

**Question:** Should FP-5 document these as **deferred advisory items** (no
fix required in Sprint-004), or should any of them be addressed in FP-5?

**Recommendation:** Defer all model metadata timestamp vectors (ND-2 through
ND-8) as advisories. They do not affect the determinism of the trading
computation path. Fixing them would require Pydantic model signature changes
with broader test impact.

---

## 9. DEFERRED ITEMS (EXPLICITLY OUT OF FP-5 SCOPE)

| Item                                              | Source         | Deferral Reason                     |
|---------------------------------------------------|----------------|-------------------------------------|
| ADV-1 — DEBUG logging verbosity                   | FP-4           | Non-blocking advisory               |
| R-7 — `StructureDetected`/`ImbalanceDetected` zero subscribers | FP-0 Discovery | FP-6 scope (EventBus wiring) |
| R-9 — `BreakOfStructureDetected` vs `StructureDetected` parallel systems | FP-0 Discovery | Phase 7 consolidation |
| R-10 — Governance features unwired               | FP-0 Discovery | Later sprint                        |
| FeatureStore unbounded growth                     | FP-0 Discovery | Phase 4 / Persistence sprint        |
| ND-2 through ND-8 — Model metadata timestamps    | FP-5 Discovery | No impact on output; deferred advisory |

---

## 10. PRODUCTION FILES AUDIT (THIS DISCOVERY STAGE)

```
Production Python Files Modified:  0
Test Files Created:                0
Documentation Files Created:       1  (this document)
```

---

## 11. DISCOVERY GATE CLASSIFICATION

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   SPRINT-004 FP-5 DISCOVERY GATE:                                            ║
║   COMPLETE — AWAITING CTO AUTHORIZATION FOR IMPLEMENTATION                   ║
║                                                                              ║
║   Architecture Status:                                                       ║
║   • Feature Pipeline transformer DAG: FULLY DETERMINISTIC (20/20 pure)      ║
║   • Non-determinism scope: ISOLATED to orchestrator timestamp injection      ║
║   • ND-1a: Controlled by existing as_of_time parameter                       ║
║   • ND-1b: Requires one-line surgical fix (OQ-FP5-1 CTO decision needed)    ║
║   • ND-2 through ND-8: Zero impact on output values; deferred advisory       ║
║   • PA-4 two-pass replay methodology: Directly applicable to FP-5           ║
║   • FP-5 test plan: 5 tests defined — awaiting authorization                 ║
║                                                                              ║
║   Open Questions:                                                            ║
║   • OQ-FP5-1 — Authorize ND-1b one-line fix in orchestrator.py?             ║
║   • OQ-FP5-2 — Confirm 500-bar synthetic sequence length?                   ║
║   • OQ-FP5-3 — Defer model metadata timestamp vectors as advisory?          ║
║                                                                              ║
║   Production files changed in this discovery stage: 0                       ║
║   Awaiting CTO authorization before any implementation begins.               ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

**STOP.** Discovery audit is complete. Returning gate document for CTO review
and stage authorization.
