# TESTING.md

> **Version:** 0.1.0  
> **Last Updated:** 2026-06-25  
> **Status:** Draft  
> **Owner:** Toji Core Team  

---

## Table of Contents

- [Purpose](#purpose)
- [Testing Strategy](#testing-strategy)
- [Test Pyramid](#test-pyramid)
- [Test Types](#test-types)
- [Testing Tools](#testing-tools)
- [Directory Structure](#directory-structure)
- [Coverage Requirements](#coverage-requirements)
- [CI Integration](#ci-integration)
- [Test Data Management](#test-data-management)
- [Best Practices](#best-practices)

---

## Purpose

This document defines the **testing strategy and standards** for the Toji platform. All code must be tested before merging to protected branches.

---

## Testing Strategy

Toji follows a **test-first development** approach:

1. Write tests before or alongside implementation
2. All public interfaces must have tests
3. Integration points tested with contract tests
4. End-to-end flows tested in staging environment

---

## Test Pyramid

```
        ╱╲
       ╱  ╲        E2E Tests (few, slow, high confidence)
      ╱────╲
     ╱      ╲      Integration Tests (moderate, medium speed)
    ╱────────╲
   ╱          ╲    Unit Tests (many, fast, isolated)
  ╱────────────╲
```

| Level | Ratio | Speed | Scope |
|-------|-------|-------|-------|
| Unit | 70% | <1s per test | Single function/class |
| Integration | 20% | <10s per test | Module interactions |
| E2E | 10% | <60s per test | Full system flows |

---

## Test Types

### Unit Tests
- Test individual functions and methods
- Mock all external dependencies
- Fast, isolated, deterministic
- Located alongside source in `tests/unit/`

### Integration Tests
- Test module boundaries and interactions
- Use test databases and services
- May use Docker containers
- Located in `tests/integration/`

### End-to-End Tests
- Test complete user flows
- Run against deployed services
- Located in `tests/e2e/`

### Property-Based Tests
- Test invariants with random inputs
- Use Hypothesis library
- Complement unit tests for complex logic

### Contract Tests
- Verify API contracts between services
- Prevent breaking changes
- Located in `tests/contract/`

---

## Testing Tools

| Tool | Purpose |
|------|---------|
| **pytest** | Test runner and framework |
| **pytest-cov** | Code coverage reporting |
| **pytest-asyncio** | Async test support |
| **hypothesis** | Property-based testing |
| **factory-boy** | Test data factories |
| **httpx** | Async HTTP client for API tests |
| **testcontainers** | Docker containers for integration tests |
| **pytest-mock** | Mocking utilities |

---

## Directory Structure

```
tests/
├── conftest.py              # Shared fixtures
├── unit/                    # Unit tests
│   ├── backend/
│   ├── agents/
│   ├── analytics/
│   ├── memory/
│   └── mcp/
├── integration/             # Integration tests
│   ├── api/
│   ├── database/
│   └── services/
├── e2e/                     # End-to-end tests
│   └── flows/
├── contract/                # Contract tests
├── fixtures/                # Shared test data
│   ├── factories.py
│   └── sample_data/
└── utils/                   # Test utilities
    └── helpers.py
```

---

## Coverage Requirements

| Module | Minimum Coverage |
|--------|-----------------|
| Backend API | 85% |
| Agents | 80% |
| Memory | 85% |
| Analytics | 80% |
| MCP | 80% |
| Overall | 80% |

### Coverage Enforcement

```bash
pytest --cov=. --cov-report=html --cov-fail-under=80
```

---

## CI Integration

<!-- TODO: Configure in Sprint 0 -->

### Pipeline Stages
1. **Lint** — ruff check, mypy
2. **Unit Tests** — Fast feedback (<5 min)
3. **Integration Tests** — Database and service tests (<15 min)
4. **Coverage Report** — Upload to coverage service
5. **E2E Tests** — Full system validation (staging only)

---

## Test Data Management

- Use factories (factory-boy) for test object creation
- Seed data via fixtures, not manual setup
- Test database reset between test suites
- No production data in tests
- Sensitive data replaced with realistic fakes

---

## Best Practices

1. **One assertion per test** — Keep tests focused
2. **Descriptive names** — `test_should_return_404_when_user_not_found`
3. **Arrange-Act-Assert** — Clear test structure
4. **No test interdependence** — Tests run in any order
5. **Fast tests** — Optimize for developer feedback loop
6. **Deterministic** — No flaky tests in CI
7. **Clean up** — Tests clean their own state
