# TOJI V1 — Quantitative Research & Continuous Paper Trading Platform

TOJI is an institutional-grade, event-driven quantitative trading platform designed for single-user paper trading campaigns on virtual private servers (VPS). It features automatic state checkpointing, crash recovery rollbacks, background health validation checks, and structured auditing logs.

## Platform Core Highlights
- **Layered Architecture**: Independent modules registered inside a custom Dependency Injection (DI) Container and decoupled via an InMemory Event Bus.
- **Continuous Soak-Testing**: Verified for months-long execution runs with minimal memory footprint and zero leakage.
- **Robust Recovery Sequences**: Sequence rollback restoring engine states, order maps, balances, and scheduled cron jobs.
- **Subsystem Auto-discovery**: Plugin loader scans directory patterns and boots resources chronologically.

## Workspace Structure
- `research_platform/platform/`: Configuration, container, and database bootstrappers.
- `research_platform/persistence/`: PostgreSQL schema mappings and repository boundaries.
- `research_platform/runtime/`: Continuously ticking trading steps scheduler.
- `research_platform/recovery/`: Integrity checker, crash detector, and state snapshot managers.
- `research_platform/validation/`: 14 continuous system status validation checkers.
- `research_platform/alerting/`: Cool-down rule alert engine notifying log/webhooks.
- `research_platform/metrics/`: Observability telemetry snapshot publisher.

## Getting Started
To bootstrap the platform engine and trigger continuous validation:
```python
from research_platform.bootstrap import bootstrap_platform, shutdown_platform

# Start platform
app = bootstrap_platform()

# Teardown platform
shutdown_platform()
```

## Running Tests
Run the integration and regression tests:
```bash
pytest research_platform/tests/ -v
```
