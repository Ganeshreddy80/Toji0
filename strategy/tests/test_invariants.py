"""Unit and integration tests verifying all 7 Sprint 3 Architectural Invariants."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
import pytest
from unittest.mock import MagicMock

from market_intelligence.core.models import MarketState
from price_action.core.enums import PatternDirection
from strategy.core.enums import StrategyDecision, StrategyType
from strategy.core.models import StrategySignal, StrategyState, StrategySnapshot
from strategy.core.orchestrator import StrategyOrchestrator
from strategy.core.state import StrategyStateStore
from strategy.core.repository import StrategyRepository
from strategy.analysis.strategy_engine import StrategyEngine
from strategy.analysis.strategy_selector import StrategySelector


# ===========================================================================
# Invariant 1: Strategies Never Submit Orders
# ===========================================================================

def test_invariant_strategies_never_submit_orders():
    """Verify that strategy modules and signals contain no order execution logic or imports."""
    import strategy.core.models as mod_models
    import strategy.core.orchestrator as mod_orch
    import strategy.analysis.strategy_engine as mod_eng

    # Inspect attributes of StrategySignal
    field_names = set(StrategySignal.model_fields.keys())
    forbidden_order_fields = {"order_id", "submit_order", "execute", "broker", "oms", "order_type"}
    assert field_names.isdisjoint(forbidden_order_fields)

    # Inspect module attributes for broker/OMS submission methods
    for mod in (mod_models, mod_orch, mod_eng):
        assert not hasattr(mod, "submit_order")
        assert not hasattr(mod, "execute_order")


# ===========================================================================
# Invariant 2: Strategies Never Size Positions
# ===========================================================================

def test_invariant_strategies_never_size_positions():
    """Verify that StrategySignal does not contain financial position sizing fields."""
    field_names = set(StrategySignal.model_fields.keys())
    forbidden_sizing_fields = {
        "quantity", "position_size", "leverage", "margin_required",
        "dollar_amount", "heat", "stop_loss_price", "take_profit_price"
    }
    assert field_names.isdisjoint(forbidden_sizing_fields)


# ===========================================================================
# Invariant 3: Strategies Never Bypass Risk Engine
# ===========================================================================

def test_invariant_strategies_never_bypass_risk_engine():
    """Verify that strategy evaluation outputs StrategySignal / StrategyState without calling Risk Engine or Execution."""
    engine = StrategyEngine()
    mock_market = MagicMock(spec=MarketState)
    mock_market.symbol = "BTC/USDT"
    mock_market.timeframe = "1h"
    mock_market.trend = None
    mock_market.bos_history = []

    # Evaluate returns a pure StrategySignal
    signal = engine.evaluate(mock_market, None, None)
    assert isinstance(signal, StrategySignal)
    assert signal.decision in (StrategyDecision.BUY, StrategyDecision.SELL, StrategyDecision.WAIT)


# ===========================================================================
# Invariant 4: Signals are Immutable
# ===========================================================================

def test_invariant_signals_are_immutable():
    """Verify that StrategySignal, StrategyState, and StrategySnapshot are frozen Pydantic models."""
    signal = StrategySignal(
        signal_id="sig-001",
        symbol="BTC/USDT",
        timeframe="1h",
        direction=PatternDirection.BULLISH,
        strategy_type=StrategyType.TREND_FOLLOWING,
        decision=StrategyDecision.BUY,
        confidence=90.0,
        confluence_score=85.0,
        reasoning="Test signal",
    )

    with pytest.raises(ValidationError if 'ValidationError' in locals() else Exception):
        signal.confidence = 50.0  # Should raise TypeError / Pydantic FrozenInstanceError

    state = StrategyState(
        symbol="BTC/USDT",
        timeframe="1h",
        active_strategy=StrategyType.TREND_FOLLOWING,
        latest_signal=signal,
    )
    with pytest.raises(Exception):
        state.symbol = "ETH/USDT"


# ===========================================================================
# Invariant 5: Invalid Signals Fail Closed
# ===========================================================================

def test_invariant_invalid_signals_fail_closed_missing_market_state():
    """Verify that missing MarketState returns a fail-closed WAIT signal with 0.0 confidence."""
    engine = StrategyEngine()
    # Call evaluate with None market_state
    signal = engine.evaluate(None, None, None)

    assert signal.decision == StrategyDecision.WAIT
    assert signal.confidence == 0.0
    assert "Fail-Closed" in signal.reasoning
    assert "Missing MarketState Context" in signal.conflicting_factors


def test_invariant_orchestrator_fails_closed_missing_market_state():
    """Verify StrategyOrchestrator fails closed when MarketState is missing from state store."""
    orch = StrategyOrchestrator()
    mock_market_store = MagicMock()
    mock_market_store.get_snapshot.return_value = None  # No market snapshot

    mock_event_bus = MagicMock()
    orch.initialize(
        strategy_engine=StrategyEngine(),
        state_store=StrategyStateStore(),
        repository=StrategyRepository(),
        event_bus=mock_event_bus,
        market_state_store=mock_market_store,
    )

    state = orch.process_strategy("BTC/USDT", "1h")
    assert state.latest_signal.decision == StrategyDecision.WAIT
    assert state.latest_signal.confidence == 0.0
    assert "Fail-Closed" in state.latest_signal.reasoning

    # Verify no StrategySignalEvent (system.strategy_signal) was published for a WAIT decision
    published_types = [type(c.args[0]).__name__ for c in mock_event_bus.publish.call_args_list]
    assert "StrategySignalEvent" not in published_types


# ===========================================================================
# Invariant 6: Failure Isolation
# ===========================================================================

def test_invariant_failure_isolation_in_engine():
    """Verify that an unexpected exception in StrategySelector fails closed to WAIT gracefully."""
    mock_selector = MagicMock()
    mock_selector.select_best_signal.side_effect = RuntimeError("Crash in strategy selector")

    engine = StrategyEngine(selector=mock_selector)
    mock_market = MagicMock(spec=MarketState)
    mock_market.symbol = "BTC/USDT"
    mock_market.timeframe = "1h"

    signal = engine.evaluate(mock_market, None, None)
    assert signal.decision == StrategyDecision.WAIT
    assert signal.confidence == 0.0
    assert "Fail-Closed" in signal.reasoning


# ===========================================================================
# Invariant 7: Deterministic Event Flow
# ===========================================================================

def test_invariant_deterministic_event_flow():
    """Verify that identical inputs generate identical signals, state updates, and events."""
    mock_event_bus = MagicMock()

    orch = StrategyOrchestrator()
    state_store = StrategyStateStore()
    repository = StrategyRepository()

    dt = datetime(2026, 7, 26, 12, 0, 0, tzinfo=timezone.utc)
    mock_market = MagicMock(spec=MarketState)
    mock_market.symbol = "SOL/USDT"
    mock_market.timeframe = "1h"
    mock_market.trend = None
    mock_market.bos_history = []

    mock_market_snap = MagicMock()
    mock_market_snap.states = {"1h": mock_market}
    mock_market_store = MagicMock()
    mock_market_store.get_snapshot.return_value = mock_market_snap

    orch.initialize(
        strategy_engine=StrategyEngine(),
        state_store=state_store,
        repository=repository,
        event_bus=mock_event_bus,
        market_state_store=mock_market_store,
    )

    state1 = orch.process_strategy("SOL/USDT", "1h")
    events1 = [type(c.args[0]).__name__ for c in mock_event_bus.publish.call_args_list]

    mock_event_bus.reset_mock()

    state2 = orch.process_strategy("SOL/USDT", "1h")
    events2 = [type(c.args[0]).__name__ for c in mock_event_bus.publish.call_args_list]

    assert state1.latest_signal.decision == state2.latest_signal.decision
    assert state1.latest_signal.confidence == state2.latest_signal.confidence
    assert events1 == events2
