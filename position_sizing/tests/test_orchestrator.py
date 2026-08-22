"""Unit tests for the Position Sizing Orchestrator."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest
from unittest.mock import MagicMock

from trading_context.core.models import TradingContext
from market_intelligence.core.models import MarketState, VolumeState
from market_intelligence.core.enums import VolumeExpansionState
from risk_engine.core.models import RiskAssessment
from risk_engine.core.enums import RiskDecision
from strategy.core.models import StrategyState
from position_sizing.core.exceptions import OrchestratorError
from position_sizing.core.enums import SizingStatus
from position_sizing.core.models import PositionSizingState
from position_sizing.core.orchestrator import PositionSizingOrchestrator
from position_sizing.core.state import PositionSizingStateStore
from position_sizing.core.repository import PositionSizingRepository
from position_sizing.analysis.position_engine import PositionSizingEngine


@pytest.fixture
def dummy_context() -> TradingContext:
    dt = datetime.now(timezone.utc)
    volume_state = VolumeState(
        symbol="BTCUSDT",
        timeframe="1h",
        volume_ma=100.0,
        normalized_volume=1.0,
        expansion_state=VolumeExpansionState.NORMAL,
        atr=2.5,
    )
    market_state = MarketState(
        symbol="BTCUSDT",
        timeframe="1h",
        volume=volume_state,
        updated_at=dt,
    )
    strategy_state = StrategyState(symbol="BTCUSDT", timeframe="1h", updated_at=dt)
    return TradingContext(
        symbol="BTCUSDT",
        timeframe="1h",
        market_state=market_state,
        strategy_state=strategy_state,
        generated_at=dt,
    )


def test_orchestrator_initialization_errors(dummy_context):
    """Verify orchestrator errors if run before initialization."""
    orch = PositionSizingOrchestrator()
    risk = RiskAssessment(overall_score=95.0, decision=RiskDecision.ALLOW)

    with pytest.raises(OrchestratorError):
        orch.process_context(dummy_context, risk)


def test_orchestrator_process_context_success(dummy_context):
    """Verify orchestrator processes size requests, stores snapshots, and dispatches events."""
    state_store = PositionSizingStateStore()
    repo = PositionSizingRepository()
    engine = PositionSizingEngine()
    event_bus = MagicMock()

    orch = PositionSizingOrchestrator()
    orch.initialize(
        state_store=state_store,
        repository=repo,
        sizing_engine=engine,
        event_bus=event_bus,
    )

    risk = RiskAssessment(overall_score=95.0, decision=RiskDecision.ALLOW)

    state = orch.process_context(
        dummy_context,
        risk,
        account_balance=100000.0,
        entry_price=100.0,
        risk_percent=0.001,
        stop_distance=5.0,
        take_profit_distance=10.0,
    )

    assert state is not None
    assert state.result.success
    assert state.result.status == SizingStatus.APPROVED

    # Check store contains snapshot
    snap = state_store.get_snapshot("BTCUSDT")
    assert snap is not None
    assert snap.states["1h"].result.success

    # Check repository contains snapshot
    loaded = repo.load_latest_snapshot("BTCUSDT")
    assert loaded is not None
    assert loaded.snapshot_id == snap.snapshot_id

    # Check events were published
    assert event_bus.publish.call_count >= 2
