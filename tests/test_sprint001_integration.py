"""Sprint 001 REAL Integration Tests — Exercise Production Code Paths.

These tests call ACTUAL production functions:
  - handle_market_tick() from scripts/run_paper_trading.py
  - PlatformStartupCoordinator.boot_platform()

They prove production behavior, not simulations.

Test Categories:
  A. Risk fail-closed integration (Issue 1)
     - Real handle_market_tick() with AccountingService missing -> OmsCore NOT called
     - Real handle_market_tick() with AccountingService exception -> OmsCore NOT called
     - Real handle_market_tick() with incomplete summary -> OmsCore NOT called
     - Real handle_market_tick() with malformed summary -> OmsCore NOT called
     - Real handle_market_tick() with valid state -> trading path proceeds

  B. TradingHalted fail-closed when flag absent (Issue 2)
     - handle_market_tick() with TradingHalted absent -> OmsCore NOT called
     - handle_market_tick() with TradingHalted=True -> OmsCore NOT called
     - handle_market_tick() with TradingHalted=False -> trading path proceeds

  C. Plugin boot isolation (Issue 3)
     - boot_platform() with real critical plugin failure -> TradingHalted=True
     - boot_platform() with real non-critical plugin failure -> TradingHalted=False

All tests verify OmsCore.submit_order() is NOT called when guards fire.
"""

from __future__ import annotations

import os
import uuid
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, call

# Ensure test-mode DB
os.environ.setdefault("DATABASE_MODE", "DEV")
os.environ.setdefault("TELEGRAM_ENABLED", "false")


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def booted_app():
    """Bootstrap the platform ONCE for the module. Teardown after all tests."""
    from research_platform.platform.bootstrap import bootstrap_platform
    app_instance = bootstrap_platform()
    yield app_instance
    app_instance.shutdown()


@pytest.fixture
def booted_container(booted_app):
    """Return the DI container from the booted platform."""
    from research_platform.platform.service_registry import ServiceRegistry
    return ServiceRegistry().get_service("Container")


@pytest.fixture
def live_state_manager():
    from toji_platform.runtime.state import RuntimeStateManager, RuntimeState
    sm = RuntimeStateManager()
    sm.set_state(RuntimeState.RUNNING)
    return sm


from toji_platform.core.dependency_injection.container import _Registration

def safe_register(container, key, instance):
    """Safely register or override a key in the DI container without raising DuplicateServiceError."""
    if hasattr(container, "_services") and isinstance(container._services, dict):
        k = container._key(key) if hasattr(container, "_key") else str(key)
        reg = _Registration(instance=instance, singleton=True)
        reg._resolved = True
        container._services[k] = reg
    else:
        if container.has(key):
            try:
                container.unregister(key)
            except Exception:
                pass
        container.register(key, instance)


def _make_btc_tick_event(price: float = 60_000.0) -> MagicMock:
    """Return a realistic BTC market tick event object."""
    event = MagicMock()
    event.payload = {
        "symbol": "BTCUSDT",
        "price": price,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "volume": 2.0,
    }
    event.source = "integration_test"
    return event


def _make_buy_ai_signal():
    """Return a BUY AISignalResult with high confidence that passes all auditors."""
    from research_platform.ai_signal.models import AISignalResult
    return AISignalResult(
        symbol="BTCUSDT",
        signal="BUY",
        entry_price=60_000.0,
        stop_loss=59_000.0,
        take_profit=63_000.0,
        risk_reward=3.0,
        confidence=0.90,
        expected_win_rate=0.7,
        reasoning="Sprint 001 integration test signal",
    )


