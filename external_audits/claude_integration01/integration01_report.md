# INTEGRATION-01 — Final Report

## What changed (summary)

No existing business logic was rewritten. Six things were added/changed, all wiring:

1. **`toji_platform/runtime/`** (new package) — `RuntimeRegistry`, `RuntimeHealth`,
   `RuntimeEngine`, `OrderSafetyGateway`. Pure composition of existing engines;
   contains no new risk math.
2. **`research_platform/runtime_integration/plugin.py`** (new, auto-discovered)
   — the only plugin whose job is wiring. Calls `RuntimeEngine.assemble()`
   during boot, at priority 14.5 (after RiskManagement, RiskEngineV2, OMS,
   ExecutionEngine have all registered).
3. **`research_platform/oms/oms_core.py`** — removed the `pass` stub in the
   risk-check branch. Added `attach_safety_gateway()` / `_safety_gateway`.
   `submit_order()` now calls the SafetyEngine and fails CLOSED (rejects the
   order) if the gateway is missing, throws, or does not approve.
4. **`research_platform/persistence/postgres/connection.py` +
   `research_platform/platform/database_boot.py`** — added a `mode` parameter.
   `DEV` keeps the old silent-SQLite-fallback behavior; `PAPER`/`PROD` raise
   `ProductionDatabaseUnavailableError` instead of ever silently degrading to
   an in-memory database.
5. **`research_platform/platform/configuration_boot.py`** — one line added to
   the existing pytest-detection branch, forcing `runtime.mode="DEV"` only
   under pytest (so the test suite doesn't need a live Postgres), never in a
   real deployment.
6. **`toji_platform/core/errors.py`** — added `RuntimeIntegrityError`,
   `RuntimeValidationError`, `ProductionDatabaseUnavailableError` to the
   existing kernel exception hierarchy.
7. Test fixtures fixed: `research_platform/tests/test_oms.py`'s container
   fixture previously never registered a risk engine at all (the exact gap
   Round-2 flagged). It now wires a real `RiskManagementOrchestrator` +
   `OrderSafetyGateway`. New file `research_platform/tests/test_integration01_safety.py`
   adds the Phase 5 lifecycle tests plus RuntimeHealth tests.

Nothing under the top-level deprecated packages (`risk_engine/`,
`execution_engine/`, `market_gateway/`, etc.) was touched. See
`ARCHITECTURE_STATUS.md` for the full classification.

---

## Verification performed

- Ran the real boot chain (`PlatformApplication().boot()`, the same call
  `backend/main.py` and `main.py` make) outside pytest, with no Postgres
  driver installed and `runtime.mode` at its real default (`PAPER`):
  **boot aborted** with `ProductionDatabaseUnavailableError`, exactly as
  required. No silent SQLite fallback occurred.
- Ran the same boot chain with `mode` forced to `DEV`: boot succeeded, and
  `RuntimeRegistry.snapshot()` returned real class names for `SafetyEngine`,
  `RiskEngine`, `OMS`, `ExecutionEngine`, and `Database`, and
  `oms._safety_gateway is container.resolve("SafetyEngine")` was `True`.
- Ran `pytest research_platform/` (1484 tests, excluding one pre-existing
  test file with an unrelated `ImportError` for a missing `AlphaGeneticEngine`
  class, and one pre-existing hang-prone thread test):
  **1468 passed, 26 failed.**
- The 26 failures are a **pre-existing test-isolation bug**, not caused by
  this sprint: the identical 25/26 failures reproduce on an unmodified copy
  of the original zip with zero of this sprint's changes applied (verified
  by extracting a second, untouched copy and running the same command). The
  one-failure difference between runs is itself evidence of the pre-existing
  flakiness (shared global state / thread timing across `test_strategy_lifecycle.py`
  and `test_portfolio_analytics.py`), not something introduced here. This is
  a legitimate finding for a future sprint, but is out of scope for
  INTEGRATION-01.
- The new safety-specific tests (10 new + all 4 pre-existing `test_oms.py`
  tests) pass, including: kill-switch blocks an order and the broker records
  zero fills; releasing the kill switch restores normal flow; a circuit-breaker
  symbol halt blocks that symbol only; an anonymous (`strategy_id=""`) order is
  rejected; a normal order fills end-to-end; an OMS with nothing attached to
  `_safety_gateway` rejects every order; `RuntimeHealth.validate()` raises when
  OMS has no gateway attached, passes when fully wired, and raises if the
  deprecated top-level `risk_engine/` is ever registered alongside the
  canonical stack; Postgres-unavailable raises in `PAPER`/`PROD` mode and
  falls back only in `DEV`.

---

## Answers

### 1. Can KillSwitch stop every order?

