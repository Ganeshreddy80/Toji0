"""Unit tests for the Confluence Orchestrator."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from market_intelligence.core.state import MarketIntelligenceState
from market_intelligence.core.models import MarketState, MarketSnapshot
from price_action.core.state import PriceActionStateStore
from price_action.core.models import PatternState, PatternSnapshot
from toji_platform.core.event_bus import InMemoryEventBus
from confluence.core.enums import SetupGrade
from confluence.core.exceptions import OrchestratorError
from confluence.core.state import ConfluenceStateStore
from confluence.core.repository import ConfluenceRepository
from confluence.analysis.confluence_engine import ConfluenceEngine
from confluence.core.orchestrator import ConfluenceOrchestrator


def test_orchestrator_uninitialized_raises():
    """Verify that orchestrator raises error if not initialized."""
    orch = ConfluenceOrchestrator()
    with pytest.raises(OrchestratorError):
        orch.process_confluence("BTCUSDT", "1h")


def test_orchestrator_full_coordination():
    """Verify orchestrator coordinates execution, state store updates, repo saves, and event publishing."""
    # 1. Setup mock components and event bus
    bus = InMemoryEventBus()
    state_store = ConfluenceStateStore()
    repo = ConfluenceRepository()
    engine = ConfluenceEngine()

    market_state_store = MarketIntelligenceState()
    pattern_state_store = PriceActionStateStore()

    # Create & initialize orchestrator
    orch = ConfluenceOrchestrator()
    orch.initialize(
        confluence_engine=engine,
        state_store=state_store,
        repository=repo,
        event_bus=bus,
        market_state_store=market_state_store,
        pattern_state_store=pattern_state_store,
    )

    # Subscribe to confluence events
    events_received = []
    bus.subscribe("system.confluence_updated", events_received.append)
    bus.subscribe("system.setup_detected", events_received.append)

    # 2. Populate source state stores
    dt = datetime.now(timezone.utc)
    market_state = MarketState(
        symbol="BTCUSDT",
        timeframe="1h",
        updated_at=dt,
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

    # 3. Process confluence
    conf_state = orch.process_confluence("BTCUSDT", "1h")

    # 4. Verify output State
    assert conf_state.symbol == "BTCUSDT"
    assert conf_state.timeframe == "1h"
    # Scored baseline/empty yields C under Sprint 6 grade thresholds
    assert conf_state.score.setup_grade == SetupGrade.C

    # 5. Verify confluence state store updated
    snapshot = state_store.get_snapshot("BTCUSDT")
    assert snapshot is not None
    assert "1h" in snapshot.states
    assert snapshot.states["1h"].score.overall_score == conf_state.score.overall_score

    # 6. Verify repository saved snapshot
    latest_repo = repo.load_latest_snapshot("BTCUSDT")
    assert latest_repo is not None
    assert latest_repo.snapshot_id == snapshot.snapshot_id

    # 7. Verify ConfluenceUpdated event dispatched
    assert len(events_received) == 1
    assert events_received[0].event_type == "system.confluence_updated"
    assert events_received[0].payload["symbol"] == "BTCUSDT"
    assert events_received[0].payload["timeframe"] == "1h"
