# TOJI FP-7D-2 INDEPENDENT CTO CERTIFICATION REPORT

**Audit mode:** Read-only independent red-team / CTO architecture audit  
**Repository under audit:** `toji-main5.zip`  
**Audit date:** 2026-08-21  
**Author:** Manus AI  
**Certification boundary:** FP-7D-2 only; no production-readiness, live-trading, persistence, OMS, backtesting, or behavioral-parity certification is implied.

## 1. Executive Verdict

### **CERTIFIED WITH CONDITIONS**

The implementation evidence for the FP-7D-2 objective is positive. The current snapshot contains a 21-name `DEFAULT_COMPUTE_NAMES` tuple derived from `DEFAULT_FEATURE_DEFINITIONS`; the active transformer registry, registered-feature registry, and populated DAG all contain the same 21 names; paper and live compute sites reference the canonical tuple; lazy live import behavior is preserved; the FP-7D-1 and FP-7C predecessor contracts remain intact; and the required tests passed on Python 3.12.3.

Unconditional **CERTIFIED PASS** is withheld for one evidence-boundary condition: the uploaded snapshot contains no Git metadata and no independently supplied predecessor manifest or hash baseline. Therefore, the audit can prove that the extracted files match the uploaded ZIP and that the current source satisfies the FP-7D-2 checks, but it cannot prove the historical diff of the entire repository or conclusively distinguish every pre-existing file from every FP-7D-2 modification. This is a certification-evidence limitation, not an observed FP-7D-2 implementation failure.

A separate security hygiene finding is recorded because the ZIP contains a non-empty `.env` file with permissive mode `666`. Its contents were intentionally not read or printed. This finding is outside FP-7D-2 functional scope, but the file must not be included in any certification artifact and should be treated as potentially sensitive until cleared.

## 2. Environment

| Item | Observed value | Evidence / classification |
|---|---|---|
| Operating system | Linux `x86_64`, kernel `6.18.38+` | Executed audit environment; PROVEN |
| Python used | `Python 3.12.3` | Actual test runtime; PROVEN |
| pytest used | `pytest 9.1.1` | Actual test runner; PROVEN |
| Python 3.13 | Unavailable | Explicitly checked; not tested and not claimed |
| Git metadata in snapshot | Unavailable (`.git` absent) | Scope-provenance limitation; PROVEN |
| SQLAlchemy | Installed during audit because collection initially lacked it | Environmental setup correction; not a source change |
| Secrets read | None | `.env` metadata only; contents intentionally not inspected |

The first focused-test attempt could not start because `pytest` was absent from the environment. After installing the test runner, the first complete Sprint-004 collection encountered one environmental `ModuleNotFoundError` for `sqlalchemy`. SQLAlchemy was then installed and the required tests were rerun successfully. These initial errors are classified as **environmental**, not repository test failures.

## 3. Exact Test Results

### 3.1 Required individual test modules

| Test module | Result | Warnings | Errors / skips |
|---|---:|---:|---:|
| `test_sprint004_fp7d2_compute_centralization.py` | **17 passed** | 43 | 0 |
| `test_sprint004_fp7a_correctness.py` | **17 passed, 2 xfailed** | 49 | 0 |
| `test_sprint004_fp7b_query_api.py` | **12 passed** | 47 | 0 |
| `test_sprint004_fp7c_staleness.py` | **30 passed** | 45 | 0 |
| `test_sprint004_fp7d1_alias_removal.py` | **10 passed** | 43 | 0 |

The two FP-7A `XFAIL` results are strict, explicitly declared compatibility expectations. They cover obsolete AST assertions that required a literal list after FP-7D-2 replaced that list with `list(DEFAULT_COMPUTE_NAMES)`. The xfail reasons state that annualized-vol inclusion is now independently covered by the FP-7D-2 test. They are therefore classified as **intentional predecessor-test compatibility xfails**, not newly introduced failures.

### 3.2 Focused combined run

Command executed:

```text
PYTHONPATH=. python3 -m pytest -q \
  research_platform/tests/test_sprint004_fp7d2_compute_centralization.py \
  research_platform/tests/test_sprint004_fp7a_correctness.py \
  research_platform/tests/test_sprint004_fp7b_query_api.py \
  research_platform/tests/test_sprint004_fp7c_staleness.py \
  research_platform/tests/test_sprint004_fp7d1_alias_removal.py
```

Exact result: **86 passed, 2 xfailed, 55 warnings, 0 failed, 0 skipped, 0 errors** in 1.90 seconds.

### 3.3 Complete Sprint-004 FP family

Command executed:

```text
PYTHONPATH=. python3 -m pytest -q research_platform/tests/test_sprint004_fp*.py
```

Exact result: **158 passed, 2 xfailed, 339 warnings, 0 failed, 0 skipped, 0 errors** in 3.82 seconds across 160 collected items.

The complete family included FP1, FP2, FP3D, FP5, FP6, FP7A, FP7B, FP7C, FP7D-1, and FP7D-2.

### 3.4 Relevant Feature Platform tests

The matching test files were:

```text
research_platform/tests/test_feature_platform.py
research_platform/tests/test_live_trading.py
tests/unit/data/test_feature_store.py
```

Command executed:

```text
PYTHONPATH=. python3 -m pytest -q \
  research_platform/tests/test_feature_platform.py \
  research_platform/tests/test_live_trading.py \
  tests/unit/data/test_feature_store.py
```

Exact result: **25 passed, 86 warnings, 0 failed, 0 skipped, 0 errors** in 4.10 seconds.

Warnings were primarily the repository’s existing `datetime.utcnow()` deprecation warnings, an unknown `asyncio_mode` pytest configuration option in this environment, and numerical runtime warnings observed in feature validation tests. They did not change the FP-7D-2 outcome and are classified as **pre-existing or environmental warnings**, not newly introduced FP-7D-2 failures.

## 4. 21-Feature Parity Matrix

The matrix below was verified programmatically after `register_default_features()` populated the registry and DAG. Every row is present in the definitions, transformer registry, registered-feature registry, DAG, and `DEFAULT_COMPUTE_NAMES`; both production compute sites reference the canonical tuple rather than a local 21-name literal.

| Feature | Definition | Transformer | DAG | Registry | `DEFAULT_COMPUTE_NAMES` | Paper | Live |
|---|---|---|---|---|---|---|---|
| `open` | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `high` | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `low` | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `close` | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `volume` | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `log_return` | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `atr` | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `ema9` | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `ema21` | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `ema50` | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `rsi` | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `volume_change` | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `support` | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `resistance` | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `rolling_std` | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `normalized_atr` | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `annualized_vol` | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `breakout` | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `trend` | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `risk_score` | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `signal` | PASS | PASS | PASS | PASS | PASS | PASS | PASS |

Programmatic counts were:

| Surface | Count | Result |
|---|---:|---|
| `DEFAULT_FEATURE_DEFINITIONS` | 21 | PASS |
| `DEFAULT_COMPUTE_NAMES` | 21 | PASS |
| `FeaturePipeline._transformers` | 21 | PASS |
| Registered definitions after `register_default_features()` | 21 | PASS |
| DAG nodes after `register_default_features()` | 21 | PASS |
| Definition-name order equals compute-tuple order | Yes | PASS |
| Duplicate compute names | 0 | PASS |
| DAG cycle | False | PASS |

## 5. C1 Parity Guard

The canonical constant is defined in `research_platform/feature_platform/orchestrator.py` as a tuple comprehension directly over `DEFAULT_FEATURE_DEFINITIONS`. The active pipeline transformer map contains exactly the same 21-name set. `register_default_features()` registers each definition and adds the corresponding node to the dependency graph, producing 21 registry entries and 21 DAG nodes.

