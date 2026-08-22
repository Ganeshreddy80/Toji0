"""Integration tests for Live Runner."""

from __future__ import annotations

import time
import pytest
from unittest.mock import MagicMock

from toji_platform.runner import LiveRunner, RecoveryManager
from toji_platform.core.types import HealthStatus, ModuleState, PluginId
from toji_platform.services.trade_journal import TradeJournal
from toji_platform.services.replay_journal import ReplayJournal
from toji_platform.services.metrics_service import MetricsService
from toji_platform.services.market_data_manager import MarketDataManager


def test_live_runner_boot_and_shutdown():
    # Use mock gateway configuration
    config = {
        "market_gateway.provider_mode": "mock",
        "dashboard.port": 8011,
    }
    
    runner = LiveRunner(config_overrides=config)
    
    # Run the live runner in a background thread for 3 seconds
    import threading
    t = threading.Thread(target=runner.run, args=(["BTC/USDT"], 3.0), daemon=True)
    t.start()

    time.sleep(2.0)

    # 1. Verify all new services exist in the DI container
    container = runner._kernel.container
    assert container.has(TradeJournal)
    assert container.has(ReplayJournal)
    assert container.has(MetricsService)
    assert container.has(MarketDataManager)

    # 2. Check health checks are functional
    health_results = runner._kernel.health_check()
    assert "Trade Journal" in health_results
    assert "Replay Journal" in health_results
    assert "Metrics Service" in health_results
    assert "Market Data Manager" in health_results

    # Wait for the runner to finish
    t.join(timeout=8.0)
    if t.is_alive():
        print("!!! RUNNER THREAD STILL ALIVE. Active threads:")
        import threading
        for thread in threading.enumerate():
            print(f"  Thread: {thread.name}, Alive: {thread.is_alive()}, Daemon: {thread.daemon}")
    assert not t.is_alive()


def test_recovery_manager():
    kernel = MagicMock()
    pm = MagicMock()
    kernel.plugin_manager = pm
    
    # Mock a failed plugin
    mock_plugin = MagicMock()
    mock_plugin.state = ModuleState.FAILED
    pm.get.return_value = mock_plugin

    # Mock health checks showing unhealthy plugin
    kernel.health_check.return_value = {
        "failed_plugin": HealthStatus.UNHEALTHY
    }

    # RecoveryManager check
    mgr = RecoveryManager(kernel, check_interval_sec=0.1, max_retries=1)
    
    mgr._check_and_recover()

    # Verify recovery methods were triggered
    mock_plugin.shutdown.assert_called_once()
    mock_plugin.initialize.assert_called_once()
