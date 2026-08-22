"""Integration tests for the Price Action Engine pipeline execution, lifecycle transitions, and event bus."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from market_intelligence.core.enums import SwingType
from market_intelligence.core.models import MarketState, SwingPoint
from price_action.core.enums import PatternDirection, PatternStatus, PatternType
from price_action.core.events import (
    PatternCompleted,
    PatternConfirmed,
    PatternDetected,
    PatternInvalidated,
    PatternUpdated,
)
from price_action.analysis.pattern_engine import PatternEngine
from price_action.core.orchestrator import PriceActionOrchestrator
from price_action.core.state import PriceActionStateStore
from price_action.core.repository import PriceActionRepository
from toji_platform.core.event_bus import InMemoryEventBus


def make_swing(index: int, price: float, point_type: SwingType) -> SwingPoint:
    return SwingPoint(
        symbol="BTCUSDT",
        timeframe="1h",
        point_type=point_type,
        price=price,
        timestamp=datetime.fromtimestamp(index * 3600, tz=timezone.utc),
        index=index,
    )


def test_pattern_pipeline_lifecycle_transitions():
    """Verify the pattern pipeline lifecycle: candidate -> confirmed -> completed/invalidated."""
    bus = InMemoryEventBus()
    state_store = PriceActionStateStore()
    repo = PriceActionRepository()
    engine = PatternEngine()
    engine._detectors.clear()
    from price_action.analysis.triangle_detector import TriangleDetector
    engine.register_detector(TriangleDetector(container=None))
    
    orch = PriceActionOrchestrator()
    orch.initialize(
        pattern_engine=engine,
        state_store=state_store,
        repository=repo,
        event_bus=bus,
    )

    events = []
    bus.subscribe("system.pattern_detected", lambda event: events.append(("detected", event)))
    bus.subscribe("system.pattern_confirmed", lambda event: events.append(("confirmed", event)))
    bus.subscribe("system.pattern_completed", lambda event: events.append(("completed", event)))
    bus.subscribe("system.pattern_invalidated", lambda event: events.append(("invalidated", event)))

    # Step 1: Candidate is detected (Ascending Triangle consolidation)
    swings_1 = [
        make_swing(10, 100.0, SwingType.HIGH),
        make_swing(15, 80.0, SwingType.LOW),
        make_swing(20, 100.0, SwingType.HIGH),
        make_swing(25, 85.0, SwingType.LOW),
        make_swing(30, 100.0, SwingType.HIGH),
        make_swing(35, 90.0, SwingType.LOW),  # Consolidation inside boundaries
    ]
    state_1 = MarketState(
        symbol="BTCUSDT",
        timeframe="1h",
        swings=swings_1,
        trend=None,
        liquidity=None,
        zones=[],
        session=None,
        volume=None,
        context=None,
        confidence=None,
        story=None,
        structure_history=[],
        bos_history=[],
        choch_history=[],
        sr_levels=[],
        market_phase_state="Unknown",
        market_context=None,
        updated_at=datetime.now(timezone.utc),
    )
    
    pattern_state_1 = orch.process_market_state(state_1)
    
    # Verify candidate detected
    assert len(pattern_state_1.candidate_patterns) == 1
    assert len(pattern_state_1.active_patterns) == 0
    assert any(e[0] == "detected" for e in events)
    events.clear()

    # Step 2: Breakout occurs (Confirmed match)
    swings_2 = list(swings_1)
    swings_2[-1] = make_swing(35, 105.0, SwingType.HIGH)  # High breakout!
    state_2 = MarketState(
        symbol="BTCUSDT",
        timeframe="1h",
        swings=swings_2,
        trend=None,
        liquidity=None,
        zones=[],
        session=None,
        volume=None,
        context=None,
        confidence=None,
        story=None,
        structure_history=[],
        bos_history=[],
        choch_history=[],
        sr_levels=[],
        market_phase_state="Unknown",
        market_context=None,
        updated_at=datetime.now(timezone.utc),
    )
    
    pattern_state_2 = orch.process_market_state(state_2)
    
    # Verify pattern confirmed
    assert len(pattern_state_2.active_patterns) == 1
    assert any(e[0] == "confirmed" for e in events)
    events.clear()

    # Step 3: Target is reached (Completed match)
    # Target height = max(100) - min(80) = 20. Breakout price around 100. Target = 120.0
    swings_3 = list(swings_2)
    swings_3.append(make_swing(40, 125.0, SwingType.HIGH))  # Price hits target level
    state_3 = MarketState(
        symbol="BTCUSDT",
        timeframe="1h",
        swings=swings_3,
        trend=None,
        liquidity=None,
        zones=[],
        session=None,
        volume=None,
        context=None,
        confidence=None,
        story=None,
        structure_history=[],
        bos_history=[],
        choch_history=[],
        sr_levels=[],
        market_phase_state="Unknown",
        market_context=None,
        updated_at=datetime.now(timezone.utc),
    )
    
    pattern_state_3 = orch.process_market_state(state_3)
    
    # Verify pattern is completed
    assert len(pattern_state_3.active_patterns) == 0
    assert len(pattern_state_3.historical_patterns) == 1
    assert pattern_state_3.historical_patterns[0].status == PatternStatus.COMPLETED
    assert any(e[0] == "completed" for e in events)


def test_pattern_pipeline_invalidation():
    """Verify the pattern pipeline invalidation transition."""
    bus = InMemoryEventBus()
    state_store = PriceActionStateStore()
    repo = PriceActionRepository()
    engine = PatternEngine()
    engine._detectors.clear()
    from price_action.analysis.triangle_detector import TriangleDetector
    engine.register_detector(TriangleDetector(container=None))
    
    orch = PriceActionOrchestrator()
    orch.initialize(
        pattern_engine=engine,
        state_store=state_store,
        repository=repo,
        event_bus=bus,
    )

    events = []
    bus.subscribe("system.pattern_invalidated", lambda event: events.append(("invalidated", event)))

    # Step 1: Confirmed breakout
    swings_1 = [
        make_swing(10, 100.0, SwingType.HIGH),
        make_swing(15, 80.0, SwingType.LOW),
        make_swing(20, 100.0, SwingType.HIGH),
        make_swing(25, 85.0, SwingType.LOW),
        make_swing(30, 100.0, SwingType.HIGH),
        make_swing(35, 105.0, SwingType.HIGH),  # Breakout
    ]
    state_1 = MarketState(
        symbol="BTCUSDT",
        timeframe="1h",
        swings=swings_1,
        trend=None,
        liquidity=None,
        zones=[],
        session=None,
        volume=None,
        context=None,
        confidence=None,
        story=None,
        structure_history=[],
        bos_history=[],
        choch_history=[],
        sr_levels=[],
        market_phase_state="Unknown",
        market_context=None,
        updated_at=datetime.now(timezone.utc),
    )
    orch.process_market_state(state_1)

    # Step 2: Price falls below invalidation level (min price of pattern is 80.0)
    swings_2 = list(swings_1)
    swings_2.append(make_swing(40, 75.0, SwingType.LOW))  # Breach invalidation level
    state_2 = MarketState(
        symbol="BTCUSDT",
        timeframe="1h",
        swings=swings_2,
        trend=None,
        liquidity=None,
        zones=[],
        session=None,
        volume=None,
        context=None,
        confidence=None,
        story=None,
        structure_history=[],
        bos_history=[],
        choch_history=[],
        sr_levels=[],
        market_phase_state="Unknown",
        market_context=None,
        updated_at=datetime.now(timezone.utc),
    )
    pattern_state_2 = orch.process_market_state(state_2)

    # Verify pattern is invalidated
    invalidated_matches = [m for m in pattern_state_2.historical_patterns if m.match_id == "match-tri-BTCUSDT-1h-35"]
    assert len(invalidated_matches) == 1
    assert invalidated_matches[0].status == PatternStatus.INVALIDATED
    assert any(e[0] == "invalidated" for e in events)


def test_pattern_pipeline_replay_determinism():
    """Verify that processing the exact same sequence of states in replay yields identical outputs."""
    engine = PatternEngine()
    
    # Sequence of swing states
    swings_seq = [
        [
            make_swing(10, 100.0, SwingType.HIGH),
            make_swing(15, 80.0, SwingType.LOW),
            make_swing(20, 100.0, SwingType.HIGH),
            make_swing(25, 85.0, SwingType.LOW),
        ],
        [
            make_swing(10, 100.0, SwingType.HIGH),
            make_swing(15, 80.0, SwingType.LOW),
            make_swing(20, 100.0, SwingType.HIGH),
            make_swing(25, 85.0, SwingType.LOW),
            make_swing(30, 100.0, SwingType.HIGH),
            make_swing(35, 105.0, SwingType.HIGH),
        ]
    ]

    outputs_1 = []
    outputs_2 = []

    # Run 1
    state_store_1 = PriceActionStateStore()
    orch_1 = PriceActionOrchestrator()
    orch_1.initialize(engine, state_store_1, PriceActionRepository())
    for seq in swings_seq:
        ms = MarketState(
            symbol="BTCUSDT",
            timeframe="1h",
            swings=seq,
            trend=None,
            liquidity=None,
            zones=[],
            session=None,
            volume=None,
            context=None,
            confidence=None,
            story=None,
            structure_history=[],
            bos_history=[],
            choch_history=[],
            sr_levels=[],
            market_phase_state="Unknown",
            market_context=None,
            updated_at=datetime.fromtimestamp(1234567, tz=timezone.utc),
        )
        outputs_1.append(orch_1.process_market_state(ms))

    # Run 2 (Replay)
    state_store_2 = PriceActionStateStore()
    orch_2 = PriceActionOrchestrator()
    orch_2.initialize(engine, state_store_2, PriceActionRepository())
    for seq in swings_seq:
        ms = MarketState(
            symbol="BTCUSDT",
            timeframe="1h",
            swings=seq,
            trend=None,
            liquidity=None,
            zones=[],
            session=None,
            volume=None,
            context=None,
            confidence=None,
            story=None,
            structure_history=[],
            bos_history=[],
            choch_history=[],
            sr_levels=[],
            market_phase_state="Unknown",
            market_context=None,
            updated_at=datetime.fromtimestamp(1234567, tz=timezone.utc),
        )
        outputs_2.append(orch_2.process_market_state(ms))

    # Compare outputs model dumps
    for out1, out2 in zip(outputs_1, outputs_2):
        assert out1.model_dump() == out2.model_dump()
