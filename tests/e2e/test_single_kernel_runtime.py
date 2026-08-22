"""E2E single kernel runtime and singleton protection tests.
"""

from __future__ import annotations

import os
import sys
import pytest
from unittest.mock import patch, MagicMock

from research_platform.platform.bootstrap import bootstrap_platform
from research_platform.platform.state import PlatformState
from research_platform.platform.service_registry import ServiceRegistry
from research_platform.platform.startup import PlatformStartupCoordinator
from research_platform.platform.plugin_loader import PluginLoader
from research_platform.platform.database_boot import DatabaseLifecycleManager
from research_platform.live_trading.scheduler import ContinuousScheduler
from scripts.run_paper_trading import PaperRunner


@pytest.fixture(autouse=True)
def reset_singleton():
    """Ensure platform singleton is reset before and after each test."""
    with PlatformState._lock:
        PlatformState._kernel = None
    os.environ["TOJI_SINGLE_KERNEL"] = "true"
    yield
    with PlatformState._lock:
        PlatformState._kernel = None
    os.environ.pop("TOJI_SINGLE_KERNEL", None)


def test_supervisor_boots_kernel_once():
    """Verify that PlatformState prevents double boot and each core component initializes once."""
    with patch.object(PluginLoader, "discover_plugins", return_value=[]) as mock_plugins:
        with patch.object(DatabaseLifecycleManager, "connect") as mock_db:
            with patch.object(ContinuousScheduler, "start_scheduler") as mock_sched:
                
                # First boot
                app1 = bootstrap_platform()
                
                # Second boot attempt
                app2 = bootstrap_platform()
                
                assert app1 is app2
                mock_plugins.assert_called_once()
                mock_db.assert_called_once()
                # ContinuousScheduler is started in plugin initialization if plugin is loaded,
                # since we mocked discover_plugins to return empty list, it's called 0 times.
                # Let's verify double boot is blocked.
                assert PlatformState.exists() is True


def test_paper_runner_reuses_existing_kernel():
    """Verify that PaperRunner accepts existing container/event bus and does not boot a new platform."""
    # Reset and boot platform once
    app = bootstrap_platform()
    container = ServiceRegistry().get_service("Container")
    event_bus = ServiceRegistry().get_service("EventBus")
    
    assert container is not None
    assert event_bus is not None
    
    with patch("research_platform.platform.bootstrap.PlatformApplication.boot") as mock_boot:
        # Instantiate PaperRunner with existing kernel components
        runner = PaperRunner(container=container, event_bus=event_bus)
        
        # Verify startup does not call boot_platform
        with patch("research_platform.paper_trading.orchestrator.PaperTradingOrchestrator.start_paper_session"):
            with patch("research_platform.paper_market.orchestrator.PaperMarketOrchestrator.start_paper_market"):
                runner.start()
                
                mock_boot.assert_not_called()
                assert runner.running is True
                runner.stop()


def test_no_duplicate_market_gateway():
    """Verify only one BinanceMarketGateway instance exists in the container."""
    bootstrap_platform()
    container = ServiceRegistry().get_service("Container")
    
    # Try resolving gateway types robustly depending on active provider class
    try:
        from research_platform.live_trading.binance_demo import BinanceDemoGateway
        gateway1 = container.resolve(BinanceDemoGateway)
        gateway2 = container.resolve(BinanceDemoGateway)
    except Exception:
        from research_platform.live_trading.factory import BinanceMarketGateway
        gateway1 = container.resolve(BinanceMarketGateway)
        gateway2 = container.resolve(BinanceMarketGateway)
        
    assert gateway1 is not None
    assert gateway1 is gateway2


def test_double_boot_kernel_is_same_and_boot_counter():
    """Regression Test 1: Call bootstrap_platform() twice, assert kernel1 is kernel2 and boot count is 1."""
    from research_platform.platform.application import PlatformApplication
    
    with patch.object(PlatformApplication, "boot") as mock_boot:
        kernel1 = bootstrap_platform()
        kernel2 = bootstrap_platform()
        
        assert kernel1 is kernel2
        assert mock_boot.call_count == 1


def test_core_services_registered_in_container():
    """Regression Test 2: After boot, assert container has RuntimeEngine, Database, Scheduler, and RecoveryOrchestrator."""
    app = bootstrap_platform()
    container = ServiceRegistry().get_service("Container")
    
    assert container.get("RuntimeEngine") is not None
    assert container.get("Database") is not None
    assert container.get("Scheduler") is not None
    assert container.get("RecoveryOrchestrator") is not None
