# ARCHITECTURE_STATUS.md

Generated as part of **INTEGRATION-01**. This file is the source of truth for
"is this code actually running?" Nothing was deleted. Status is derived
mechanically, not from documentation:

- **ACTIVE_RUNTIME** — reachable from `backend.main:app` / `main.py` →
  `research_platform.platform.bootstrap.bootstrap_platform()` →
  `PlatformStartupCoordinator.boot_platform()` → the plugin loader, which
  only discovers `research_platform/<pkg>/plugin.py` files. Verified by
  actually booting the platform (see `integration01_report.md`).
- **EXPERIMENTAL** — present in the repository, imported by nothing in the
  active runtime, but not a duplicate of an active module either (dev
  tooling, scaffolding, or an in-progress subsystem with no `plugin.py`
  yet).
- **DEPRECATED** — a duplicate implementation of a concern that already has
  an ACTIVE_RUNTIME equivalent. Never imported by `research_platform/`
  (confirmed by grep — zero cross-references in either direction, other
  than one shared schema module noted below).

Re-verify this file any time a `plugin.py` is added/removed, since it can go
stale otherwise: `find research_platform -maxdepth 2 -name plugin.py`.

---

## ACTIVE_RUNTIME

### Kernel (always boots first)
- `toji_platform/core/event_bus/` — InMemoryEventBus
- `toji_platform/core/dependency_injection/` — Container
- `toji_platform/core/configuration/`
- `toji_platform/core/errors.py`
- `toji_platform/runtime/` — **new in INTEGRATION-01**: RuntimeRegistry, RuntimeHealth, RuntimeEngine, OrderSafetyGateway

### Boot framework
- `research_platform/platform/` — bootstrap, startup, plugin_loader, database_boot, configuration_boot, container_boot, eventbus_boot, service_registry, shutdown, application
- `research_platform/config/` — ConfigManager (R51)
- `research_platform/persistence/` — Postgres/SQLite connection, session, migrations, repositories (imported directly by `platform/database_boot.py` and by every repository-backed orchestrator)
- `research_platform/security/` — RBAC/API-key middleware, imported directly by `backend/main.py`
- `research_platform/runtime_integration/` — **new in INTEGRATION-01**: the one auto-discovered plugin that assembles the SafetyEngine and attaches it to OMS

### Domain plugins (auto-discovered via `research_platform/<pkg>/plugin.py`, 60 total)
ai_intelligence, ai_signal, alerting, alpha_factory, backtesting_engine,
config, configuration, confluence, data_platform, deployment,
execution_engine, execution_simulator, experiment_management,
experiment_manager, feature_platform, governance, institutional_memory,
knowledge_graph, live_trading, logging, market_regime, metrics, monitoring,
multi_agent, multi_timeframe, observability, **oms**, operations_center,
optimization_engine, paper_dashboard, paper_market, paper_trading,
portfolio_analytics, portfolio_construction, portfolio_engine,
portfolio_intelligence, portfolio_optimizer, price_action, recovery,
reporting, research_intelligence, research_lab, **risk_engine_v2**,
**risk_management**, runtime, runtime_integration, scheduler, simulation,
strategy_framework, strategy_lab, strategy_lifecycle, strategy_registry,
stress_testing, system_validation, toji_os, trade_journal, validation,
validation_core, walk_forward, workflow_orchestration

**Safety-critical subset (verified end-to-end in this sprint):**
- `research_platform/risk_management/` — **canonical RiskEngine**: KillSwitch, ComplianceEngine, VaR/CVaR/leverage engines, `RiskManagementOrchestrator.validate_order()`
- `research_platform/risk_engine_v2/` — CircuitBreaker (companion check, not competing — see Phase 2 below), Kelly sizing, exposure manager
- `research_platform/oms/` — `OmsCore`, now with a mandatory, fail-closed `_safety_gateway` attachment point
- `research_platform/execution_engine/` — thin orchestrator registered in the container (the real broker adapter is NOT here — see DEPRECATED)
- `research_platform/paper_market/`, `research_platform/paper_trading/` — the only order-routing/broker path currently reachable at runtime

