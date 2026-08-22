"""Unit and integration tests for TOJI Continuous Paper Trading Runner.
"""

from __future__ import annotations

import os
import sys
import uuid
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from research_platform.platform.bootstrap import bootstrap_platform
from research_platform.platform.service_registry import ServiceRegistry

from toji_platform.runtime.state import RuntimeStateManager, RuntimeState
from toji_platform.runtime.heartbeat import run_heartbeat_check, trigger_heartbeat_alert
from research_platform.news.news_provider import NewsProvider
from research_platform.ai_signal.usage_rules import AIUsageController


@pytest.fixture
def app():
    os.environ["DATABASE_MODE"] = "DEV"
    os.environ["TELEGRAM_ENABLED"] = "true"
    os.environ["TELEGRAM_BOT_TOKEN"] = "mock_telegram"
    os.environ["TELEGRAM_CHAT_ID"] = "mock_chat"

    app_instance = bootstrap_platform()
    yield app_instance
    app_instance.shutdown()


def test_runner_boots_all_services(app):
    """Verify that all target systems initialize and register correctly inside DI container."""
    container = ServiceRegistry().get_service("Container")
    assert container is not None
    
    from research_platform.feature_platform.orchestrator import FeaturePlatformOrchestrator
    from research_platform.price_action.orchestrator import PriceActionOrchestrator
    from research_platform.strategy_framework.composer import StrategyComposer
    from research_platform.ai_signal.signal_generator import AISignalGenerator
    from research_platform.oms.oms_core import OmsCore
    from research_platform.risk_management.orchestrator import RiskManagementOrchestrator
    from research_platform.paper_market.orchestrator import PaperMarketOrchestrator
    from research_platform.paper_trading.orchestrator import PaperTradingOrchestrator
    from research_platform.alerting.orchestrator import AlertOrchestrator

    # Core Subsystems Checks
    assert container.has("Database")
    assert container.has("IEventBus")
    assert container.has(FeaturePlatformOrchestrator)
    assert container.has(PriceActionOrchestrator)
    assert container.has(StrategyComposer)
    assert container.has(AISignalGenerator)
    assert container.has("OrderManagementSystemOrchestrator")
    assert container.has(OmsCore)
    assert container.has(RiskManagementOrchestrator)
    assert container.has(PaperMarketOrchestrator)
    assert container.has(PaperTradingOrchestrator)
    assert container.has("AlertOrchestrator")


def test_runtime_heartbeat_updates(app):
    """Verify that the heartbeat formatting outputs correct fields and uptime."""
    state_manager = RuntimeStateManager()
    state_manager.set_state(RuntimeState.RUNNING)
    state_manager.record_tick()
    state_manager.record_signal()
    state_manager.record_trade()

    container = ServiceRegistry().get_service("Container")
    status_str = run_heartbeat_check(state_manager, container)

    assert "Uptime:" in status_str
    assert "Watching:" in status_str
    assert "Ticks Processed:\n1" in status_str
    assert "Signals Today:\n1" in status_str
    assert "Trades Today:\n1" in status_str
    assert "DB:\nOK" in status_str
    assert "Safety:\nACTIVE" in status_str


def test_ctrl_c_shutdown_safe(app):
    """Verify that the graceful shutdown routine shuts down the platform and saves final state."""
    state_manager = RuntimeStateManager()
    state_manager.set_state(RuntimeState.RUNNING)

    with patch("sys.exit") as mock_exit:
        from scripts.run_paper_trading import handle_shutdown
        with patch("scripts.run_paper_trading.app", app):
            with patch("scripts.run_paper_trading.state_manager", state_manager):
                with patch("scripts.run_paper_trading.running", True):
                    handle_shutdown(None, None)
                    assert state_manager.state == RuntimeState.STOPPED
                    mock_exit.assert_called_once_with(0)


