"""Unit tests for the Strategy Orchestrator."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from market_intelligence.core.state import MarketIntelligenceState
from market_intelligence.core.models import MarketState, MarketSnapshot
from price_action.core.state import PriceActionStateStore
from price_action.core.models import PatternState, PatternSnapshot
from confluence.core.state import ConfluenceStateStore
from confluence.core.models import ConfluenceState, ConfluenceSnapshot, ConfluenceScore
from confluence.core.enums import SetupGrade
from toji_platform.core.event_bus import InMemoryEventBus
from strategy.core.enums import StrategyDecision, StrategyType
from strategy.core.exceptions import OrchestratorError
from strategy.core.state import StrategyStateStore
from strategy.core.repository import StrategyRepository
from strategy.analysis.strategy_engine import StrategyEngine
from strategy.core.orchestrator import StrategyOrchestrator


def test_orchestrator_uninitialized_raises():
    """Verify that orchestrator raises error if not initialized."""
    orch = StrategyOrchestrator()
    with pytest.raises(OrchestratorError):
        orch.process_strategy("BTCUSDT", "1h")


def test_orchestrator_full_coordination():
    """Verify orchestrator coordinates execution, state store updates, repo saves, and event publishing."""
    # 1. Setup components
    bus = InMemoryEventBus()
    state_store = StrategyStateStore()
    repo = StrategyRepository()
    engine = StrategyEngine()

    market_state_store = MarketIntelligenceState()
    pattern_state_store = PriceActionStateStore()
    confluence_state_store = ConfluenceStateStore()

    orch = StrategyOrchestrator()
    orch.initialize(
        strategy_engine=engine,
        state_store=state_store,
        repository=repo,
        event_bus=bus,
        market_state_store=market_state_store,
        pattern_state_store=pattern_state_store,
        confluence_state_store=confluence_state_store,
    )

    # Subscribe to strategy events
    events_received = []
    bus.subscribe("system.strategy_updated", events_received.append)
    bus.subscribe("system.strategy_signal", events_received.append)
    bus.subscribe("system.strategy_changed", events_received.append)
    bus.subscribe("system.strategy_rejected", events_received.append)

    # 2. Populate source states
    dt = datetime.now(timezone.utc)
    market_state = MarketState(
        symbol="BTCUSDT",
        timeframe="1h",
        updated_at=dt,
        market_phase_state="Unknown",
    )
    market_snapshot = MarketSnapshot(
        snapshot_id="ms-1",
        symbol="BTCUSDT",
        timestamp=dt,
        states={"1h": market_state},
    )
    market_state_store.update_snapshot(market_snapshot)

    pattern_state = PatternState(
        symbol="BTCUSDT",
        timeframe="1h",
        updated_at=dt,
    )
    pattern_snapshot = PatternSnapshot(
        snapshot_id="ps-1",
        symbol="BTCUSDT",
        timestamp=dt,
        states={"1h": pattern_state},
    )
    pattern_state_store.update_snapshot(pattern_snapshot)

    confluence_score = ConfluenceScore(
        overall_score=75.0,
        setup_grade=SetupGrade.B,
        trend_score=70.0,
        structure_score=70.0,
        liquidity_score=70.0,
        zone_score=70.0,
        volume_score=70.0,
        regime_score=70.0,
        session_score=70.0,
        mtf_score=70.0,
        correlation_score=70.0,
        pattern_score=70.0,
        quality_score=70.0,
        conflict_penalty=0.0,
        supporting_factors=[],
        conflicting_factors=[],
    )
    confluence_state = ConfluenceState(
        symbol="BTCUSDT",
        timeframe="1h",
        score=confluence_score,
        updated_at=dt,
    )
    confluence_snapshot = ConfluenceSnapshot(
        snapshot_id="cs-1",
        symbol="BTCUSDT",
        timestamp=dt,
        states={"1h": confluence_state},
    )
    confluence_state_store.update_snapshot(confluence_snapshot)

    # 3. Process strategy
    strat_state = orch.process_strategy("BTCUSDT", "1h")

    # 4. Verify output State (should default to WAIT since no buy/sell setups are triggered)
    assert strat_state.symbol == "BTCUSDT"
    assert strat_state.timeframe == "1h"
    assert strat_state.active_strategy is None
    assert strat_state.latest_signal is not None
    assert strat_state.latest_signal.decision == StrategyDecision.WAIT

    # 5. Verify state store updated
    snapshot = state_store.get_snapshot("BTCUSDT")
    assert snapshot is not None
    assert "1h" in snapshot.states
    assert snapshot.states["1h"].latest_signal.decision == StrategyDecision.WAIT

    # 6. Verify repository saved snapshot
    latest_repo = repo.load_latest_snapshot("BTCUSDT")
    assert latest_repo is not None
    assert latest_repo.snapshot_id == snapshot.snapshot_id

    # 7. Verify StrategyUpdated event dispatched
    assert len(events_received) == 1
    assert events_received[0].event_type == "system.strategy_updated"
    assert events_received[0].payload["symbol"] == "BTCUSDT"
    assert events_received[0].payload["timeframe"] == "1h"
