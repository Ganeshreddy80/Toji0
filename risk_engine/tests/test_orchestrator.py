"""Unit tests for the Risk Engine Orchestrator."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest
from unittest.mock import MagicMock

from trading_context.core.models import TradingContext
from market_intelligence.core.models import MarketState, SessionState
from market_intelligence.core.enums import SessionName
from strategy.core.models import StrategyState
from risk_engine.core.enums import RiskDecision, RiskSeverity
from risk_engine.core.exceptions import OrchestratorError
from risk_engine.core.models import RiskState, RiskSnapshot, RiskAssessment
from risk_engine.core.state import RiskStateStore
from risk_engine.core.repository import RiskRepository
from risk_engine.analysis.risk_engine import RiskEngine
from risk_engine.core.orchestrator import RiskOrchestrator
from risk_engine.core.events import (
    RiskUpdated,
    RiskApproved,
    RiskRejected,
    RiskThresholdExceeded,
)


@pytest.fixture
def dummy_context() -> TradingContext:
    dt = datetime.now(timezone.utc)
    session_state = SessionState(
        symbol="BTCUSDT",
        session_name=SessionName.NEW_YORK,
        session_high=50000.0,
        session_low=49000.0,
    )
    market_state = MarketState(
        symbol="BTCUSDT",
        timeframe="1h",
        updated_at=dt,
        session=session_state,
    )
    strategy_state = StrategyState(symbol="BTCUSDT", timeframe="1h", updated_at=dt)
    return TradingContext(
        symbol="BTCUSDT",
        timeframe="1h",
        market_state=market_state,
        strategy_state=strategy_state,
        generated_at=dt,
    )


@pytest.fixture
def mock_event_bus() -> MagicMock:
    bus = MagicMock()
    bus.publish = MagicMock()
    return bus


def test_orchestrator_initialization_errors(dummy_context):
    """Verify orchestrator fails to run if not initialized."""
    orchestrator = RiskOrchestrator()
    with pytest.raises(OrchestratorError, match="not initialized"):
        orchestrator.process_context(dummy_context)


def test_orchestrator_process_context_allow(dummy_context, mock_event_bus):
    """Verify E2E orchestrator run resulting in ALLOW decision publishes risk_updated and risk_approved."""
    state_store = RiskStateStore()
    repo = RiskRepository()
    engine = RiskEngine()

    orchestrator = RiskOrchestrator()
    orchestrator.initialize(
        state_store=state_store,
        repository=repo,
        risk_engine=engine,
        event_bus=mock_event_bus,
    )

    # 1. Run midweek (Wednesday) to pass weekend block
    dt = datetime(2026, 6, 24, 12, 0, 0, tzinfo=timezone.utc)
    ctx = dummy_context.model_copy(update={"generated_at": dt})

    risk_state = orchestrator.process_context(
        ctx,
        current_daily_loss_pct=0.0,
        current_drawdown_pct=0.0,
        market_closed=False,
    )

    assert risk_state is not None
    assert risk_state.assessment.decision == RiskDecision.ALLOW

    # Verify state store updated
    loaded_snap = state_store.get_snapshot("BTCUSDT")
    assert loaded_snap is not None
    assert loaded_snap.states["1h"].assessment.decision == RiskDecision.ALLOW

    # Verify repository saved snapshot
    saved_snap = repo.load_latest_snapshot("BTCUSDT")
    assert saved_snap is not None
    assert saved_snap.states["1h"] == risk_state

    # Verify events published: system.risk_updated, system.risk_checked, and system.risk_approved
    assert mock_event_bus.publish.call_count == 3
    events = [call[0][0] for call in mock_event_bus.publish.call_args_list]
    assert any(isinstance(ev, RiskUpdated) for ev in events)
    assert any(isinstance(ev, RiskApproved) for ev in events)


def test_orchestrator_process_context_block(dummy_context, mock_event_bus):
    """Verify orchestrator run resulting in BLOCK decision publishes risk_updated, risk_rejected, and threshold exceeded."""
    state_store = RiskStateStore()
    repo = RiskRepository()
    engine = RiskEngine()

    orchestrator = RiskOrchestrator()
    orchestrator.initialize(
        state_store=state_store,
        repository=repo,
        risk_engine=engine,
        event_bus=mock_event_bus,
    )

    # Trigger daily loss breach (CRITICAL)
    dt = datetime(2026, 6, 24, 12, 0, 0, tzinfo=timezone.utc)
    ctx = dummy_context.model_copy(update={"generated_at": dt})

    risk_state = orchestrator.process_context(
        ctx,
        current_daily_loss_pct=0.05,
        daily_loss_limit_pct=0.02,
        market_closed=False,
    )

    assert risk_state is not None
    assert risk_state.assessment.decision == RiskDecision.BLOCK

    # Verify events: system.risk_updated, system.risk_checked, system.risk_rejected, and system.risk_threshold_exceeded
    assert mock_event_bus.publish.call_count == 4
    events = [call[0][0] for call in mock_event_bus.publish.call_args_list]
    assert any(isinstance(ev, RiskUpdated) for ev in events)
    assert any(isinstance(ev, RiskRejected) for ev in events)
    assert any(isinstance(ev, RiskThresholdExceeded) for ev in events)