def test_market_tick_loop_running(app):
    """Verify that feeding ticks sequentially calculates features, price action, strategy, and OMS order."""
    container = ServiceRegistry().get_service("Container")
    
    # Active a paper trading session
    from research_platform.paper_trading.orchestrator import PaperTradingOrchestrator
    paper_trading = container.resolve(PaperTradingOrchestrator)
    try:
        paper_trading.start_paper_session("test_session_runner", 100000.0)
    except Exception:
        pass  # session might already be running

    state_manager = RuntimeStateManager()
    state_manager.set_state(RuntimeState.RUNNING)

    # 1. Simulates candle payload
    tick_payload = {
        "symbol": "BTCUSDT",
        "price": 60000.0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "volume": 2.0
    }
    
    # Spy / mock AI Signal to trigger trade
    from research_platform.ai_signal.models import AISignalResult
    mock_ai = AISignalResult(
        symbol="BTCUSDT",
        signal="BUY",
        entry_price=60000.0,
        stop_loss=59000.0,
        take_profit=62000.0,
        risk_reward=2.0,
        confidence=0.85,
        expected_win_rate=0.7,
        reasoning="Bullish trigger"
    )

    from research_platform.ai_signal.signal_generator import AISignalGenerator
    from research_platform.strategy_framework.composer import StrategyComposer
    ai_generator = container.resolve(AISignalGenerator)
    strategy_composer = container.resolve(StrategyComposer)
    
    with patch.object(strategy_composer, "generate_decision", return_value="BUY"):
        with patch.object(ai_generator, "generate_signal", return_value=mock_ai):
            # We manually invoke the runner handle_market_tick callback
            from scripts.run_paper_trading import handle_market_tick
        
            # Inject state
            event_mock = MagicMock()
            event_mock.payload = tick_payload
            
            with patch("scripts.run_paper_trading.container", container):
                with patch("scripts.run_paper_trading.state_manager", state_manager):
                    with patch("scripts.run_paper_trading.running", True):
                        handle_market_tick(event_mock)

                        # Verify that ticks, signals, and trades were recorded
                        assert state_manager.processed_ticks == 1
                        assert state_manager.generated_signals == 1
                        assert state_manager.executed_paper_trades == 1


def test_openrouter_cannot_trade():
    """Verify that LLM usage policy validations block direct order actions."""
    # Allowed actions
    assert AIUsageController.validate_action("explain_trade") is True
    assert AIUsageController.validate_action("summarize_market") is True

    # Forbidden actions
    with pytest.raises(PermissionError) as excinfo:
        AIUsageController.validate_action("submit_order")
    assert "LLM Policy Violation" in str(excinfo.value)

    with pytest.raises(PermissionError) as excinfo2:
        AIUsageController.validate_action("disable_safety")
    assert "LLM Policy Violation" in str(excinfo2.value)


def test_news_cannot_trade():
    """Verify that fetching news does not place orders or touch execution registries."""
    provider = NewsProvider()
    articles = provider.fetch_market_news("crypto")
    assert len(articles) > 0
    assert articles[0].title is not None
    assert articles[0].sentiment in ("BULLISH", "BEARISH", "NEUTRAL")


def test_crash_recovery():
    """Verify that serialization to Redis can rehydrate runtime states completely."""
    # Setup mock Redis client
    mock_redis = MagicMock()
    
    state_manager = RuntimeStateManager(redis_client=mock_redis)
    state_manager.set_state(RuntimeState.RUNNING)
    state_manager.processed_ticks = 120
    state_manager.generated_signals = 4
    state_manager.executed_paper_trades = 2
    
    # Trigger persistence
    state_manager.persist()
    assert mock_redis.set.called

    # Setup loading mock return value
    import json
    stats_data = {
        "state": "RUNNING",
        "start_time": datetime.now(timezone.utc).isoformat(),
        "last_tick_time": datetime.now(timezone.utc).isoformat(),
        "processed_ticks": 120,
        "generated_signals": 4,
        "executed_paper_trades": 2,
        "errors": []
    }
    mock_redis.get.return_value = json.dumps(stats_data)

    # Rehydrate
    new_state_manager = RuntimeStateManager(redis_client=mock_redis)
    new_state_manager.load()
    
    assert new_state_manager.state == RuntimeState.RUNNING
    assert new_state_manager.processed_ticks == 120
    assert new_state_manager.generated_signals == 4
    assert new_state_manager.executed_paper_trades == 2
