# TOJI Production Fix Plan

This document outlines the step-by-step remediation plan to resolve the blockers identified during the Production Readiness Audit.

---

## Remediations

### 1. Resolve Supervisor Deadlock

*   **Problem**: `stderr=subprocess.PIPE` without reading locks the paper runner.
*   **Fix**: Modify `scripts/runtime_supervisor.py` to either:
    1.  Omit `stderr=subprocess.PIPE` (allow it to write to supervisor's inherited stderr).
    2.  Use a background thread that continuously reads and outputs lines from the child's `stderr` stream.

---

### 2. Wire Up Risk Governance & Execution Engines

*   **Problem**: New safety and simulator files exist but are never executed during paper trading.
*   **Fix**:
    - Update `scripts/run_paper_trading.py` to route orders through the new `ExchangeExecutionSimulator` instead of bypassing it.
    - Wire `AIDecisionAuditor` into `run_paper_trading.py`'s tick loop right before the `submit_order` call:
      ```python
      auditor = AIDecisionAuditor()
      decision = auditor.audit(ai_signal, regime="TRENDING")
      if not decision.approved:
          # reject signal and alert
      ```
    - Replace/extend the OMS compliance check with the new `KillSwitchEngine` evaluate logic.

---

### 3. Persist Risk State to Redis

*   **Problem**: Restarts reset `HALTED` and `WARNING` safety states to `NORMAL`.
*   **Fix**:
    - Modify `RuntimeStateManager` and `KillSwitchEngine` to serialize the current switch state (`NORMAL`, `WARNING`, `REDUCED_RISK`, `HALTED`) and daily accumulated loss metrics to Redis under `TOJI:risk_state`.
    - On reboot, the supervisor and runner must call `load()` to populate the initial state.

---

### 4. Connect Risk Alerts to Telegram

*   **Problem**: Halted states and risk exceptions never post to Telegram.
*   **Fix**:
    - Connect the `_alert_callback` of `KillSwitchEngine` to the `send_telegram_alert` helper in `run_paper_trading.py`.