The repository’s FP-7D-2 parity assertions were exercised adversarially without changing repository files. In an in-memory-only mutation, one transformer (`close`) was removed and the repository’s `TestTransformerParityGuard.test_transformer_keys_match_compute_names` assertion failed as expected. In a separate in-memory-only mutation, a fake definition named `__audit_fake__` was appended and the repository’s `TestDerivationFromDefinitions.test_exactly_equals_definition_names` assertion failed as expected. The mutations were restored in `finally` blocks and were never written to disk.

The tuple mutation attempt also failed with the expected `TypeError`, proving that the exposed compute set is not list-mutable. Fresh-process imports confirmed that the live plugin and orchestrator can be imported in either order, and two independent fresh imports produced the same compute-tuple representation.

The guard is implemented as an automated test-level parity guard rather than a production startup assertion. This is sufficient for the FP-7D-2 acceptance checks executed here, but the known residual risk remains that adding a definition without its transformer can cause a runtime `KeyError` when the compute path is exercised. The FP-7D discovery document itself records this transformer-registry gap risk as an existing risk and it remains outside the authorized remediation scope.

## 6. C2 Documentation Audit

The FP-7D documentation uses the permitted precision. In `docs/architecture/SPRINT-004-FP7D-DISCOVERY-GATE.md:411-415`, it states that FP-7D-2 establishes **feature-computation parity only** and does **not** establish end-to-end paper/live trading behavioral parity. The document also identifies position sizing, exit handling, OMS execution, and other runtime-path differences as outside FP-7D-2 scope.

A complete non-virtualenv repository search found no documentation claim that paper/live trading behavior is identical or behaviorally identical. The only matching prohibited-language search result was the explicit disclaimer quoted above, which is a correct negative statement rather than a prohibited positive claim.

The allowed claim is supported: paper and live use the same canonical feature-computation set. No broader behavioral-parity claim is certified.

## 7. C3 Scope Audit

### 7.1 Authorized scope observed

The expected FP-7D-2 production paths are present:

| Path | Current-snapshot evidence |
|---|---|
| `research_platform/feature_platform/orchestrator.py` | Present; defines `DEFAULT_COMPUTE_NAMES` |
| `scripts/run_paper_trading.py` | Present; imports and uses `DEFAULT_COMPUTE_NAMES` |
| `research_platform/live_trading/plugin.py` | Present; lazy-imports and uses `DEFAULT_COMPUTE_NAMES` |
| `research_platform/tests/test_sprint004_fp7d2_compute_centralization.py` | Present; 17 tests passed |

The protected predecessor and deferred paths were also present and source-hashed for evidence, including FP-7A, FP-7B, FP-7C, FP-7D-1, `backtesting/engine.py`, `research_platform/runtime/strategy_loop.py`, FeatureStore/interfaces/pipeline/dependency-graph/transformer files, `research_platform/oms/oms_core.py`, and `toji_platform/core/event_bus/bus.py`.

For all audited paths, the SHA-256 hash of the extracted file matched the SHA-256 hash of the same member streamed directly from the uploaded ZIP. This proves that the audit workspace remained byte-identical to the uploaded snapshot for those files. It does **not** prove the historical diff relative to a predecessor snapshot.

### 7.2 Scope-provenance condition

The extracted repository has no `.git` directory. The project-shared ZIP is byte-identical to the uploaded ZIP, so it is not an independent predecessor baseline. Consequently, a complete repository-wide “unexpected modification” determination cannot be proven from the supplied materials alone. The required remediation is to provide either the predecessor FP-7D-1/current baseline, a trusted Git commit/diff, or a signed file manifest that identifies the permitted changes. This condition blocks unconditional PASS but does not identify an unauthorized FP-7D-2 change.

## 8. Import/Circular Dependency Audit

The live plugin does not import `DEFAULT_COMPUTE_NAMES` at module top level. Its import occurs inside `_handle_market_tick`, immediately before the canonical compute call. This preserves the required lazy-import posture for plugin discovery. The paper runner imports the constant at its existing module-level domain-import boundary.

Fresh subprocess checks passed for both import orders:

```text
IMPORT_ORDER import-orchestrator-first: PASS
IMPORT_ORDER import-plugin-first: PASS
ORDER_STABLE_ACROSS_FRESH_IMPORTS True
```

