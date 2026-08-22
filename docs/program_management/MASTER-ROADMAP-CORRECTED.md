# TOJI — MASTER PROGRAM ROADMAP (CORRECTED)

**Author:** TOJI CTO / Lead Architect  
**Date:** 2026-08-10T13:40:00Z  
**Governance:** Master Architecture Governance  
**Status:** GOVERNING DOCUMENT — Supersedes all previous partial roadmaps  

---

## MISSION

TOJI is a canonical quantitative trading platform targeting:

1. Deterministic, reproducible paper trading validated against live market data.
2. A research subsystem that qualifies strategies before they enter paper trading.
3. Long-running paper validation before any consideration of live trading.
4. Full persistence, restart/rehydration, and cloud-readiness.

**Live trading remains LOCKED** until all production-readiness gates pass.

---

## CANONICAL DATA FLOW PIPELINE

```
Market Data
    ↓
Price Action
    ↓
Features
    ↓
Strategy
    ↓
Confluence
    ↓
AI Signal
    ↓
Risk
    ↓
Position Sizing
    ↓
Portfolio
    ↓
OMS
    ↓
Paper Execution
    ↓
Accounting
    ↓
Persistence
```

**AND** a separate but integrated Research pipeline:

```
Historical / Recorded Data
    ↓
Data Preparation
    ↓
Feature Generation
    ↓
Price Action
    ↓
Strategy
    ↓
Backtest
    ↓
Walk-Forward
    ↓
Monte Carlo / Stress
    ↓
Performance Analysis
    ↓
Strategy Qualification
    ↓
Paper Trading
```

---

## NON-NEGOTIABLE ARCHITECTURAL RULES

1. **DO NOT** delete, merge, rename, or rewrite `research_platform`, `toji_platform`, duplicate engines, standalone `price_action/` modules, or research implementations during any phase.
2. **Consolidation process ONLY:** Discover → Compare → Select Canonical → Adapter/Migrate → Regression Test → Remove Obsolete (in a dedicated approved phase).
3. **Live trading LOCKED** until Phase 13 (Long-Running Paper Validation) is complete and certified.
4. **Neon PostgreSQL** = current transactional database (orders, trades, positions, ledger, account state).
5. **AWS/S3** = future scope only. No migration until paper runtime is stable and validated.
6. **Price Action MUST NOT** make trading decisions, place orders, bypass Risk, or access OMS.

---

## MASTER PROGRAM PHASES

| Phase | Name | Status | Gate |
|---|---|---|---|
| **PHASE 0** | Architecture Discovery | ✅ COMPLETE | Architecture audit certified |
| **PHASE 1** | Runtime Stabilization | ✅ COMPLETE | Sprint 001 regression suite passed |
| **PHASE 2** | Persistence + Neon PostgreSQL | ✅ COMPLETE | Live Neon atomic commit/rollback + rehydration verified |
| **PHASE 3** | Price Action | 🟡 READY — NOT IMPLEMENTED | CTO Correction Gate PASS |
| **PHASE 4** | Research Consolidation Discovery | 🔴 NOT STARTED | Research subsystem inventory complete |
| **PHASE 5** | Feature Pipeline | 🔴 NOT STARTED | Feature platform contracts verified |
| **PHASE 6** | Strategy + Confluence | 🔴 NOT STARTED | Strategy contract parity defined |
| **PHASE 7** | AI Signal | 🔴 NOT STARTED | AI signal integration traced |
| **PHASE 8** | Risk + Portfolio + Execution Integration | 🔴 NOT STARTED | Full tick-to-trade pipeline verified |
| **PHASE 9** | Research ↔ Trading Parity | 🔴 NOT STARTED | Shared strategy contract confirmed |
| **PHASE 10** | End-to-End Paper Trading | 🔴 NOT STARTED | First genuine paper trade verified |
| **PHASE 11** | Platform Consolidation | 🔴 NOT STARTED | Duplicate removal approved & regression-tested |
| **PHASE 12** | Cloud Architecture | 🔴 NOT STARTED | AWS deployment plan approved |
| **PHASE 13** | Long-Running Paper Validation | 🔴 NOT STARTED | 30-day paper run with zero critical failures |
| **PHASE 14** | Production Readiness | 🔴 NOT STARTED | All gates passed; live trading lock lifted |

---

## CURRENT CERTIFIED STATE (Evidence-Based)

### Sprint 001 (Phase 1)
- Runtime stabilization complete.
- Risk-state phantom constants removed.
- Risk gate is fail-closed when authoritative accounting state is unavailable.
- Critical plugin boot failures handled safely.
- OMS coexistence preserved.
- Paper fill pipeline traced and verified.

### Sprint 002 Phase 2
- Atomic trade + position + ledger transaction implemented.
- Database recovery failure masking fixed.
- PostgreSQL connection resilience improved.
- Neon PostgreSQL connectivity verified.
- Real PostgreSQL atomic commit test: **PASSED**.
- Real PostgreSQL atomic rollback test: **PASSED**.

### Sprint 002 Phase 3
- Portfolio/accounting state rehydration implemented and verified.
- Real Neon PERSIST → STOP → START → REHYDRATE → VERIFY: **PASSED**.
- Accounting math verified (no double-subtraction of commissions): **PASS**.
- Quiet unit regression suite: **73+ PASSED, 0 FAILED**.

### Sprint 003 Pre-Implementation (Phase 3 Prep)
- Price Action CTO Correction Gate: **PASS**.
- Active canonical runtime: `research_platform/price_action/`.
- Standalone stack `price_action/`: preserved, unbooted, unreachable.
- `_bars` private coupling in `run_paper_trading.py:284`: **NOT YET FIXED** (identified, approved for fix in PA-2).
- Boot order clarified: `FeaturePlatformPlugin` (10) boots before `PriceActionPlugin` (10.1) in DI container; tick-loop invokes PA before Feature.

---

## NEXT IMPLEMENTATION ACTION

**SPRINT 003 → Stage PA-0 / PA-1 implementation.**

Prerequisite: Approval of this corrected master roadmap and all governance documents.

---

## DATABASE & STORAGE GOVERNANCE

| Store | Purpose | Status |
|---|---|---|
| **Neon PostgreSQL** | Orders, trades, positions, ledger, account state, metadata | ✅ Current |
| **AWS PostgreSQL/RDS** | Production migration candidate | 🔴 Future — NOT NOW |
| **Object Storage (S3)** | Historical datasets, backtest artifacts, research archives | 🔴 Future — NOT NOW |
