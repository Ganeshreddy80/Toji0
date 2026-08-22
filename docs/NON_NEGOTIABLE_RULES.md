# NON_NEGOTIABLE_RULES.md

> **Version:** 0.1.0  
> **Last Updated:** 2026-06-25  
> **Status:** Active — ENFORCED  
> **Owner:** Toji Core Team  

---

## Table of Contents

- [Purpose](#purpose)
- [Security Rules](#security-rules)
- [Code Quality Rules](#code-quality-rules)
- [Architecture Rules](#architecture-rules)
- [Process Rules](#process-rules)
- [Data Rules](#data-rules)
- [Documentation Rules](#documentation-rules)
- [Enforcement](#enforcement)

---

## Purpose

This document defines **inviolable constraints** that apply to all development on the Toji platform. These rules exist to protect the integrity, security, and quality of the system.

**Violation of any rule listed here is grounds for immediate PR rejection.**

---

## Security Rules

| # | Rule | Rationale |
|---|------|-----------|
| S1 | **No secrets in source code** | Secrets in code are the #1 cause of breaches |
| S2 | **No secrets in logs** | Log aggregation can expose credentials |
| S3 | **No disabled authentication in production** | Zero-trust is non-negotiable |
| S4 | **No raw SQL queries** | SQL injection prevention; use ORM/parameterized queries |
| S5 | **No user input in shell commands** | Command injection prevention |
| S6 | **All API endpoints authenticated** | Unless explicitly public (health checks only) |
| S7 | **All data validated at API boundary** | Never trust input |
| S8 | **TLS for all external communication** | Encryption in transit |

---

## Code Quality Rules

| # | Rule | Rationale |
|---|------|-----------|
| C1 | **All code must pass linting** | Consistent code quality |
| C2 | **All code must pass type checking** | Runtime safety via static analysis |
| C3 | **All public functions must have docstrings** | Maintainability and onboarding |
| C4 | **All public functions must have type hints** | Self-documenting interfaces |
| C5 | **No `print()` statements** | Use structured logging |
| C6 | **No `TODO` without issue reference** | Track all tech debt |
| C7 | **No `# type: ignore` without comment** | Justify all suppressed warnings |
| C8 | **Test coverage ≥80% on new code** | Quality assurance |

---

## Architecture Rules

| # | Rule | Rationale |
|---|------|-----------|
| A1 | **No circular imports** | Clean dependency graph |
| A2 | **No hardcoded configuration** | All config via env/files |
| A3 | **No direct database access from API routes** | Use service/repository layer |
| A4 | **No business logic in API routes** | Routes are thin adapters |
| A5 | **No global mutable state** | Use dependency injection |
| A6 | **No synchronous blocking in async code** | Use `asyncio` properly |
| A7 | **Every module must have `__init__.py`** | Explicit package structure |

---

## Process Rules

| # | Rule | Rationale |
|---|------|-----------|
| P1 | **No direct pushes to `main`** | All changes via pull request |
| P2 | **No merges without passing CI** | Automated quality gate |
| P3 | **No merges without code review** | Human quality gate |
| P4 | **Conventional Commits required** | Automated changelog generation |
| P5 | **All PRs must reference an issue** | Traceability |
| P6 | **Breaking changes require RFC** | Impact assessment |
| P7 | **All deployments via CI/CD** | No manual deployments |

---

## Data Rules

| # | Rule | Rationale |
|---|------|-----------|
| D1 | **No production data in development** | Data privacy |
| D2 | **All migrations must be reversible** | Safe rollbacks |
| D3 | **No schema changes without review** | Data integrity |
| D4 | **All data deletions are soft-delete** | Audit trail preservation |
| D5 | **PII encrypted at rest** | Compliance |

---

## Documentation Rules

| # | Rule | Rationale |
|---|------|-----------|
| O1 | **All API changes require doc updates** | Documentation accuracy |
| O2 | **All architecture changes require ADR** | Decision traceability |
| O3 | **All breaking changes logged in CHANGELOG** | User communication |
| O4 | **README must reflect current state** | First impression matters |

---

## Enforcement

These rules are enforced through:

1. **Pre-commit hooks** — Automated checks before every commit
2. **CI pipeline** — Automated checks on every PR
3. **Code review** — Human verification on every PR
4. **Automated scanning** — Security and dependency checks
5. **Architecture review** — Periodic design review sessions

### Exceptions

Exceptions to any rule require:
1. Written justification in the PR description
2. Approval from at least two senior engineers
3. Documented in `ARCHITECTURE.md` as an ADR
4. Time-bound plan to resolve the exception
