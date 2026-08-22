# Sprint Report — TOJI Sprint OPS-01 (Continuous Paper Trading Runtime)

## Executive Summary
This sprint establishes continuous execution capability for the TOJI algorithmic trading platform. It introduces a continuous runner script, a persistent telemetry-backed state manager, a multi-threaded heartbeat auditing daemon, external news parsing capabilities with containment boundaries, and strict LLM policy gates blocking model-directed trading and risk parameter modifications.

---

## Deliverables

### 1. Paper Trading Runner (`scripts/run_paper_trading.py`)
- Coordinates boot sequences for all 10 core subsystems via DI container bootstrapping.
- Replaces default live market tick listeners with a sequential execution pipeline:
  `Market Tick → Normalize → Feature calculation → Price Action → Strategy composer → AI signal confluence → OMS validation → Paper execution matching`.
- Intercepts signals (`SIGINT` and `SIGTERM`) to trigger graceful shutdowns (suspending tick ingestion, executing active fills, saving final state, disconnecting database, and sending notifications).

### 2. Runtime State Manager (`toji_platform/runtime/state.py`)
- Implements state transition flow: `STARTING`, `RUNNING`, `DEGRADED`, `STOPPING`, `STOPPED`, `ERROR`.
- Telemetry telemetry counters tracking runtime parameters: processed ticks, signals generated, paper trades executed, and errors.
- Serializes telemetry in Redis keys: `TOJI:runtime_status`, `TOJI:last_heartbeat`, `TOJI:processed_ticks`, `TOJI:runtime_stats`.

### 3. Heartbeat System (`toji_platform/runtime/heartbeat.py`)
- Daemon checking core subsystem statuses:
  - Database status
  - Redis status
  - Market simulation feed active
  - OMS instance status
  - Risk engine active status
  - Process memory usage (RSS via `psutil`)
- Dispatches status messages via Telegram alerting channel on a 60-second cycle.

### 4. News Provider (`research_platform/news/news_provider.py`)
- Fetches and normalizes news articles, parsing title, source, publication date, and keyword-based sentiments (`BULLISH`, `BEARISH`, `NEUTRAL`).
- Contains all outputs as explainability meta-parameters; strictly forbids ingestion for order execution, complying with absolute risk isolation rules.

### 5. AI Safety Usage Rules (`research_platform/ai_signal/usage_rules.py`)
- Implements `AIUsageController` validating LLM/agentic commands.
- Permits `explain_trade`, `summarize_market`, `analyze_performance`, and `generate_report`.
- Forbids and raises `PermissionError` for capabilities trying to invoke `submit_order`, `change_risk`, `disable_safety`, or `enable_live_mode`.

---

## Verification Results

All 7 suite scenarios pass successfully, showing perfect validation of the runtime components:

```
tests/runtime/test_paper_runner.py::test_runner_boots_all_services PASSED
tests/runtime/test_paper_runner.py::test_runtime_heartbeat_updates PASSED
tests/runtime/test_paper_runner.py::test_ctrl_c_shutdown_safe PASSED
tests/runtime/test_paper_runner.py::test_market_tick_loop_running PASSED
tests/runtime/test_paper_runner.py::test_openrouter_cannot_trade PASSED
tests/runtime/test_paper_runner.py::test_news_cannot_trade PASSED
tests/runtime/test_paper_runner.py::test_crash_recovery PASSED

======================== 7 passed in 4.36s =========================
```

The entire repository regression suite was executed, achieving 100% compliance:
```
====================== 902 passed in 15.44s =======================
```

---

## Tradeoffs and Architectural Design Decisions
- **Custom Tick Listener Loop**: Rather than relying on default live trading plugin bindings, the runner overrides bindings to force step-by-step pipeline ordering, avoiding race conditions or duplicates.
- **SQLite DB Fallback**: Under local testing conditions, the database connection is redirected to an in-memory SQLite schema, maintaining execution capabilities when PostgreSQL databases are offline.
- **Strict Compliance Enforcement**: All orders generated via the AI confluence flow pass through `oms_core.submit_order` validation rules and risk checks, preventing any possibility of bypassing safety nets.
