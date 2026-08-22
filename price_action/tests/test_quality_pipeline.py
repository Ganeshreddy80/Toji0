"""Integration tests for the Pattern Quality Engine pipeline execution."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from market_intelligence.core.enums import SwingType
from market_intelligence.core.models import MarketState, SwingPoint
from price_action.core.enums import PatternDirection, PatternStatus, PatternType
from price_action.core.events import PatternQualityUpdated
from price_action.analysis.pattern_engine import PatternEngine
from price_action.quality.quality_engine import PatternQualityEngine
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


def test_quality_pipeline_execution():
    """Verify that quality evaluation runs in the orchestrator pipeline and fires events."""
    bus = InMemoryEventBus()
    state_store = PriceActionStateStore()
    repo = PriceActionRepository()
    engine = PatternEngine()
    
    # We clear and only use TriangleDetector to isolate the test
    engine._detectors.clear()
    from price_action.analysis.triangle_detector import TriangleDetector
    engine.register_detector(TriangleDetector(container=None))

    quality_engine = PatternQualityEngine()

    orch = PriceActionOrchestrator()
    orch.initialize(
        pattern_engine=engine,
        state_store=state_store,
        repository=repo,
        event_bus=bus,
        quality_engine=quality_engine,
    )

    quality_events = []
    bus.subscribe("system.pattern_quality_updated", quality_events.append)

    # Candidate is detected (Ascending Triangle consolidation)
    swings = [
        make_swing(10, 100.0, SwingType.HIGH),
        make_swing(15, 80.0, SwingType.LOW),
        make_swing(20, 100.0, SwingType.HIGH),
        make_swing(25, 85.0, SwingType.LOW),
        make_swing(30, 100.0, SwingType.HIGH),
        make_swing(35, 90.0, SwingType.LOW),
    ]

    market_state = MarketState(
        symbol="BTCUSDT",
        timeframe="1h",
        swings=swings,
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

    pattern_state = orch.process_market_state(market_state)

    # Verify candidate is populated with quality
    assert len(pattern_state.candidate_patterns) == 1
    candidate = pattern_state.candidate_patterns[0]
    assert candidate.quality is not None
    assert candidate.quality.overall_score > 0.0

    # Verify event was dispatched
    assert len(quality_events) == 1
    event = quality_events[0]
    assert isinstance(event, PatternQualityUpdated)
    assert event.payload["pattern_id"] == candidate.candidate_id
    assert event.payload["quality"]["overall_score"] == candidate.quality.overall_score