No circular-import error was observed under the available Python 3.12.3 environment. This is an import/discovery result only; it is not a certification of live exchange connectivity or real-order execution.

## 9. Hidden Duplication Audit

A complete AST-assisted scan of non-virtualenv Python source searched for full literal copies and broad subsets of the canonical feature names. No full 21-name literal duplicate was found in production code. The only full 21-name literal was `CANONICAL_21` in the FP-7D-2 test fixture, which is an intentional test oracle.

The remaining hits were classified as follows:

| Location | Classification | Reason |
|---|---|---|
| `backtesting/engine.py:29-45,54-57` | INDEPENDENT ARCHITECTURE / known deferred issue | Backtesting maintains its own 15-feature dependency and compute path; explicitly out of FP-7D-2 scope |
| `research_platform/runtime/strategy_loop.py:30-33` | KNOWN FALLBACK DIVERGENCE | Fallback query subset; explicitly deferred and not a compute-site replacement target |
| `research_platform/tests/test_sprint004_fp7d2_compute_centralization.py:41` | TEST FIXTURE | Intentional 21-feature expected-set oracle |
| `research_platform/tests/test_sprint004_fp1_registration_lifecycle.py` and `test_sprint004_fp2_public_api_boundary.py` | TEST FIXTURE / TEST INPUT | Explicit test inputs and expected subsets |
| `research_platform/tests/test_sprint004_fp5_determinism.py` | TEST FIXTURE | Determinism test data |
| `tests/e2e/test_signal_lifecycle.py` and `test_end_to_end_trading_verification.py` | TEST FIXTURE / E2E INPUT | Explicit integration test inputs |

No suspicious production duplicate of the canonical 21-feature compute set was identified. Intentional AI Signal, Position Sizing, Exit Engine, Trade Journal, backtesting, and StrategyLoop query/fallback subsets were not modified.

## 10. FP-7D-1 / FP-7C Preservation

FP-7D-1 preservation is proven by the focused tests and source inspection: `FeaturePlatformOrchestrator.query_history` is absent from executable production code, while `query_historical` remains present and callable.

FP-7C preservation is proven by the focused staleness tests and source inspection. `query_realtime` retains the `max_age_seconds` parameter with default `None`, uses one UTC reference time for the call, preserves symbol rows, and handles stale or malformed timestamps according to the tested contract. The focused FP-7C module passed all 30 tests.

The FeatureStore interface and implementation continue to expose `query_historical` and `query_latest`, and the orchestrator continues to expose `query_historical` and `query_realtime`. No source hash changes were observed in the protected FeatureStore, interface, pipeline, dependency-graph, transformer, OMS, or EventBus files during this audit.

## 11. Adversarial Test Results

| Adversarial check | Result | Evidence |
|---|---|---|
| Remove one transformer in memory | PASS | Repository parity assertion failed as expected |
| Add fake definition in memory | PASS | Repository definition-derivation assertion failed as expected |
| Mutate `DEFAULT_COMPUTE_NAMES` | PASS | Tuple assignment raised `TypeError` |
| Compare paper/live compute references | PASS | Both source sites contain `list(DEFAULT_COMPUTE_NAMES)` |
| Search hidden full 21-name production duplicates | PASS | None found; test oracle excluded as fixture |
| Import orchestrator then plugin | PASS | Fresh subprocess return code 0 |
| Import plugin then orchestrator | PASS | Fresh subprocess return code 0 |
| Fresh-import ordering stability | PASS | Two fresh subprocess representations matched |
| Verify production `query_history` absence | PASS | No executable production Python hit |
| Verify FP-7C `max_age_seconds` behavior | PASS | 30/30 staleness tests passed |
| Verify live plugin discovery import | PASS | Module import succeeded without top-level orchestrator import |

No real exchange credentials were used and no real trades were placed.

## 12. Newly Discovered Defects

### AUD-001 — Incomplete historical scope provenance

