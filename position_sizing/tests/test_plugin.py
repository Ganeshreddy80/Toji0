"""Unit tests for the Position Sizing plugin lifecycle and bindings."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest
from unittest.mock import MagicMock

from toji_platform.core.dependency_injection.container import Container
from toji_platform.core.event_bus.bus import InMemoryEventBus
from toji_platform.core.event_bus.interfaces import IEventBus
from toji_platform.core.types import HealthStatus, ModuleState, PluginId
from trading_context.core.models import TradingContext, TradingContextSnapshot
from trading_context.core.interfaces import ITradingContextStateStore
from market_intelligence.core.models import MarketState
from strategy.core.models import StrategyState
from risk_engine.core.events import RiskApproved
from risk_engine.core.models import RiskState, RiskAssessment
from risk_engine.core.enums import RiskDecision
from position_sizing.core.interfaces import (
    IPositionSizingStateStore,
    IPositionSizingRepository,
    IPositionSizingEngine,
)
from position_sizing.core.plugin import PositionSizingPlugin
from position_sizing.core.events import PositionSizingInitialized


def test_plugin_metadata():
    """Verify plugin identity metadata."""
    plugin = PositionSizingPlugin(event_bus=MagicMock())
    assert plugin.plugin_id == PluginId("position_sizing")
    assert plugin.name == "Position Sizing Engine"
    assert plugin.version == "1.0.0"
    assert "risk_engine" in plugin.dependencies
    assert "trading_context" in plugin.dependencies


def test_plugin_initialize_and_shutdown():
    """Verify DI registration and lifecycle events."""
    container = Container()
    event_bus = InMemoryEventBus()
    container.register(IEventBus, instance=event_bus)

    plugin = PositionSizingPlugin(
        event_bus=event_bus,
        container=container,
    )

    # Pre-init state
    assert plugin.state == ModuleState.CREATED

    # Init
    plugin.initialize()
    assert plugin.state == ModuleState.RUNNING
    assert plugin.health_check() == HealthStatus.HEALTHY

    # Verify bindings in container
    assert container.has(IPositionSizingStateStore)
    assert container.has(IPositionSizingRepository)
    assert container.has(IPositionSizingEngine)

    # Shutdown
    plugin.shutdown()
    assert plugin.state == ModuleState.STOPPED


def test_plugin_event_processing():
    """Verify plugin listens to RiskApproved and executes orchestrator."""
    container = Container()
    event_bus = MagicMock()
    container.register(IEventBus, instance=event_bus)

    # Register mock TradingContext state store
    tc_store = MagicMock()
    container.register(ITradingContextStateStore, instance=tc_store)

    orch = MagicMock()

    plugin = PositionSizingPlugin(
        event_bus=event_bus,
        container=container,
        orchestrator=orch,
    )
    plugin.initialize()

    # Create dummy TradingContext
    dt = datetime.now(timezone.utc)
    market_state = MarketState(symbol="BTCUSDT", timeframe="1h", updated_at=dt)
    strategy_state = StrategyState(symbol="BTCUSDT", timeframe="1h", updated_at=dt)
    tc = TradingContext(
        symbol="BTCUSDT",
        timeframe="1h",
        market_state=market_state,
        strategy_state=strategy_state,
    )
    tc_snapshot = TradingContextSnapshot(
        snapshot_id="tc-snap",
        symbol="BTCUSDT",
        timestamp=dt,
        states={"1h": tc},
    )
    tc_store.get_snapshot.return_value = tc_snapshot

    # Fire system.risk_approved event
    risk_assessment = RiskAssessment(overall_score=90.0, decision=RiskDecision.ALLOW)
    risk_state = RiskState(
        symbol="BTCUSDT",
        timeframe="1h",
        assessment=risk_assessment,
        updated_at=dt,
    )

    event = RiskApproved(
        source="risk_engine.orchestrator",
        payload={
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "state": risk_state.model_dump(mode="json"),
        },
    )

    # Call the subscriber directly (plugin subscribes this callback)
    plugin._on_risk_approved(event)

    # Verify the orchestrator process_context was called
    orch.process_context.assert_called_once_with(tc, risk_assessment)
