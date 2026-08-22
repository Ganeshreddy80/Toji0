# RESEARCH ↔ TRADING PARITY PLAN

**Author:** TOJI CTO / Lead Architect  
**Date:** 2026-08-10T13:43:00Z  
**Governance:** Master Architecture Governance — Phase 9 Definition Document  
**Status:** DESIGN ONLY — Not to be implemented until Phases 3–8 are complete and certified.

---

## 1. THE PROBLEM

The research and paper trading paths currently use **incompatible strategy models**:

| Path | Strategy Model | Used In |
|---|---|---|
| Research / Backtest | `research_platform.strategy_lab.models.StrategyDefinition` | `BacktestingEngineOrchestrator`, `StrategyLabOrchestrator`, `OptimizationEngineOrchestrator` |
| Paper Trading | `research_platform.strategy_framework.models.ComposedStrategy` | `StrategyComposer`, `scripts/run_paper_trading.py` |

This means a strategy validated in backtesting cannot be directly transferred to paper trading — it must be manually re-specified in a different schema. This creates risk of specification drift.

---

## 2. TARGET ARCHITECTURE

The final parity architecture must ensure:

```
                CANONICAL STRATEGY CONTRACT
                          │
                +---------+---------+
                │                   │
             RESEARCH             PAPER
                │                   │
           Backtest              Runtime
           Walk-Forward          Tick Loop
           Monte Carlo           Risk Gate
           Optimization          OMS
                │                   │
                +---------+---------+
                          │
                   Same semantics
                   Same parameters
                   Same rule evaluation
                   Same decision output
```

---

## 3. INFORMATION FLOW TARGET

```
                   MARKET DATA
                       │
               +-------+-------+
               │               │
            RESEARCH          PAPER
               │               │
          Historical         Live Market
               │               │
           Replay              │
               │               │
           Strategy ←----------+ (shared contract)
               │
           Backtesting
               │
       Walk-Forward / Monte Carlo
               │
        Strategy Qualification
               │
               +────→ Paper
                         │
                     Results
                         │
                         +────→ Research Feedback
```

---

## 4. PARITY REQUIREMENTS

1. **Identical signal generation:** Given the same market input, the research path and paper trading path must produce the same strategy decision (BUY/SELL/HOLD).
2. **Identical position sizing:** Position sizing rules must be shared or provably equivalent.
3. **Identical risk gates:** Risk evaluation logic must be shared or provably equivalent.
4. **Deterministic execution:** Both paths must produce identical outputs for identical inputs.

---

## 5. IMPLEMENTATION APPROACH (FUTURE PHASE 9)

1. **Audit** both `StrategyDefinition` and `ComposedStrategy` for structural overlap.
2. **Define** a `CanonicalStrategyContract` (interface/base class) covering:
   - Strategy ID, name, type, version, symbols, parameters.
   - Entry rule evaluation method.
   - Exit rule evaluation method.
   - Position sizing rule.
   - Risk constraint expression.
3. **Adapt** `StrategyDefinition` and `ComposedStrategy` to implement or extend `CanonicalStrategyContract`.
4. **Update** `BacktestingEngineOrchestrator` and `StrategyComposer` to consume `CanonicalStrategyContract`.
5. **Regression test** both paths produce identical decisions for identical inputs.
6. Only after full test certification, deprecate and eventually remove the redundant model.

---

## 6. QUALIFICATION GATE (FUTURE)

A strategy must pass all of the following before entering paper trading:

| Gate | Criterion |
|---|---|
| Backtest Sharpe ≥ 1.0 | On in-sample data |
| Walk-Forward Robustness ≥ 0.7 | Out-of-sample performance retention |
| Max Drawdown ≤ 20% | Over walk-forward period |
| Monte Carlo 95th percentile positive | Over 1,000 simulations |
| Stress test pass | Under volatility shock scenarios |
| Paper trading warm-up pass | 7-day paper run with no critical failures |

**This gate is NOT implemented now.** Defined here for Phase 9 planning.

---

## 7. CURRENT STATUS

- Research ↔ Trading parity: **NOT STARTED** (Phase 9).
- No changes will be made to research modules during Phases 3–8.
- The strategy semantic gap is documented, not acted upon.
