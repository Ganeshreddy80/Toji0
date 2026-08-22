# CODE_QUALITY_REPORT.md — Static Code Quality Audit

## 1. Static Scan Overview
- **Total Files Scanned**: `819`
- **Quality Standard**: Zero warnings, unused imports pruned, safe dependency hierarchies.

---

## 2. Unused Imports (1333 occurrences)
Unused imports block namespaces and increase footprint.

| File Path | Line | Unused Import Name |
| :--- | :--- | :--- |
| `bootstrap.py` | 4 | `annotations` |
| `kernel.py` | 7 | `annotations` |
| `multi_agent/interfaces.py` | 4 | `annotations` |
| `multi_agent/interfaces.py` | 7 | `Any` |
| `multi_agent/models.py` | 4 | `annotations` |
| `multi_agent/models.py` | 8 | `Optional` |
| `multi_agent/events.py` | 4 | `annotations` |
| `multi_agent/agents.py` | 4 | `annotations` |
| `multi_agent/consensus.py` | 4 | `annotations` |
| `multi_agent/orchestrator.py` | 4 | `annotations` |
| `multi_agent/plugin.py` | 4 | `annotations` |
| `multi_agent/repository.py` | 4 | `annotations` |
| `optimization_engine/interfaces.py` | 4 | `annotations` |
| `optimization_engine/algorithms.py` | 4 | `annotations` |
| `optimization_engine/algorithms.py` | 6 | `copy` |

---

## 3. Potential Security Vulnerabilities (1 occurrences)
Bandit-level security analysis checking execution inputs, shell processes, and query concatenations.

| File Path | Line | Vulnerability Type | Description |
| :--- | :--- | :--- | :--- |
| `scratch/simulation_runner.py` | 29 | **SQL Injection Risk** | Database query formatting via string concatenation or format(). Use query parameters. |

---

## 4. Dead Code / Unused Private Members (1 occurrences)
Private functions or members prefixed with an underscore defined but not called or referenced in the module scope.

| File Path | Line | Private Member Name |
| :--- | :--- | :--- |
| `portfolio_analytics/orchestrator.py` | 70 | `_get_oms_orchestrator` |

---

## 5. Duplicate Function / Class Definitions (23 occurrences)
Identified overlapping namespaces within the same module scope.

| File Path | Lines | Definition Name |
| :--- | :--- | :--- |
| `multi_agent/agents.py` | 14, 34, 54, 66, 87, 107, 119, 131 | `evaluate_proposal` |
| `optimization_engine/algorithms.py` | 21, 31, 38, 90 | `generate_combinations` |
| `alerting/channels.py` | 17, 33, 41, 67 | `send` |
| `tests/test_validation.py` | 98, 318 | `test_passes_under_normal_conditions` |
| `tests/test_validation.py` | 104, 125, 160, 176, 201, 228, 244, 260, 276, 292, 308, 324, 345, 369 | `test_name` |
| `tests/test_validation.py` | 155, 328 | `test_duration_recorded` |
| `tests/test_validation.py` | 170, 217 | `test_returns_valid_result` |
| `tests/test_platform_management.py` | 182, 310, 447 | `worker` |
| `tests/test_platform_management.py` | 205, 215, 331, 341, 351, 369, 469, 479 | `sub` |
| `tests/test_platform_management.py` | 280, 358 | `critical_health` |
| `tests/test_runtime.py` | 263, 280 | `execute` |
| `tests/test_runtime.py` | 265, 282 | `recover` |
| `tests/test_platform_scheduling.py` | 184, 372 | `worker` |
| `tests/test_platform_scheduling.py` | 206, 217, 229, 393, 403, 414, 425, 439 | `sub` |
| `tests/test_platform_scheduling.py` | 305, 321 | `callback_err` |
