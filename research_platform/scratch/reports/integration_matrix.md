# TOJI V1 Integration Matrix

This report maps the interaction surfaces between core infrastructure subsystems and domain-level quantitative components.

| Component / Subsystem | Configuration (R51) | Logging (R52) | Validation (R53) | Alerting (R54) | Metrics (R55) | Scheduler (R56) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **OMS** | Loaded at boot | Logs filled trades | Checked for neg bal | Dispatched alerts | Tracks open orders | Evaluates schedules |
| **Portfolio** | Bounds validated | Audits weights | Validates sum ~1.0 | Alerts drawdown | Measures value | Rebalances |
| **Strategy** | Param defaults | Logs triggers | Checked for active | Warnings on fail | Counts strategies | Triggers workflows |
| **Runtime** | Mode checks | Audit execution | Heartbeat checked | Alerts anomalies | Latency telemetry | Main ticks run |
