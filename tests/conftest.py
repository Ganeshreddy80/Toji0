"""Toji — Shared test configuration and fixtures.

This module provides shared pytest fixtures and configuration
used across all test suites (unit, integration, e2e).
"""

from __future__ import annotations

import pytest


@pytest.fixture
def app_config() -> dict[str, str]:
    """Provide a minimal application configuration for testing.

    Returns:
        Dictionary with test configuration values.
    """
    return {
        "APP_NAME": "toji-test",
        "APP_ENV": "testing",
        "APP_DEBUG": "true",
        "APP_LOG_LEVEL": "DEBUG",
    }


@pytest.fixture(scope="session", autouse=True)
def bootstrap_test_platform():
    """Session-scoped platform bootstrapping for tests."""
    from research_platform.platform.bootstrap import bootstrap_platform
    from research_platform.platform.state import PlatformState
    import os
    
    # Set default keys if missing for DEV/TEST environment
    if not os.getenv("TOJI_ADMIN_API_KEY"):
        os.environ["TOJI_ADMIN_API_KEY"] = "secure_admin_key_123"
    if not os.getenv("TOJI_ANALYST_API_KEY"):
        os.environ["TOJI_ANALYST_API_KEY"] = "secure_analyst_key_456"
        
    bootstrap_platform()
    yield
    with PlatformState._lock:
        PlatformState._kernel = None


@pytest.fixture(autouse=True)
def reset_state_manager_cache():
    """Reset RuntimeStateManager process-wide cache between tests.

    _metrics is a class-level _RuntimeMetrics instance whose fields persist
    across test functions in the same pytest session. This fixture resets it
    before and after every test so that load() always performs its initialisation
    logic correctly when a test expects fresh state.
    """
    from toji_platform.runtime.state import RuntimeStateManager
    RuntimeStateManager._metrics.db_synced = False
    RuntimeStateManager._metrics.orders = 0
    RuntimeStateManager._metrics.trades = 0
    yield
    RuntimeStateManager._metrics.db_synced = False
    RuntimeStateManager._metrics.orders = 0
    RuntimeStateManager._metrics.trades = 0
