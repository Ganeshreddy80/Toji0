"""Unit tests for the pluggable Pattern Engine and Orchestrator coordination."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from market_intelligence.core.models import MarketState
from price_action.core.enums import PatternDirection, PatternStatus, PatternType
from price_action.core.exceptions import DetectorRegistrationError, OrchestratorError
from price_action.core.interfaces import IPatternDetector
from price_action.core.models import (
    PatternCandidate,
    PatternMatch,
    PatternPoint,
)
from price_action.analysis.pattern_engine import PatternEngine
from price_action.core.orchestrator import PriceActionOrchestrator
from price_action.core.state import PriceActionStateStore
from price_action.core.repository import PriceActionRepository
from toji_platform.core.event_bus import InMemoryEventBus


class DummyDetector(IPatternDetector):
    """Dummy pluggable pattern detector implementation for testing."""

    def __init__(self, detector_id: str = "dummy_double_top") -> None:
        self._detector_id = detector_id

    @property
    def detector_id(self) -> str:
        return self._detector_id

    def detect(self, market_state: DetectorContext | MarketState) -> tuple[list[PatternCandidate], list[PatternMatch]]:
        from price_action.core.models import DetectorContext
        if isinstance(market_state, DetectorContext):
            market_state = market_state.market_state
        dt = market_state.updated_at
        p1 = PatternPoint(price=100.0, timestamp=dt, index=5, point_label="A")
        p2 = PatternPoint(price=102.0, timestamp=dt, index=10, point_label="B")

        candidate = PatternCandidate(
            candidate_id="cand-1",
            symbol=market_state.symbol,
            timeframe=market_state.timeframe,
            pattern_type=PatternType.DOUBLE_TOP,
            direction=PatternDirection.BEARISH,
            points=[p1, p2],
            score=0.9,
            detected_at=dt,
        )

        match = PatternMatch(
            match_id="match-1",
            symbol=market_state.symbol,
            timeframe=market_state.timeframe,
            pattern_type=PatternType.DOUBLE_TOP,
            direction=PatternDirection.BEARISH,
            status=PatternStatus.CONFIRMED,
            points=[p1, p2],
            fit_score=0.92,
            confirmed_at=dt,
        )

        return [candidate], [match]


def test_pattern_engine_detector_registration():
    """Verify registration, duplication protection, and removal of engines in PatternEngine."""
    engine = PatternEngine()
    detector = DummyDetector("detector_a")

    # 1. Successful registration
    engine.register_detector(detector)
    assert "detector_a" in engine._detectors

    # 2. Duplicate registration protection
    with pytest.raises(DetectorRegistrationError):
        engine.register_detector(detector)

    # 3. Successful removal
    engine.remove_detector("detector_a")
    assert "detector_a" not in engine._detectors

    # 4. Removing non-existent raises error
    with pytest.raises(DetectorRegistrationError):
        engine.remove_detector("detector_a")


def test_orchestrator_uninitialized_raises():
    """Verify that orchestrator raises error if not initialized."""
    orch = PriceActionOrchestrator()
    dt = datetime.now(timezone.utc)
    market_state = MarketState(
        symbol="BTCUSDT",
        timeframe="1h",
        swings=[],
        trend=None,
        liquidity=None,
        zones=[],
        session=None,
        volume=None,
        sr_levels=[],
        structure_history=[],
        bos_history=[],
        choch_history=[],
        market_phase_state="Unknown",
        market_context=None,
        updated_at=dt,
    )

    with pytest.raises(OrchestratorError):
        orch.process_market_state(market_state)


def test_orchestrator_full_coordination():
    """Verify pluggable detectors, state updates, repo, and event bus dispatching via Orchestrator."""
    bus = InMemoryEventBus()
    state_store = PriceActionStateStore()
    repo = PriceActionRepository()
    engine = PatternEngine()
    
    detector = DummyDetector("dummy")
    engine.register_detector(detector)

    orch = PriceActionOrchestrator()
    orch.initialize(
        pattern_engine=engine,
        state_store=state_store,
        repository=repo,
        event_bus=bus,
    )

    # Setup events subscriptions
    events_received = []
    bus.subscribe("system.pattern_detected", events_received.append)
    bus.subscribe("system.pattern_confirmed", events_received.append)

    # Run orchestrator
    dt = datetime.now(timezone.utc)
    market_state = MarketState(
        symbol="BTCUSDT",
        timeframe="1h",
        swings=[],
        trend=None,
        liquidity=None,
        zones=[],
        session=None,
        volume=None,
        sr_levels=[],
        structure_history=[],
        bos_history=[],
        choch_history=[],
        market_phase_state="Unknown",
        market_context=None,
        updated_at=dt,
    )

    pattern_state = orch.process_market_state(market_state)

    # 1. Verify returns PatternState correctly
    assert pattern_state.symbol == "BTCUSDT"
    assert len(pattern_state.candidate_patterns) == 1
    assert len(pattern_state.active_patterns) == 1

    # 2. Verify state store has update
    snapshot = state_store.get_snapshot("BTCUSDT")
    assert snapshot is not None
    assert "1h" in snapshot.states

    # 3. Verify repository saved snapshot
    latest_repo = repo.load_latest_snapshot("BTCUSDT")
    assert latest_repo is not None
    assert latest_repo.snapshot_id == snapshot.snapshot_id

    # 4. Verify events dispatched
    assert len(events_received) == 2
    event_types = {e.event_type for e in events_received}
    assert "system.pattern_detected" in event_types
    assert "system.pattern_confirmed" in event_types
