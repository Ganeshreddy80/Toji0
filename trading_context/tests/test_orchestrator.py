"""Unit tests for the Trading Context Orchestrator."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import pytest
from unittest.mock import MagicMock

from market_intelligence.core.models import MarketState
from strategy.core.models import StrategyState, StrategySignal
from strategy.core.enums import StrategyDecision, StrategyType
from price_action.core.enums import PatternDirection
from price_action.core.models import PatternState
from confluence.core.models import ConfluenceState, ConfluenceScore
from confluence.core.enums import SetupGrade
from trading_context.core.exceptions import ValidationError, OrchestratorError
from trading_context.core.models import (
    TradingContext,
    TradingContextSnapshot,
)
from trading_context.core.state import TradingContextStateStore
from trading_context.core.repository import TradingContextRepository
from trading_context.core.orchestrator import TradingContextOrchestrator
from trading_context.core.events import (
    TradingContextCreated,
    TradingContextUpdated,
    TradingContextInvalid,
)


@pytest.fixture
def base_dt() -> datetime:
    return datetime.now(timezone.utc)


@pytest.fixture
def mock_event_bus() -> MagicMock:
    bus = MagicMock()
    bus.publish = MagicMock()
    return bus


@pytest.fixture
def mock_market_store() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_pattern_store() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_confluence_store() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_strategy_store() -> MagicMock:
    return MagicMock()


def test_orchestrator_initialization_errors():
    """Verify orchestrator rejects processing if not initialized or missing essential stores."""
    orchestrator = TradingContextOrchestrator()

    # Not initialized at all
    with pytest.raises(OrchestratorError, match="Orchestrator is not initialized"):
        orchestrator.process_context("BTCUSDT", "1h")

    # Initialized but missing market_state_store
    state_store = TradingContextStateStore()
    repo = TradingContextRepository()
    orchestrator.initialize(state_store=state_store, repository=repo)

    with pytest.raises(OrchestratorError, match="Market state store is not resolved/provided"):
        orchestrator.process_context("BTCUSDT", "1h")


def test_orchestrator_validation_failure(
    mock_event_bus,
    mock_market_store,
    mock_strategy_store,
    base_dt,
):
    """Verify that validation failures are caught, log/warn, and publish invalid event."""
    state_store = TradingContextStateStore()
    repo = TradingContextRepository()
    orchestrator = TradingContextOrchestrator()
    orchestrator.initialize(
        state_store=state_store,
        repository=repo,
        event_bus=mock_event_bus,
        market_state_store=mock_market_store,
        strategy_state_store=mock_strategy_store,
    )

    # Mock market store returns None -> will fail presence check
    mock_market_store.get_snapshot.return_value = None

    # Run
    result = orchestrator.process_context("BTCUSDT", "1h")

    assert result is None
    mock_event_bus.publish.assert_called_once()
    event = mock_event_bus.publish.call_args[0][0]
    assert isinstance(event, TradingContextInvalid)
    assert event.payload["symbol"] == "BTCUSDT"
    assert event.payload["timeframe"] == "1h"
    assert "Missing MarketState" in event.payload["reason"]


def test_orchestrator_process_context_success_created_and_updated(
    mock_event_bus,
    mock_market_store,
    mock_pattern_store,
    mock_confluence_store,
    mock_strategy_store,
    base_dt,
):
    """Verify successful context creation and then update flows, ensuring events are dispatched."""
    state_store = TradingContextStateStore()
    repo = TradingContextRepository()
    orchestrator = TradingContextOrchestrator()
    orchestrator.initialize(
        state_store=state_store,
        repository=repo,
        event_bus=mock_event_bus,
        market_state_store=mock_market_store,
        pattern_state_store=mock_pattern_store,
        confluence_state_store=mock_confluence_store,
        strategy_state_store=mock_strategy_store,
    )

    # 1. Setup mock states
    market_state = MarketState(symbol="BTCUSDT", timeframe="1h", updated_at=base_dt)
    
    pattern_state = PatternState(symbol="BTCUSDT", timeframe="1h", updated_at=base_dt)
    
    score = ConfluenceScore(
        overall_score=85.0, setup_grade=SetupGrade.A, trend_score=80, structure_score=80,
        liquidity_score=80, zone_score=80, volume_score=80, regime_score=80, session_score=80,
        mtf_score=80, correlation_score=80, pattern_score=80, quality_score=80, conflict_penalty=0
    )
    confluence_state = ConfluenceState(symbol="BTCUSDT", timeframe="1h", score=score, updated_at=base_dt)
    
    strategy_signal = StrategySignal(
        signal_id="sig-123",
        symbol="BTCUSDT",
        timeframe="1h",
        direction=PatternDirection.BULLISH,
        strategy_type=StrategyType.TREND_FOLLOWING,
        decision=StrategyDecision.BUY,
        confidence=80.0,
        confluence_score=85.0,
        reasoning="Test signal rationale",
        detected_at=base_dt,
    )
    strategy_state = StrategyState(
        symbol="BTCUSDT", timeframe="1h", latest_signal=strategy_signal, updated_at=base_dt
    )

    # Setup mocks
    m_snap = MagicMock()
    m_snap.states = {"1h": market_state}
    mock_market_store.get_snapshot.return_value = m_snap

    p_snap = MagicMock()
    p_snap.states = {"1h": pattern_state}
    mock_pattern_store.get_snapshot.return_value = p_snap

    c_snap = MagicMock()
    c_snap.states = {"1h": confluence_state}
    mock_confluence_store.get_snapshot.return_value = c_snap

    s_snap = MagicMock()
    s_snap.states = {"1h": strategy_state}
    mock_strategy_store.get_snapshot.return_value = s_snap

    # 2. Process first time (Created event)
    ctx1 = orchestrator.process_context("BTCUSDT", "1h")
    
    assert ctx1 is not None
    assert ctx1.symbol == "BTCUSDT"
    assert ctx1.timeframe == "1h"
    assert ctx1.market_state == market_state
    assert ctx1.pattern_state == pattern_state
    assert ctx1.confluence_state == confluence_state
    assert ctx1.strategy_state == strategy_state
    assert ctx1.strategy_signal == strategy_signal

    mock_event_bus.publish.assert_called_once()
    event1 = mock_event_bus.publish.call_args[0][0]
    assert isinstance(event1, TradingContextCreated)
    assert event1.payload["symbol"] == "BTCUSDT"
    assert event1.payload["timeframe"] == "1h"

    # Verify repository saved it
    saved_snap = repo.load_latest_snapshot("BTCUSDT")
    assert saved_snap is not None
    assert saved_snap.states["1h"].replay_id == ctx1.replay_id

    # 3. Process second time (Updated event)
    mock_event_bus.publish.reset_mock()
    
    # Modify timestamp slightly to simulate new state update
    new_dt = base_dt + timedelta(seconds=5)
    market_state_new = market_state.model_copy(update={"updated_at": new_dt})
    strategy_state_new = strategy_state.model_copy(update={"updated_at": new_dt})
    
    m_snap.states = {"1h": market_state_new}
    s_snap.states = {"1h": strategy_state_new}

    ctx2 = orchestrator.process_context("BTCUSDT", "1h")
    
    assert ctx2 is not None
    assert ctx2.replay_id != ctx1.replay_id
    assert ctx2.market_state.updated_at == new_dt

    mock_event_bus.publish.assert_called_once()
    event2 = mock_event_bus.publish.call_args[0][0]
    assert isinstance(event2, TradingContextUpdated)
    assert event2.payload["symbol"] == "BTCUSDT"
    assert event2.payload["timeframe"] == "1h"