def _run_tick_with_container(container, state_manager, price: float = 60_000.0):
    """
    Call the REAL handle_market_tick with patched global state.
    Returns the state_manager for assertion.
    """
    from research_platform.strategy_framework.composer import StrategyComposer
    from research_platform.ai_signal.signal_generator import AISignalGenerator

    strategy_composer = container.resolve(StrategyComposer)
    ai_generator = container.resolve(AISignalGenerator)
    mock_signal = _make_buy_ai_signal()

    with patch.object(strategy_composer, "generate_decision", return_value="BUY"), \
         patch.object(ai_generator, "generate_signal", return_value=mock_signal):
        from scripts.run_paper_trading import handle_market_tick
        event = _make_btc_tick_event(price=price)
        with patch("scripts.run_paper_trading.container", container), \
             patch("scripts.run_paper_trading.state_manager", state_manager), \
             patch("scripts.run_paper_trading.running", True):
            handle_market_tick(event)

    return state_manager


# ── A. Risk Fail-Closed Integration (Issue 1) ─────────────────────────────────

class TestRiskFailClosedIntegration:
    """
    Real integration tests: exercise the actual handle_market_tick() production code.
    Each test verifies that OmsCore.submit_order() is NOT called when risk state is unavailable.
    """

    def test_valid_accounting_service_allows_trading_path(self, booted_container, live_state_manager):
        """
        With a real, booted AccountingService (registered by PortfolioAccountingPlugin),
        the trading path must proceed past the risk gate.
        OmsCore.submit_order() must be called.
        """
        assert booted_container.has("AccountingService"), (
            "AccountingService must be registered by PortfolioAccountingPlugin"
        )

        from research_platform.oms.oms_core import OmsCore
        oms_core = booted_container.resolve(OmsCore)

        with patch.object(oms_core, "submit_order", wraps=oms_core.submit_order) as mock_submit:
            _run_tick_with_container(booted_container, live_state_manager)

        # Risk gate passed: OMS was called at least once
        assert mock_submit.call_count >= 1, (
            "OmsCore.submit_order() must be called when risk state is valid. "
            f"call_count={mock_submit.call_count}"
        )

    def test_accounting_service_missing_blocks_oms(self, booted_container, live_state_manager):
        """
        AccountingService absent from container -> RISK_STATE_UNKNOWN -> OmsCore NOT called.
        This exercises the actual production fail-closed block in handle_market_tick().
        """
        from research_platform.oms.oms_core import OmsCore
        oms_core = booted_container.resolve(OmsCore)

        real_svc = booted_container.resolve("AccountingService") if booted_container.has("AccountingService") else None
        try:
            with patch.object(booted_container, "has",
                              side_effect=lambda k: False if str(k) == "AccountingService" else type(booted_container).has(booted_container, k)), \
                 patch.object(oms_core, "submit_order") as mock_submit:
                _run_tick_with_container(booted_container, live_state_manager)

            assert mock_submit.call_count == 0, (
                "OmsCore.submit_order() must NOT be called when AccountingService is missing. "
                f"call_count={mock_submit.call_count}"
            )
        finally:
            if real_svc:
                safe_register(booted_container, "AccountingService", real_svc)

    def test_accounting_service_exception_blocks_oms(self, booted_container, live_state_manager):
        """
        AccountingService.get_portfolio_summary() raises -> RISK_STATE_UNKNOWN -> OmsCore NOT called.
        """
        from research_platform.oms.oms_core import OmsCore
        real_svc = booted_container.resolve("AccountingService") if booted_container.has("AccountingService") else MagicMock()
        oms_core = booted_container.resolve(OmsCore)

        broken_svc = MagicMock()
        broken_svc.get_portfolio_summary.side_effect = RuntimeError("DB connection lost in test")

        safe_register(booted_container, "AccountingService", broken_svc)
        try:
            with patch.object(oms_core, "submit_order") as mock_submit:
                _run_tick_with_container(booted_container, live_state_manager)

            assert mock_submit.call_count == 0, (
                "OmsCore.submit_order() must NOT be called when AccountingService raises. "
                f"call_count={mock_submit.call_count}"
            )
        finally:
            safe_register(booted_container, "AccountingService", real_svc)

    def test_incomplete_summary_blocks_oms(self, booted_container, live_state_manager):
        """
        AccountingService.get_portfolio_summary() missing 'peak_equity' -> incomplete -> OmsCore NOT called.
        """
        from research_platform.oms.oms_core import OmsCore
        real_svc = booted_container.resolve("AccountingService") if booted_container.has("AccountingService") else MagicMock()
        oms_core = booted_container.resolve(OmsCore)

        incomplete_svc = MagicMock()
        incomplete_svc.get_portfolio_summary.return_value = {
            "equity": 100_000.0,
            # peak_equity missing
            "daily_pnl": 0.0,
        }

        safe_register(booted_container, "AccountingService", incomplete_svc)
        try:
            with patch.object(oms_core, "submit_order") as mock_submit:
                _run_tick_with_container(booted_container, live_state_manager)

            assert mock_submit.call_count == 0, (
                "OmsCore.submit_order() must NOT be called when summary is incomplete. "
                f"call_count={mock_submit.call_count}"
            )
        finally:
            safe_register(booted_container, "AccountingService", real_svc)

    def test_malformed_summary_blocks_oms(self, booted_container, live_state_manager):
        """
        AccountingService.get_portfolio_summary() returns non-numeric equity -> malformed -> OmsCore NOT called.
        """
        from research_platform.oms.oms_core import OmsCore
        real_svc = booted_container.resolve("AccountingService") if booted_container.has("AccountingService") else MagicMock()
        oms_core = booted_container.resolve(OmsCore)

        malformed_svc = MagicMock()
        malformed_svc.get_portfolio_summary.return_value = {
            "equity": "INVALID_STRING",
            "peak_equity": 100_000.0,
            "daily_pnl": 0.0,
        }

        safe_register(booted_container, "AccountingService", malformed_svc)
        try:
            with patch.object(oms_core, "submit_order") as mock_submit:
                _run_tick_with_container(booted_container, live_state_manager)

            assert mock_submit.call_count == 0, (
                "OmsCore.submit_order() must NOT be called when summary is malformed. "
                f"call_count={mock_submit.call_count}"
            )
        finally:
            safe_register(booted_container, "AccountingService", real_svc)