### Entrypoints
- `backend/main.py` (uvicorn target, used by `docker/Dockerfile` CMD)
- `main.py` (headless run)

### Data schemas (partial — one file only)
- `data/schemas/market_data.py` — imported by `research_platform/data/dataset.py` and its own tests. This is the ONLY file under the top-level `data/` package that is actually reachable from the active runtime. The rest of top-level `data/` is unverified and should be treated as EXPERIMENTAL until checked.

---

## EXPERIMENTAL

In-repo, not auto-discovered, not a duplicate of anything active. Not
booted, not tested against the live runtime, not safety-relevant today.

- `research_platform/ai_copilot/` — no `plugin.py`, not registered anywhere
- `research_platform/workspace/` — no `plugin.py`, not registered anywhere
- `research_platform/scratch/` — developer audit/lint scripts (`audit_*.py`, `lint_checker.py`, `simulation_runner.py`), not production code, not imported by anything
- `data/` (top-level, minus `data/schemas/market_data.py` above) — unverified

---

## DEPRECATED

Duplicate implementations of a concern that already has an ACTIVE_RUNTIME
equivalent inside `research_platform/`. Confirmed via cross-reference grep:
**zero** files under `research_platform/` import any of the packages below,
and these packages have no `plugin.py`, so the plugin loader never touches
them. Do not delete per sprint instructions — but do not add features to
them either; any new work belongs in the ACTIVE_RUNTIME equivalent.

| Deprecated (top-level) | Concern | ACTIVE_RUNTIME equivalent |
|---|---|---|
| `risk_engine/` | Risk / kill switch | `research_platform/risk_management/` |
| `execution_engine/` | Order execution, EMS algos, Binance broker adapter | `research_platform/execution_engine/` + `research_platform/oms/` (broker adapter itself is not yet migrated — see BROKER-01 note below) |
| `market_gateway/` | Exchange connectivity (the real Binance provider lives here) | none active yet — this is the gap BROKER-01 needs to close |
| `universe/` | Asset discovery/ranking | no active equivalent found |
| `strategy/`, `decision/` | Strategy signal generation | `research_platform/ai_signal/`, `research_platform/strategy_lifecycle/`, `research_platform/strategy_framework/` |
| `portfolio_engine/`, `position_sizing/` | Portfolio construction/sizing | `research_platform/portfolio_engine/`, `portfolio_analytics/`, `portfolio_construction/`, `portfolio_intelligence/`, `portfolio_optimizer/` (five active implementations — still needs consolidation, out of scope for this sprint) |
| `confluence/`, `price_action/` (top-level) | Signal confirmation | `research_platform/confluence/`, `research_platform/price_action/` |
| `orchestrators/`, `agents/` | Generic orchestration | `research_platform/platform/` (RuntimeEngine, PlatformStartupCoordinator) |
| `intelligence/`, `market_intelligence/`, `memory/`, `knowledge/`, `trading_context/` | AI/knowledge subsystems | `research_platform/ai_intelligence/`, `ai_signal/`, `institutional_memory/`, `knowledge_graph/` (still fragmented — out of scope for this sprint) |
| `prompts/`, `workflows/`, `analytics/`, `mcp/` | Misc | no clear single equivalent — flagged for a future consolidation pass |
| `dashboard/` (top-level) | Web dashboard | unclear — no `plugin.py`; needs a manual check of whether it is a separate standalone service (out of scope here) |

**Important nuance:** `market_gateway/` (top-level, real Binance websocket
provider) and `execution_engine/` (top-level, real Binance broker adapter +
EMS algos) contain the most complete, non-trivial working code of any
deprecated module. They should be **migrated into `research_platform/`**,
not deleted, when BROKER-01 is scheduled — this status file marks them
DEPRECATED only in the sense of "not currently wired," not "throwaway."
