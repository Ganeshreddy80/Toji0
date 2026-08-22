# Sprint 000 — Project Baseline Sprint

> **Document Type:** Sprint Execution Plan  
> **Sprint ID:** SPRINT-000  
> **Sprint Name:** Project Baseline & Discovery  
> **Owner:** Senior Technical Program Manager / CTO Office  
> **Status:** Not Started  
> **Execution Constraint:** Pure Discovery & Audit (Zero Code Implementation)  

---

## Purpose

The purpose of **Sprint 000** is to perform a comprehensive, non-invasive discovery and baseline audit of the existing TOJI repository, runtime architecture, configuration inventory, and risk controls. This sprint establishes the foundational metrics and architectural baselines necessary to execute Phase 0 and Phase 1 of the master roadmap without modifying any application source code or Python scripts.

---

## Objectives

1. Complete a full static analysis and structural inventory of all repository artifacts, entry points, and module interfaces.
2. Document existing module dependency trees, runtime execution call graphs, and configuration entry points.
3. Map current system data flows from market ingestion through strategy routing, risk calculation, position management, and order execution.
4. Establish baseline metrics for code coverage, static linting scores, security vulnerability scans, and documentation coverage.
5. Define formal governance standards and verification gates for upcoming execution sprints.

---

## Scope

### In-Scope (Discovery & Audit Only)
- Static code inspection and directory layout mapping across all sub-packages (`backend/`, `confluence/`, `execution_engine/`, `market_gateway/`, `portfolio_engine/`, `risk_engine/`, `strategy/`, etc.).
- Audit of configuration management (`.env`, `.env.example`, Pydantic settings schema analysis).
- Analysis of test coverage and existing test suite structure (`tests/`, `confluence/tests/`).
- Mapping of runtime startup sequences and entry-point scripts (`main.py`, `strategy_router.py`, `run_paper_trade_verification.py`, `storage_audit.py`).
- Security static analysis (secret detection, baseline checks).

### Out-of-Scope (Strictly Prohibited)
- Writing, editing, or refactoring any application source code.
- Modifying or creating any Python (`.py`) files.
- Modifying existing unit/integration test logic or execution behavior.
- Altering database schemas or configuration files.
- Deploying services or initiating live exchange network connections.

---

## Deliverables

1. **Repository Inventory & Architecture Audit Report:** Detailed taxonomy of all repository components, file lines of code (LOC), and sub-system responsibilities.
2. **Runtime Boot & Dependency Graph Document:** Visual and textual map of process startup order, module import dependencies, and circular dependency flags.
3. **Trading Data Flow Map:** Documented signal path tracing from tick intake to order dispatch and risk checks.
4. **Configuration & Secrets Audit Summary:** Assessment of environment variable usage, secret isolation, and missing configuration defaults.
5. **Quality & Test Coverage Baseline Baseline:** Metric report capturing current test pass rate, code coverage percentage, and static lint error inventory.

---

## Acceptance Criteria

1. **Zero Code Mutations:** 100% of discovery deliverables produced without altering any source code or Python files.
2. **Comprehensive Inventory:** 100% of top-level directories and core modules documented with clear domain ownership.
3. **Boot Order Verification:** System boot sequence completely mapped from entry-point invocation through sub-service initialization.
4. **Risk & Dependency Identification:** All circular imports, legacy entry points, and single-points-of-failure cataloged for Phase 0 execution.
5. **Stakeholder Alignment:** Discovery artifacts reviewed and signed off by the TPM and Lead Architect.

---

## Verification

- **Static Inspection:** Verify file creation using git/filesystem status to ensure no files outside `docs/program_management/` were touched.
- **Checksum Verification:** Confirm source code file hashes remain identical before and after Sprint 000 completion.
- **Audit Verification:** Verify all deliverables (reports, dependency maps, baseline metrics) are linked and indexed in the program management store.

---

## Rollback Plan

Since Sprint 000 is strictly a read-only discovery sprint:
- **Trigger:** Any unintended modification or accidental mutation of source files during discovery.
- **Action:** Execute `git checkout -- .` and `git clean -fd` to revert working directory immediately to pre-sprint state.
- **Escalation:** Report any scope breach to the Technical Program Manager for immediate review.

---

## Risks

| Risk ID | Description | Impact | Likelihood | Mitigation Strategy |
| :--- | :--- | :--- | :--- | :--- |
| **R-000-1** | Accidental edit or formatting change to source files during discovery | Medium | Low | Maintain strict read-only file access during analysis; verify via git status. |
| **R-000-2** | Hidden side-effects triggered by running inspection tools or scripts | High | Low | Conduct discovery using static AST analysis and code inspection tools only. |
| **R-000-3** | Incomplete identification of circular import paths due to dynamic imports | Medium | Medium | Utilize static analyzer call-graph trees to inspect dynamic import sites. |

---

## Dependencies

- Approval of `docs/roadmap/TOJI-ROADMAP.md` as the single source of truth.
- Access to the target codebase repository (`toji-main 3`).
- Read-only execution privileges for static audit tools.

---

## Completion Checklist

- [ ] Repository structural inventory completed and documented.
- [ ] Runtime startup sequence call-graph mapped (`main.py` -> modules).
- [ ] Trading pipeline signal flow traced and documented.
- [ ] Environment variable and secrets security baseline completed.
- [ ] Static test coverage and quality baselines recorded.
- [ ] Final Sprint 000 summary report presented to CTO office.
- [ ] Zero source code or Python file modifications confirmed.
