# TOJI Production Readiness Report

## Executive Summary

- **Status**: **NOT_READY**
- **Date**: 2026-07-06
- **Auditor**: Senior Quant Trading CTO & SRE

Despite the rich logical features and high test count (946 passed), the TOJI system is **not ready for testnet or production deployment** due to critical architectural gaps, a fatal supervisor deadlock bug, and memory-only safety gates.

---

## Production Readiness Scores

| Category | Score | Status | Key Issues |
|---|---|---|---|
| **Architecture** | **65/100** | Needs Attention | Newly built risk governance and institutional execution engines are **dead code** and are not wired into the actual continuous paper loop (`run_paper_trading.py`). |
| **Reliability** | **40/100** | **CRITICAL** | **Supervisor Deadlock**: Using `stderr=subprocess.PIPE` without reading freezes the paper trading engine after 26 ticks (64KB stderr buffer filled). |
| **Trading Logic** | **95/100** | Excellent | Tick normalisation, feature computation, and strategy composure are highly optimized. |
| **Risk Safety** | **50/100** | **CRITICAL** | **Halt Bypass on Restart**: Risk state is in-memory only. A supervisor restart reset halts, exposing the engine to unchecked trade loops. |
| **Testing Quality** | **75/100** | Good | 946 passing tests but heavily reliant on isolated mocks, hiding the lack of runtime wiring. |
| **Deployment Ready**| **NOT_READY** | **Blocked** | Deadlocks and unwired safety components must be resolved before live trading starts. |

---

## Major Blockers

### Blocker 1: Supervisor Deadlock
The supervisor runs `run_paper_trading.py` using:
```python
    engine_process = subprocess.Popen(
        engine_cmd,
        stderr=subprocess.PIPE,
        text=True
    )
```
Because `stderr` is piped but never drained while the process runs, the OS pipe buffer fills up within minutes (usually 64KB, which corresponds to the plugin startup prints and warnings). The child process then permanently blocks on the `write()` system call, stopping tick ingestion.

### Blocker 2: Unwired Governance and Execution Layers
The paper trading runner uses:
- The old `RiskManagementOrchestrator` instead of the new `KillSwitchEngine` / `RealTimeRiskMonitor`.
- The old `PaperMarketOrchestrator` routing instead of the institutional `ExchangeExecutionSimulator` (spread, taker fee, ATR slippage).
- The `AIDecisionAuditor` is completely skipped before order submission.

### Blocker 3: Risk State Reset
`KillSwitch` and `PositionGuardian` states do not persist to Redis. If the runner crashes or is restarted, it boots into the `NORMAL` state, even if trading was previously halted due to excessive drawdown or daily loss limits.

---

## Recommendation
**Do not deploy to testnet.** Implement the fixes outlined in `FIX_PLAN.md` immediately.