# ── B. TradingHalted Fail-Closed (Issue 2) ────────────────────────────────────

class TestTradingHaltedFailClosedIntegration:
    """
    Real integration tests for the TradingHalted safety gate in handle_market_tick().
    Verifies that missing TradingHalted flag fails CLOSED, not open.
    """

    def test_trading_halted_absent_blocks_oms(self, booted_container, live_state_manager):
        """
        TradingHalted key absent from container -> safety state UNKNOWN -> OmsCore NOT called.
        This is a fail-CLOSED requirement per Sprint 001 correction.
        """
        from research_platform.oms.oms_core import OmsCore
        oms_core = booted_container.resolve(OmsCore)

        with patch.object(booted_container, "has",
                          side_effect=lambda k: False if str(k) == "TradingHalted" else type(booted_container).has(booted_container, k)), \
             patch.object(oms_core, "submit_order") as mock_submit:
            _run_tick_with_container(booted_container, live_state_manager)

        assert mock_submit.call_count == 0, (
            "OmsCore.submit_order() must NOT be called when TradingHalted is absent from container. "
            f"call_count={mock_submit.call_count}"
        )

    def test_trading_halted_true_blocks_oms(self, booted_container, live_state_manager):
        """
        TradingHalted=True in container -> critical plugin failure -> OmsCore NOT called.
        """
        from research_platform.oms.oms_core import OmsCore
        oms_core = booted_container.resolve(OmsCore)

        real_halted = booted_container.resolve("TradingHalted") if booted_container.has("TradingHalted") else False
        safe_register(booted_container, "TradingHalted", True)
        safe_register(booted_container, "CriticalFailedPlugins", ["OmsPlugin_test"])

        try:
            with patch.object(oms_core, "submit_order") as mock_submit:
                _run_tick_with_container(booted_container, live_state_manager)

            assert mock_submit.call_count == 0, (
                "OmsCore.submit_order() must NOT be called when TradingHalted=True. "
                f"call_count={mock_submit.call_count}"
            )
        finally:
            safe_register(booted_container, "TradingHalted", real_halted)
            safe_register(booted_container, "CriticalFailedPlugins", [])

    def test_trading_halted_false_allows_trading_path(self, booted_container, live_state_manager):
        """
        TradingHalted=False + valid AccountingService -> safety gate passes -> OmsCore called.
        This is the NORMAL operating path on clean boot.
        """
        from research_platform.oms.oms_core import OmsCore
        oms_core = booted_container.resolve(OmsCore)

        assert booted_container.has("TradingHalted"), "TradingHalted must be registered by boot coordinator"
        assert booted_container.resolve("TradingHalted") is False, (
            "After clean boot, TradingHalted must be False"
        )

        with patch.object(oms_core, "submit_order", wraps=oms_core.submit_order) as mock_submit:
            _run_tick_with_container(booted_container, live_state_manager)

        assert mock_submit.call_count >= 1, (
            "OmsCore.submit_order() must be called when TradingHalted=False and state valid. "
            f"call_count={mock_submit.call_count}"
        )


