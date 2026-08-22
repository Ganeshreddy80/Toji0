# SPRINT 003 — PRICE ACTION ARCHITECTURE & INTEGRATION PLAN (REVISED)

**Author:** TOJI CTO / Lead Architect  
**Date:** 2026-08-10T13:43:00Z  
**Environment:** Developer Mac (Neon PostgreSQL Cloud Instance)  
**Governance:** Master Architecture Governance — Sprint 003 Plan (Supersedes previous version)  
**Predecessor:** `PRICE-ACTION-CTO-CORRECTION-GATE.md` — **PASS**

---

## STATUS CORRECTIONS FROM CTO REVIEW

1. **`_bars` private coupling is NOT fixed.** `run_paper_trading.py:284` still accesses `pa_orch._bars.get(symbol, [])` directly. The approved public contract is defined but not yet implemented.
2. **Plugin boot vs. tick order clarified:** `FeaturePlatformPlugin` (priority `10`) DI-boots BEFORE `PriceActionPlugin` (priority `10.1`). However, during active tick processing, Price Action is invoked BEFORE Feature Platform (line 280 vs. line 337 in `run_paper_trading.py`).
3. **Arbitrary performance targets removed.** All performance claims are deferred until PA-5 empirical measurement.

---

## NON-NEGOTIABLE CONSTRAINTS

- Price Action MUST NOT make trading decisions.
- Price Action MUST NOT place orders.
- Price Action MUST NOT bypass Risk.
- Price Action MUST NOT access OMS.
- No duplicate implementation (`price_action/`) will be deleted or merged during Sprint 003.
- No production source files will be modified until CTO gate approval for each stage.

---

## SPRINT 003 STAGES

### Stage PA-0: Discovery & Interface Verification
**Goal:** Confirm all public methods on `IPriceActionOrchestrator` and their contracts.
**Scope:**
- Audit `research_platform/price_action/interfaces.py` — existing public methods: `process_tick`, `get_swings`, `get_structure_changes`, `get_blocks`, `get_gaps`, `get_atr`, `get_vwap`.
- Confirm a `get_bars(symbol: str) -> List[Dict[str, Any]]` public method is missing (required to replace `_bars` access).
- Confirm `StructureDetected`, `ImbalanceDetected`, `SessionUpdated` event schemas in `events.py`.
- Confirm DI resolution order in `startup.py`: `FeaturePlatformPlugin` priority `10` < `PriceActionPlugin` priority `10.1`.
- **Output:** Discovery notes in gate document. No code changes.

### Stage PA-1: Input/Output Contract Formalization
**Goal:** Define and implement the `get_bars()` public method on `IPriceActionOrchestrator` and `PriceActionOrchestrator`.
**Scope:**
- Add `get_bars(symbol: str) -> List[Dict[str, Any]]` to `IPriceActionOrchestrator` interface.
- Implement `get_bars()` on `PriceActionOrchestrator` to return a defensive copy of `_bars[symbol]`.
- Standardize all timestamps in tick and bar outputs to UTC ISO-8601 aware `datetime` objects.
- **Tests:** Unit tests verifying `get_bars()` returns correct 1m OHLC bars after tick ingestion.

### Stage PA-2: Decoupled Integration
**Goal:** Replace private `_bars` coupling in `run_paper_trading.py` with the public `get_bars()` method.
**Scope:**
- Update `scripts/run_paper_trading.py:284` from `pa_orch._bars.get(symbol, [])` to `pa_orch.get_bars(symbol)`.
- Verify no other caller accesses `_bars` directly (grep evidence required before change).
- **Tests:** Integration test verifying post-change tick-to-feature pipeline produces same results.

### Stage PA-3: Deterministic Unit Test Suite
**Goal:** Comprehensive, isolated unit tests for all PA detection logic.
**Scope:**
- 5-bar fractal swing high/low detection: rising, falling, sideways market conditions.
- Bullish and bearish Fair Value Gap (FVG) detection.
- Market structure break detection (higher high, lower low).
- Memory cache truncation: 1,000-tick and 200-bar limits enforced under continuous stream.
- Missing/zero volume tick handling.
- **Tests:** All must pass deterministically (same input → same output, always).

### Stage PA-4: Historical Validation
**Goal:** Prove PA detection is deterministic over an extended replay.
**Scope:**
- Replay 1,000 continuous 1-minute OHLCV candles through `PriceActionOrchestrator`.
- Record all detected swing points and FVGs.
- Replay the exact same candles again and verify bit-for-bit identical detection output.
- **Tests:** Replay idempotency test must pass.

### Stage PA-5: Empirical Performance Baseline
**Goal:** Measure actual performance; do NOT optimize yet.
**Metrics to measure:**
- p50, p95, p99, max latency per `process_tick()` call (in microseconds).
- Throughput: ticks/second ingestion rate.
- CPU utilization (%) during 10,000-tick benchmark.
- RSS memory growth (MB) across 1, 2, 5, 10 active symbols.
- Number of detected events per 1,000 ticks.
**Output:** Baseline measurement report. Optimization targets defined only AFTER this data is collected.

---

## ACCEPTANCE CRITERIA

1. All Sprint 003 unit and integration tests pass.
2. Zero regressions in Sprint 001 and Sprint 002 test suites (73+ unit + 2 live Neon integration tests).
3. `_bars` private coupling fully replaced by public `get_bars()` method in `run_paper_trading.py`.
4. Empirical baseline measurement captured and documented.
5. No orphaned standalone `price_action/` module modified or deleted.
6. Neon PostgreSQL remains the transactional database.

---

## MASTER ROADMAP POSITION

This sprint corresponds to **Phase 3** of the [MASTER-ROADMAP-CORRECTED.md](file:///Users/a.ganeshkumarreddy12/Downloads/toji-main%203/docs/program_management/MASTER-ROADMAP-CORRECTED.md).

Research subsystem integration is **Phase 4 and later** — outside the scope of Sprint 003.
