# RESEARCH SUBSYSTEM — CONSOLIDATION STRATEGY

**Author:** TOJI CTO / Lead Architect  
**Date:** 2026-08-10T13:42:00Z  
**Governance:** Master Architecture Governance — Phase 4 Planning Document  
**Status:** PLANNING ONLY — No consolidation will be performed until an approved later phase.

---

## 1. CONSOLIDATION PRINCIPLE

The correct consolidation process is:

```
DISCOVER
    ↓
COMPARE (source evidence only)
    ↓
SELECT CANONICAL IMPLEMENTATION
    ↓
ADAPTER / MIGRATE
    ↓
REGRESSION TEST
    ↓
REMOVE OBSOLETE IMPLEMENTATION (only after tests pass)
```

No step may be skipped. No merging without regression gates.

---

## 2. CURRENT DUPLICATE STATUS (Source Evidence)

| Duplicate | Path A | Path B | Overlap | Canonical Candidate | Status |
|---|---|---|---|---|---|
| Backtesting Engine | `research_platform/backtesting_engine/` | `backtesting/engine.py` | Both implement a backtest execution loop | `research_platform/backtesting_engine/` — booted, tested, integrated | `backtesting/engine.py` is orphaned, no callers |
| Price Action | `research_platform/price_action/` | `price_action/` | Both detect market structure | `research_platform/price_action/` — active runtime | `price_action/` is standalone, inactive |
| Strategy Model | `strategy_lab/models.StrategyDefinition` | `strategy_framework/models.ComposedStrategy` | Both represent a composed strategy | TBD — requires Phase 9 analysis | Gap exists; no removal planned now |

---

## 3. CONSOLIDATION PHASES

### Phase 4: Research Consolidation Discovery
**Goal:** Extend the inventory begun in `RESEARCH-SUBSYSTEM-INVENTORY.md` to a full cross-module dependency map.
- Map all imports between `research_platform/` modules.
- Identify which research modules depend on `toji_platform/` components.
- Identify which paper trading modules depend on research components.
- Record all shared domain models (if any).

### Phase 9: Research ↔ Trading Parity
**Goal:** Resolve the `StrategyDefinition` vs. `ComposedStrategy` semantic gap.
- Define a single **Canonical Strategy Contract** interface (likely a shared base class or adapter).
- All research modules (backtest, walk-forward, optimization) use the canonical contract.
- All paper trading modules use the canonical contract.
- Regression tests must prove both paths produce identical signal outputs for the same input.

### Phase 11: Platform Consolidation
**Goal:** Remove orphaned and superseded implementations after parity is proven.
- Only after Phase 9 is certified PASS.
- Target candidates: `backtesting/engine.py`, `price_action/` (after research_platform version is fully tested and proven equivalent or superior).
- Removal gated by: full regression suite pass + integration test pass + explicit CTO sign-off.

---

## 4. NON-NEGOTIABLE RULES

- **Do NOT delete** any duplicate during Phases 3–8.
- **Do NOT merge** `research_platform` and `toji_platform` namespaces during Phases 3–8.
- **Do NOT rename** modules or classes without a full import audit.
- Only consolidation steps explicitly approved in a gate document may be implemented.