| Field | Finding |
|---|---|
| ID | AUD-001 |
| Severity | Medium for certification evidence; not an observed implementation defect |
| Evidence | `.git` is absent; no predecessor manifest or trusted diff was supplied |
| Reproduction | `test -d .git` returns false in the extracted repository; current ZIP and shared ZIP have identical SHA-256 |
| Impact | The audit proves current-snapshot correctness and archive integrity, but cannot prove the complete historical repository diff or rule out pre-existing unauthorized files |
| Blocking status | Blocks unconditional `CERTIFIED PASS`; non-blocking for the demonstrated FP-7D-2 behavior |
| Required remediation | Supply a trusted predecessor baseline, Git diff, or signed file-manifest/hash comparison before final unconditional certification |

### AUD-002 — Credential-bearing `.env` file included in snapshot

| Field | Finding |
|---|---|
| ID | AUD-002 |
| Severity | High if populated; actual contents and exposure are unknown because they were not read |
| Evidence | `.env` exists at repository root, size 3415 bytes, mode `666`; no values were printed or inspected |
| Reproduction | `stat -c '%n size=%s mode=%a' .env` |
| Impact | Any populated credentials could be exposed through repository or audit-artifact distribution |
| Blocking status | Non-blocking for FP-7D-2 feature correctness; blocks safe distribution of an unfiltered certification ZIP |
| Required remediation | Treat any populated credentials as compromised, rotate/revoke them, remove `.env` from distributable artifacts, and use a sanitized template such as `.env.example` |

No secret values are included in this report or in the attached evidence files.

## 13. Known Deferred Issues

The following areas were not fixed or certified because they are explicitly outside FP-7D-2 scope: OMS duplicate-order protection; end-to-end paper/live behavioral parity; FeatureStore historical multi-version semantics; out-of-order online feature writes; PostgreSQL production certification; validation persistence; backtesting divergence; StrategyLoop fallback divergence; EventBus architecture; and online persistence architecture.

The implementation establishes the permitted statement that paper and live share the same canonical feature-computation set. It does not establish that paper and live trading behavior are identical. Live trading remains outside production-readiness certification and no real trade was placed.

## 14. Final Certification Recommendation

**Recommendation: accept FP-7D-2 implementation as functionally passing with conditions.** The canonical compute-set centralization, parity surfaces, lazy live import, predecessor preservation, documentation precision, and adversarial checks are supported by executed evidence. Before issuing an unconditional CTO certification, obtain a trusted predecessor scope baseline and clear the `.env` artifact through the project’s security process.

The implementing audit made no changes to canonical repository source files, tests, or documentation. The audit-only harness, logs, and report were created outside the repository under `/home/ubuntu/toji-audit/`. No certification ZIP was generated, avoiding inclusion of the repository’s `.venv`, `.pyc`, `.env`, or other non-certification material.

## Certification Status

| Dimension | Status |
|---|---|
| FP-7D-2 functional objective | **PASS** |
| C1 parity and adversarial guard behavior | **PASS** |
| C2 documentation precision | **PASS** |
| C3 historical scope proof | **CONDITION — baseline unavailable** |
| FP-7D-1 preservation | **PASS** |
| FP-7C preservation | **PASS** |
| Python 3.13 coverage | **UNKNOWN — unavailable in environment** |
| Safe artifact distribution | **CONDITION — `.env` present in source snapshot** |
| Overall independent CTO status | **CERTIFIED WITH CONDITIONS** |

## Evidence Files

The following supporting files were generated outside the canonical repository and contain no secret values:

- `focused_tests.log` — focused combined test execution.
- `all_sprint004_fp_tests.log` — complete Sprint-004 FP family execution.
- `feature_platform_tests.log` — relevant Feature Platform test execution.
- `individual_test_results.log` — per-module mandatory test results.
- `adversarial_audit.log` — in-memory mutation, import-order, parity, and duplication results.
- `scope_hashes_and_manifest.log` — archive-to-extracted source hashes and non-virtualenv Python manifest.
