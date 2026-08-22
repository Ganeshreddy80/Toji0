# Paper Trading Operational Guide

Guides continuous paper trading executions on virtual servers.

## Monitoring Status Logs
Review structural logs located in `./logs/system.log`. In case of high CPU warnings or drawdown alerts, Webhooks are automatically dispatched to alert receivers.

## Recovery Procedures
If the trading process terminates abruptly:
- Systemd automatically restarts the service.
- On boot, `RecoveryPlugin` intercepts startup and calls `execute_recovery()`, rolling back state variables.
- Trading loops resume where they left off without manual interventions.