# ── C. Plugin Boot Isolation (Issue 3) ───────────────────────────────────────

class TestPluginBootIsolationIntegration:
    """
    Real integration tests for PlatformStartupCoordinator.boot_platform().
    Uses actual production classes with injected failures.
    """

    def _make_failing_plugin(self, name: str, exc: Exception):
        """Create a real plugin object whose initialize() raises."""
        class FailingPlugin:
            pass
        FailingPlugin.__name__ = name

        instance = FailingPlugin()

        def failing_initialize():
            raise exc

        instance.initialize = failing_initialize
        instance.shutdown = lambda: None
        return instance

    def _make_ok_plugin(self, name: str, booted_flag: list):
        """Create a real plugin object whose initialize() succeeds and records itself."""
        class OkPlugin:
            pass
        OkPlugin.__name__ = name

        instance = OkPlugin()

        def ok_initialize():
            booted_flag.append(name)

        instance.initialize = ok_initialize
        instance.shutdown = lambda: None
        return instance

    def test_critical_plugin_failure_sets_trading_halted_true(self):
        """
        A critical plugin (OmsPlugin) raising in initialize() must set TradingHalted=True
        in the DI container via the actual PlatformStartupCoordinator.boot_platform().
        """
        from research_platform.platform.startup import PlatformStartupCoordinator
        from research_platform.platform.container_boot import ContainerBootloader

        coordinator = PlatformStartupCoordinator()
        real_container = ContainerBootloader().boot_container()

        failing_oms = self._make_failing_plugin("OmsPlugin", RuntimeError("OMS init failed in test"))

        with patch.object(coordinator, "config_loader") as mock_config, \
             patch.object(coordinator, "container_boot") as mock_cb, \
             patch.object(coordinator, "eventbus_boot") as mock_eb, \
             patch.object(coordinator, "plugin_loader") as mock_pl, \
             patch.object(coordinator, "service_registry"):

            mock_config.load_configuration.return_value = {
                "database": {"host": "localhost", "port": 5432, "name": "test", "user": "test", "password": "test"}
            }
            mock_db = MagicMock()
            mock_db.connect.return_value = None

            with patch("research_platform.platform.startup.DatabaseLifecycleManager", return_value=mock_db):
                mock_cb.boot_container.return_value = real_container
                mock_eb.boot_eventbus.return_value = MagicMock()
                mock_pl.discover_plugins.return_value = [failing_oms]

                coordinator.boot_platform()

        assert real_container.has("TradingHalted"), "TradingHalted must be registered after boot"
        assert real_container.resolve("TradingHalted") is True, (
            "TradingHalted must be True when OmsPlugin (critical) fails"
        )
        assert real_container.has("CriticalFailedPlugins")
        assert "OmsPlugin" in real_container.resolve("CriticalFailedPlugins")

    def test_non_critical_plugin_failure_trading_halted_remains_false(self):
        """
        A non-critical plugin (MetricsPlugin) raising in initialize() must NOT set TradingHalted.
        TradingHalted=False must remain after boot.
        """
        from research_platform.platform.startup import PlatformStartupCoordinator
        from research_platform.platform.container_boot import ContainerBootloader

        coordinator = PlatformStartupCoordinator()
        real_container = ContainerBootloader().boot_container()

        failing_metrics = self._make_failing_plugin("MetricsPlugin", RuntimeError("metrics failed in test"))

        with patch.object(coordinator, "config_loader") as mock_config, \
             patch.object(coordinator, "container_boot") as mock_cb, \
             patch.object(coordinator, "eventbus_boot") as mock_eb, \
             patch.object(coordinator, "plugin_loader") as mock_pl, \
             patch.object(coordinator, "service_registry"):

            mock_config.load_configuration.return_value = {
                "database": {"host": "localhost", "port": 5432, "name": "test", "user": "test", "password": "test"}
            }
            mock_db = MagicMock()
            mock_db.connect.return_value = None

            with patch("research_platform.platform.startup.DatabaseLifecycleManager", return_value=mock_db):
                mock_cb.boot_container.return_value = real_container
                mock_eb.boot_eventbus.return_value = MagicMock()
                mock_pl.discover_plugins.return_value = [failing_metrics]

                coordinator.boot_platform()

        assert real_container.has("TradingHalted")
        assert real_container.resolve("TradingHalted") is False, (
            "TradingHalted must remain False when only non-critical plugin fails"
        )
        assert real_container.has("CriticalFailedPlugins")
        assert real_container.resolve("CriticalFailedPlugins") == []

    def test_critical_failure_non_critical_plugins_still_boot(self):
        """
        After a critical plugin (OmsPlugin) fails, remaining NON-CRITICAL plugins MUST still boot.
        The platform must not abort all subsequent plugin initialization.
        """
        from research_platform.platform.startup import PlatformStartupCoordinator
        from research_platform.platform.container_boot import ContainerBootloader

        coordinator = PlatformStartupCoordinator()
        real_container = ContainerBootloader().boot_container()

        booted_tracker = []
        failing_oms = self._make_failing_plugin("OmsPlugin", RuntimeError("OMS init failed"))
        ok_metrics = self._make_ok_plugin("MetricsPlugin", booted_tracker)
        ok_reporting = self._make_ok_plugin("ReportingPlugin", booted_tracker)

        with patch.object(coordinator, "config_loader") as mock_config, \
             patch.object(coordinator, "container_boot") as mock_cb, \
             patch.object(coordinator, "eventbus_boot") as mock_eb, \
             patch.object(coordinator, "plugin_loader") as mock_pl, \
             patch.object(coordinator, "service_registry"):

            mock_config.load_configuration.return_value = {
                "database": {"host": "localhost", "port": 5432, "name": "test", "user": "test", "password": "test"}
            }
            mock_db = MagicMock()
            mock_db.connect.return_value = None

            with patch("research_platform.platform.startup.DatabaseLifecycleManager", return_value=mock_db):
                mock_cb.boot_container.return_value = real_container
                mock_eb.boot_eventbus.return_value = MagicMock()
                mock_pl.discover_plugins.return_value = [failing_oms, ok_metrics, ok_reporting]

                coordinator.boot_platform()

        assert real_container.resolve("TradingHalted") is True
        assert "MetricsPlugin" in booted_tracker
        assert "ReportingPlugin" in booted_tracker