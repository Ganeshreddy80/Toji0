# TOJI Runtime Lifecycle Audit & Fixes Report

## Executive Summary
During this fix sprint, we investigated and resolved the duplicate booting of the TOJI Platform Kernel, implemented granular startup validation reporting with execution duration metrics, and verified runtime resilience. All changes were validated using both unit and end-to-end integration test suites (746 unit tests and 27 E2E tests, all passing successfully).

---

## Completed Tasks

### 1. Unified Single-Instance Kernel (Task 1, 2, 3, & 4)
* **Problem**: The system was booting twice: once inside the `runtime_supervisor.py` process and immediately again as a separate subprocess run via `scripts/run_paper_trading.py`. This led to duplicate database connection pools, duplicate plugins initialization, and duplicate market websocket streams.
* **Solution**:
  1. Refactored `research_platform/platform/bootstrap.py` to store the active platform instance inside a thread-safe `PlatformState` singleton class. Subsequent bootstrap calls return the active initialized instance instead of recreating it.
  2. Refactored `scripts/run_paper_trading.py` to encapsulate execution under a `PaperRunner` class. This runner accepts the existing Dependency Injection container and Event Bus instances, reusing the running kernel instead of triggering another full bootstrap cycle.
  3. Modified `scripts/runtime_supervisor.py` to use a hybrid launching model:
     - **Production & E2E Verification**: The supervisor boots the platform once and runs the `PaperRunner` inside the supervisor process as a background thread, ensuring a single shared memory space and exactly one kernel instantiation.
     - **Unit Testing**: Fallback to subprocess spawning is preserved if the platform container is not pre-initialized (supporting legacy mocks/unit tests).
  4. Modified `scripts/runtime_supervisor.py` to execute fast-fail validation checks on API key settings before bootstrapping the platform or database pools.

### 2. Startup Validation Reporting (Task 5)
* **Problem**: When startup validation fails or succeeds, output logs lacked checker-specific diagnostics and duration tracking.
* **Solution**:
  - Updated `research_platform/validation/orchestrator.py` to capture individual checker execution states, diagnostics messages, and execution durations.
  - Formatted the stdout report during startup validations to output clean status blocks with execution times (e.g., `MemoryLeakChecker: PASS [Duration: 0.0151s]`).

### 3. Automated Test Verification (Task 6, 7, & 8)
* **E2E tests**: Implemented `tests/e2e/test_single_kernel_runtime.py` verifying that:
  - The supervisor boots the kernel exactly once.
  - The Paper Runner reuses the existing bootstrapped kernel.
  - No duplicate market gateway or duplicate streams are created.
* **Unit tests**: Implemented `tests/unit/test_validation_reporting.py` verifying that checker durations and messages are accurately formatted and logged.
* **Results**:
  - **E2E test suite**: 27 passed, 0 failed.
  - **Unit test suite**: 746 passed, 0 failed.

---

## Code References
* Unified Bootstrap logic: [bootstrap.py](../../research_platform/platform/bootstrap.py)
* Refactored Paper Runner class: [run_paper_trading.py](../../scripts/run_paper_trading.py)
* Updated Supervisor process: [runtime_supervisor.py](../../scripts/runtime_supervisor.py)
* Validation reporting: [orchestrator.py](../../research_platform/validation/orchestrator.py)
* Single Kernel E2E tests: [test_single_kernel_runtime.py](../../tests/e2e/test_single_kernel_runtime.py)
