# RESEARCH SUBSYSTEM — COMPONENT INVENTORY

**Author:** TOJI CTO / Lead Architect  
**Date:** 2026-08-10T13:41:00Z  
**Governance:** Master Architecture Governance — Phase 4 Input Document  
**Method:** Source-level inspection only. No inference, no guessing.

---

## SCOPE

All components within `research_platform/` and top-level directories related to:
research, backtesting, simulation, walk-forward, Monte Carlo, validation,
experiment management, strategy evaluation, performance analytics, and
feature/strategy research.

---

## COMPONENT INVENTORY TABLE

| # | Component | Path | Primary Class | Responsibility | Runtime Reachable | DI Registered | Plugin | Tests |
|---|---|---|---|---|---|---|---|---|
| 1 | **Backtesting Engine** | `research_platform/backtesting_engine/` | `BacktestingEngineOrchestrator` | Event-driven backtest loop: historical replay, order matching, portfolio tracking, analytics | **YES** — booted in `startup.py` (priority 15), consumed by `optimization_engine` and `strategy_factory` | `BacktestingEngineOrchestrator`, `BacktestRepository` | `BacktestingEnginePlugin` | `test_backtesting_engine.py` |
| 2 | **Simulation Engine** | `research_platform/simulation/` | `SimulationOrchestrator` | Deterministic replay, what-if stress evaluations, paper order simulation, failure injection | **YES** — booted in `startup.py`, consumed by tests | `SimulationOrchestrator` | Plugin available | `test_simulation.py` |
| 3 | **Walk-Forward Engine** | `research_platform/walk_forward/` | `WalkForwardOrchestrator` | Rolling, expanding, and validation walk-forward splits; robustness scoring | **YES** — booted in `startup.py` | DI registered | Plugin available | Referenced in `test_research_execution.py` |
| 4 | **Stress Testing** | `research_platform/stress_testing/` | `StressTestingOrchestrator` | Monte Carlo scenario generation, volatility stress, drawdown recovery analysis | **YES** — booted in `startup.py` (priority 25) | DI registered | `StressTestingPlugin` | `test_research_sprint6_pipeline.py` |
| 5 | **Strategy Lab** | `research_platform/strategy_lab/` | `StrategyLabOrchestrator` | Research-grade strategy definition, builder, registry, position-sizing, and risk rules. **Primary consumer:** `BacktestingEngineOrchestrator` (imports `StrategyDefinition`) | **YES** — booted in `startup.py` | DI registered | Plugin available | `test_strategy_lab.py` |
| 6 | **Experiment Manager** | `research_platform/experiment_manager/` | `ExperimentManagerOrchestrator` | Strategy A/B experiments, comparison engine, ranking, reproducibility | **YES** — booted in `startup.py` (priority 23) | DI registered | `ExperimentManagerPlugin` | `test_experiment_management.py` |
| 7 | **Optimization Engine** | `research_platform/optimization_engine/` | `OptimizationEngineOrchestrator` | Hyperparameter optimization over backtests; calls `BacktestingEngineOrchestrator.run_backtest()` | **YES** — booted in `startup.py` (priority 16) | DI registered | `OptimizationEnginePlugin` | `test_optimization_engine.py` |
| 8 | **Research Lab** | `research_platform/research_lab/` | `ResearchLabOrchestrator` | Factor engine, hypothesis engine, indicator library, feature store for alpha research | **YES** — booted in `startup.py` | DI registered | Plugin available | `test_research_foundation.py` |
| 9 | **Portfolio Analytics** | `research_platform/portfolio_analytics/` | `PortfolioAnalyticsOrchestrator` | Sharpe, attribution, benchmark comparison, risk metrics (Sortino, Calmar, VaR), performance reporting | **YES** — booted in `startup.py` (priority 21) | DI registered | `PortfolioAnalyticsPlugin` | `test_portfolio_analytics.py` |
| 10 | **Validation** | `research_platform/validation/` | `ValidationOrchestrator` | Platform health checking: database, memory, latency, resource, integrity, burn-in, soak tests | **YES** — called post-boot in `startup.py:194-204` | `ValidationOrchestrator` | `ValidationPlugin` | `test_validation.py` |
| 11 | **Strategy Factory / Evaluator** | `research_platform/strategy_factory/` | `StrategyEvaluator` | Evaluates strategy candidates via backtests and qualifies for paper trading | Source-traced to `strategy_factory/evaluator.py` which imports `BacktestingEngineOrchestrator` | DI registered | Plugin available | Referenced in tests |
| 12 | **Top-level `backtesting/`** | `backtesting/engine.py` | `BacktestEngine` (7898 bytes) | Unknown — a standalone top-level backtesting engine separate from `research_platform/backtesting_engine/` | **NO** — not booted in `startup.py`; no callers found in runtime | None | None | None found in `tests/` |
| 13 | **Research Intelligence** | `research_platform/research_intelligence/` | `ResearchIntelligenceOrchestrator` | AI-powered research analysis and insight generation | **YES** — booted in `startup.py` | DI registered | Plugin available | `test_research_intelligence.py` |
| 14 | **Strategy Lifecycle** | `research_platform/strategy_lifecycle/` | `StrategyLifecycleOrchestrator` | Strategy lifecycle management: qualification, promotion, demotion, retirement | **YES** — booted in `startup.py` (priority 22) | DI registered | `StrategyLifecyclePlugin` | `test_strategy_lifecycle.py` |

---

## STANDALONE TOP-LEVEL `backtesting/` — ISOLATION EVIDENCE

Source file: `/Users/a.ganeshkumarreddy12/Downloads/toji-main 3/backtesting/engine.py` (7,898 bytes).

Grep result across all Python files for callers of this file: **No results** — no Python file in the repository imports from `backtesting/engine.py` or instantiates its class.

**Classification:** Orphaned standalone file. Preserved. Not booted. Not callable.  
**Risk:** Low — isolated, no callers.  
**Action:** Preserve until Phase 11 (Platform Consolidation).

---

## STRATEGY SEMANTIC GAP (CRITICAL FINDING)

**Finding:** `strategy_lab.models.StrategyDefinition` (used by `BacktestingEngineOrchestrator`) is a **separate model class** from `strategy_framework.models.ComposedStrategy` (used by paper-trading runtime).

These two models represent the same domain concept (a composed strategy) using different data structures:

| Model | Module | Used By |
|---|---|---|
| `StrategyDefinition` | `research_platform/strategy_lab/models.py` | `BacktestingEngineOrchestrator`, `StrategyLabOrchestrator`, `OptimizationEngineOrchestrator` |
| `ComposedStrategy` | `research_platform/strategy_framework/models.py` | `scripts/run_paper_trading.py`, `StrategyComposer`, paper trading runtime |

**This semantic gap must be resolved in Phase 9 (Research ↔ Trading Parity).**  
**No action taken now. Preserved as-is.**

---

## RESEARCH SUBSYSTEM SUMMARY

- **Total research-related modules in `research_platform/`:** 14 identified above.
- **Active (booted in `startup.py`):** 13 modules.
- **Orphaned standalone:** 1 (`backtesting/engine.py`).
- **Key architectural gap:** `StrategyDefinition` (research) ≠ `ComposedStrategy` (paper trading).
- **Key capability gaps:** No mechanism currently connects strategy qualification output to paper trading.
