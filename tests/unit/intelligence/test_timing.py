"""Unit tests for the Timing Engine."""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone
from intelligence.timing.engine import TimingEngine


@pytest.fixture
def engine() -> TimingEngine:
    """Provide a TimingEngine instance."""
    return TimingEngine(
        half_life_seconds=600.0,  # 10 minutes decay half-life
        max_age_seconds=1800.0,   # 30 minutes max age
        event_buffer_seconds=300.0, # 5 minutes macro event buffer
    )


def test_calculate_signal_decay(engine: TimingEngine) -> None:
    """Test exponential decay score over elapsed time."""
    now = datetime.now(timezone.utc)
    fresh_time = now
    decayed_half = now - timedelta(seconds=600)
    fully_decayed = now - timedelta(seconds=1900)

    assert engine.calculate_signal_decay(fresh_time, now) == 1.0
    assert pytest.approx(engine.calculate_signal_decay(decayed_half, now), 0.01) == 0.5
    assert engine.calculate_signal_decay(fully_decayed, now) == 0.0


def test_get_market_session(engine: TimingEngine) -> None:
    """Test session classification based on UTC hours."""
    # NY session
    dt_ny = datetime(2026, 6, 25, 18, 0, 0, tzinfo=timezone.utc)
    assert engine.get_market_session(dt_ny) == "NewYork"

    # London session
    dt_ldn = datetime(2026, 6, 25, 10, 0, 0, tzinfo=timezone.utc)
    assert engine.get_market_session(dt_ldn) == "London"

    # Overlap NY-London
    dt_overlap = datetime(2026, 6, 25, 14, 30, 0, tzinfo=timezone.utc)
    assert engine.get_market_session(dt_overlap) == "Overlap"

    # Asia session
    dt_asia = datetime(2026, 6, 25, 4, 0, 0, tzinfo=timezone.utc)
    assert engine.get_market_session(dt_asia) == "Asia"

    # Quiet session
    dt_quiet = datetime(2026, 6, 25, 22, 0, 0, tzinfo=timezone.utc)
    assert engine.get_market_session(dt_quiet) == "Quiet"


def test_get_event_proximity(engine: TimingEngine) -> None:
    """Test event distance computation and unsafe buffers."""
    now = datetime.now(timezone.utc)
    macro_event_near = now + timedelta(seconds=120)  # 2 mins
    macro_event_far = now + timedelta(seconds=600)   # 10 mins

    offset_near, is_unsafe_near = engine.get_event_proximity(now, [macro_event_near, macro_event_far])
    assert offset_near == 120.0
    assert is_unsafe_near is True

    offset_far, is_unsafe_far = engine.get_event_proximity(now, [macro_event_far])
    assert offset_far == 600.0
    assert is_unsafe_far is False


def test_determine_execution_window(engine: TimingEngine) -> None:
    """Test full execution window logic mapping to timing states."""
    now = datetime.now(timezone.utc)
    fresh_signal = now
    old_signal = now - timedelta(seconds=1000)
    expired_signal = now - timedelta(seconds=2000)
    macro_event = now + timedelta(seconds=120)

    # 1. Fresh signal (Crypto) -> Immediate
    assert engine.determine_execution_window(fresh_signal, now, is_crypto=True) == "Immediate"

    # 2. Expired signal -> Expired
    assert engine.determine_execution_window(expired_signal, now, is_crypto=True) == "Expired"

    # 3. Fresh signal but event proximity risk -> Blocked
    assert engine.determine_execution_window(fresh_signal, now, event_times=[macro_event], is_crypto=True) == "Blocked"

    # 4. Old but not expired signal -> Delayed (pullback check)
    assert engine.determine_execution_window(old_signal, now, is_crypto=True) == "Delayed"

    # 5. Non-crypto during Quiet session hours -> Deferred
    quiet_time = datetime(2026, 6, 25, 22, 0, 0, tzinfo=timezone.utc)
    assert engine.determine_execution_window(quiet_time, quiet_time, is_crypto=False) == "Deferred"