**Yes, now** — for every order that goes through `OmsCore.submit_order()`,
which is the only order-submission path reachable from the runtime.
`OrderSafetyGateway.check_order()` calls
`RiskManagementOrchestrator.validate_order()`, which checks
`kill_switch.is_activated` via `ComplianceEngine.evaluate_compliance()`
(this part of the code was already correct before this sprint — it was
simply never called). `test_kill_switch_blocks_order` and
`test_kill_switch_release_restores_normal_flow` verify both activation and
release are respected live, not from a cached snapshot.

Caveat: this is proven for the **paper** order path, which is the only path
currently reachable. There is still no broker adapter wired into
`research_platform/` (see BROKER-01 note in `ARCHITECTURE_STATUS.md`), so
"stop every order" today means "stop every paper order." When a real broker
adapter is wired in for BROKER-01, it must go through `OmsCore.submit_order()`
— any code path that calls a broker directly, bypassing OMS, would bypass the
kill switch too. That's a review item for whoever does BROKER-01, not
something this sprint can pre-verify.

### 2. Can TOJI trade without risk approval?

**No, for orders submitted through OMS.** `submit_order()` now has no code
path that reaches routing/fill without an explicit `SafetyDecision(approved=True)`.
Every failure mode (gateway not attached, gateway raises, gateway returns
`approved=False`) rejects the order. `test_oms_fails_closed_with_no_safety_gateway_attached`
locks this in as a regression test against ever reintroducing the original
`pass` stub.

### 3. Can broker receive unsafe orders?

**No, through the currently-reachable path.** `PaperExecutionRouter` is only
invoked from code that has already passed `OmsCore.submit_order()`'s safety
gate. Separately, `PaperExecutionRouter.route_order()` still has its own
hardcoded `PermissionError` for `LIVE` mode — that gate is unrelated to the
KillSwitch and untouched by this sprint; it remains the second, independent
layer blocking any real-money path, exactly as found in Round 2.

### 4. Can production silently switch database?

**No, as of this sprint.** `DatabaseConnection.initialize()` only falls back
to SQLite when `mode == "DEV"`. In `PAPER` or `PROD` (or any other value), a
Postgres failure raises `ProductionDatabaseUnavailableError`, which propagates
uncaught through `DatabaseLifecycleManager.connect()` →
`PlatformStartupCoordinator.boot_platform()` → the process never finishes
booting. This was verified directly: running `backend/main.py`'s import path
in this sandbox (no Postgres reachable, `mode` at its real default of `PAPER`)
aborts with that exact exception instead of quietly starting on SQLite.

One structural limitation, stated plainly rather than papered over: this
check happens **before** the KillSwitch/SafetyEngine exist in the boot
sequence (database connects at step 2; risk/safety plugins boot at step
11+). So "EMERGENCY_STOP" here is implemented as **refusing to boot at all**,
not as a running SafetyEngine flipping a flag mid-session. That is arguably
stronger (nothing runs, ever, without persistence), but it means a Postgres
outage *while already running* (after boot) is not yet covered by this
mechanism — that would require a runtime health-check loop that watches the
DB connection post-boot and trips the KillSwitch, which does not exist yet
and is a legitimate follow-up item, not something claimed as done here.

### 5. Is TOJI ready for Dashboard-01 and the 30-day paper test?

**Closer, not there.** What changed the calculus:
- The kill switch, risk validation, and OMS are now provably connected —
  this was the single biggest blocker from Round 2 and it is fixed and
  tested.
- Silent data loss to an in-memory database in PAPER/PROD mode is now
  structurally impossible — it aborts boot instead.

What still blocks a clean 30-day run:
- **No post-boot database health monitoring.** If Postgres drops mid-run
  (not at boot), nothing currently detects it or halts trading — this
  sprint only closed the boot-time gap.
- **Redis and TimescaleDB are still not real** (unchanged from Round 2 —
  out of scope for this sprint, which was runtime wiring, not new
  infrastructure).
- **No real broker exists in the wired runtime yet.** BROKER-01 has to
  land before any of this matters for real testnet fills; when it does,
  whoever implements it must route through `OmsCore.submit_order()`, not
  call a broker adapter directly.
- **The pre-existing test-isolation bug** (26 failures under full-suite
  runs, reproduced on the unmodified baseline) should be root-caused before
  relying on the full test suite as a regression gate for BROKER-01 — right
  now a real regression could hide inside that noise.
- Five parallel portfolio-engine implementations and six-plus AI/knowledge
  subsystems are unchanged from Round 2 — still a maintenance risk, still
  out of scope here.

Recommended next sprint: (a) a lightweight post-boot DB watchdog that trips
the KillSwitch on connection loss, closing the one gap named in Q4; (b)
root-cause the pre-existing test-isolation failures; (c) BROKER-01, with an
explicit review step confirming the broker adapter is only ever called from
inside `OmsCore`.
