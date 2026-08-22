"""Unit and integration tests for Phase 12B — Sprint 4."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone, timedelta
import pytest

from data.schemas.market_data import OHLCV
from market_intelligence.core.analysis.engine import CoreAnalysisEngine
from market_intelligence.core.enums import (
    SessionName,
    TrendDirection,
    MarketRegime,
    VolumeExpansionState,
)
from market_intelligence.core.models import (
    MarketSnapshot,
    MarketState,
    TrendState,
    VolumeState,
)
from market_intelligence.core.state import MarketIntelligenceState
from toji_platform.core.event_bus import InMemoryEventBus


def make_candle(
    idx: int,
    open_p: float,
    high_p: float,
    low_p: float,
    close_p: float,
    vol: float = 100.0,
    symbol: str = "BTCUSDT",
    interval: str = "1h",
    hour_override: int | None = None,
) -> OHLCV:
    """Helper to generate deterministic OHLCV candles."""
    dt = datetime(2026, 6, 26, 10, 0, tzinfo=timezone.utc) + timedelta(hours=idx)
    if hour_override is not None:
        dt = dt.replace(hour=hour_override)
    return OHLCV(
        symbol=symbol,
        timestamp=dt,
        open=open_p,
        high=high_p,
        low=low_p,
        close=close_p,
        volume=vol,
        interval=interval,
    )


def test_session_engine():
    """Verify Session Engine transitions, timezone boundaries, overlaps, and breakout events."""
    bus = InMemoryEventBus()
    engine = CoreAnalysisEngine(event_bus=bus, k=2)
    session_engine = engine.get_session_engine()

    # 1. Verify active session list for different hours
    # 23:00 UTC -> Sydney active, Tokyo inactive
    active_23 = session_engine.get_active_sessions_for_time(datetime(2026, 6, 26, 23, 0, tzinfo=timezone.utc))
    assert SessionName.SYDNEY in active_23
    assert SessionName.TOKYO not in active_23

    # 00:00 UTC -> Sydney and Tokyo overlap
    active_0 = session_engine.get_active_sessions_for_time(datetime(2026, 6, 26, 0, 0, tzinfo=timezone.utc))
    assert SessionName.SYDNEY in active_0
    assert SessionName.TOKYO in active_0

    # 08:00 UTC -> Tokyo, London overlap
    active_8 = session_engine.get_active_sessions_for_time(datetime(2026, 6, 26, 8, 0, tzinfo=timezone.utc))
    assert SessionName.TOKYO in active_8
    assert SessionName.LONDON in active_8

    # 14:00 UTC -> London, New York overlap
    active_14 = session_engine.get_active_sessions_for_time(datetime(2026, 6, 26, 14, 0, tzinfo=timezone.utc))
    assert SessionName.LONDON in active_14
    assert SessionName.NEW_YORK in active_14

    # 2. Process candles during a session
    # Feed candles during London session (08:00 to 10:00 UTC)
    candles = [
        make_candle(0, 100.0, 105.0, 95.0, 100.0, hour_override=8),
        make_candle(1, 100.0, 110.0, 92.0, 105.0, hour_override=9),
        make_candle(2, 105.0, 120.0, 90.0, 110.0, hour_override=10),
    ]

    for c in candles:
        state = engine.analyze_candle(c)

    assert state.session is not None
    assert state.session.session_name == SessionName.LONDON
    assert state.session.session_open == 100.0
    assert state.session.session_high == 120.0
    assert state.session.session_low == 90.0
    assert state.session.session_close == 110.0
    assert not state.session.is_broken

    # 3. Verify session breakout (close above London high of 120 after London ends)
    # London ends at 17:00 UTC. At 18:00 UTC, close is 125.0
    breakout_candle = make_candle(3, 110.0, 130.0, 105.0, 125.0, hour_override=18)
    
    breakout_events = []
    bus.subscribe("system.session_breakout", breakout_events.append)
    
    state = engine.analyze_candle(breakout_candle)
    
    # Verify breakout event triggered
    assert len(breakout_events) == 1
    assert breakout_events[0].payload["session_name"] == "LONDON"
    assert breakout_events[0].payload["direction"] == "BULLISH"
    assert breakout_events[0].payload["level_breached"] == 120.0


def test_mtf_engine():
    """Verify Multi-Timeframe Alignment calculations: scores, confirmations, and trends."""
    bus = InMemoryEventBus()
    state_store = MarketIntelligenceState()
    engine = CoreAnalysisEngine(event_bus=bus, k=2, state_store=state_store)

    # Setup snapshots for 1m, 5m, 15m, 1h, 4h, 1d in state store
    # 4 timeframes have BULLISH/UP, 2 have BEARISH/DOWN -> dominant should be UP
    snapshot = MarketSnapshot(
        snapshot_id=str(uuid.uuid4()),
        symbol="BTCUSDT",
        timestamp=datetime.now(timezone.utc),
        states={
            "1m": MarketState(symbol="BTCUSDT", timeframe="1m", trend=TrendState(symbol="BTCUSDT", timeframe="1m", direction=TrendDirection.UP, strength=1.0, start_time=datetime.now(timezone.utc), end_time=datetime.now(timezone.utc)), market_phase_state="Unknown"),
            "5m": MarketState(symbol="BTCUSDT", timeframe="5m", trend=TrendState(symbol="BTCUSDT", timeframe="5m", direction=TrendDirection.UP, strength=1.0, start_time=datetime.now(timezone.utc), end_time=datetime.now(timezone.utc)), market_phase_state="Unknown"),
            "15m": MarketState(symbol="BTCUSDT", timeframe="15m", trend=TrendState(symbol="BTCUSDT", timeframe="15m", direction=TrendDirection.DOWN, strength=1.0, start_time=datetime.now(timezone.utc), end_time=datetime.now(timezone.utc)), market_phase_state="Unknown"),
            "1h": MarketState(symbol="BTCUSDT", timeframe="1h", trend=TrendState(symbol="BTCUSDT", timeframe="1h", direction=TrendDirection.UP, strength=1.0, start_time=datetime.now(timezone.utc), end_time=datetime.now(timezone.utc)), market_phase_state="Unknown"),
            "4h": MarketState(symbol="BTCUSDT", timeframe="4h", trend=TrendState(symbol="BTCUSDT", timeframe="4h", direction=TrendDirection.DOWN, strength=1.0, start_time=datetime.now(timezone.utc), end_time=datetime.now(timezone.utc)), market_phase_state="Unknown"),
        }
    )
    state_store.update_snapshot(snapshot)

    # Invoke process_alignment directly on mtf_engine to prevent internal trend engines overriding
    c = make_candle(0, 100, 105, 95, 102, interval="1d")
    mtf_engine = engine.get_mtf_engine()
    alignment = mtf_engine.process_alignment(
        symbol="BTCUSDT",
        current_timeframe="1d",
        current_trend_dir="BULLISH",
        timestamp=c.timestamp,
    )

    # Trends: 1m=UP, 5m=UP, 15m=DOWN, 1h=UP, 4h=DOWN, 1d=UP -> 4 UP, 2 DOWN.
    # Dominant = UP. Alignment score = 4 / 6 = 0.67. Conflict = 2 / 6 = 0.33.
    assert alignment.dominant_trend == TrendDirection.UP
    assert round(alignment.alignment_score, 2) == 0.67
    assert round(alignment.conflict_score, 2) == 0.33
    # 1d is the highest timeframe, so higher TF confirmation is True by definition
    assert alignment.higher_timeframe_confirmation is True


def test_market_regime_engine():
    """Verify deterministic Market Regime classification: volatile, contraction, accumulation, etc."""
    bus = InMemoryEventBus()
    engine = CoreAnalysisEngine(event_bus=bus, k=2)

    # 1. Verify Volatile Regime
    # High ATR or climatic volume expansion triggers VOLATILE
    # First feed normal volume candles
    for i in range(20):
        engine.analyze_candle(make_candle(i, 100, 105, 95, 100, vol=100.0))

    # Climatic volume candle (1000.0) -> VOLATILE regime
    climatic_candle = make_candle(20, 100, 105, 95, 100, vol=1000.0)
    state = engine.analyze_candle(climatic_candle)
    assert state.market_context.regime == MarketRegime.VOLATILE

    # 2. Verify Accumulation / Distribution Regimes
    # Patch the state machine so it holds the "Accumulation" phase state.
    # Without patching, update_state overwrites to "Unknown" when trend_direction is UNKNOWN
    # (flat candles produce no swing structure for trend detection).
    original_update = engine._state_machine.update_state

    def _patched_update(symbol, timeframe, *args, **kwargs):
        engine._state_machine._states[(symbol, timeframe)] = "Accumulation"
        return "Accumulation"

    engine._state_machine.update_state = _patched_update
    # Feed with volume=200 to keep normalized_volume > 0.8 and prevent Contraction
    state = engine.analyze_candle(make_candle(21, 100, 101, 99, 100, vol=200.0))
    # It should classify as ACCUMULATION (priority over default TRENDING/RANGING)
    assert state.market_context.regime == MarketRegime.ACCUMULATION
    # Restore original
    engine._state_machine.update_state = original_update


def test_correlation_engine():
    """Verify rolling Pearson and Spearman correlations between BTC and ETH/SOL."""
    bus = InMemoryEventBus()
    engine = CoreAnalysisEngine(event_bus=bus, k=2)

    # Feed 15 candles for BTCUSDT
    for i in range(15):
        engine.analyze_candle(make_candle(i, 100.0 + i, 105.0 + i, 95.0 + i, 100.0 + i, symbol="BTCUSDT"))

    # Feed 15 identical candles for ETHUSDT
    for i in range(15):
        engine.analyze_candle(make_candle(i, 100.0 + i, 105.0 + i, 95.0 + i, 100.0 + i, symbol="ETHUSDT"))

    # Now feed one more BTCUSDT candle. It should compute correlation with ETHUSDT.
    # Since prices are identical, correlation should be 1.0
    state = engine.analyze_candle(make_candle(15, 115.0, 120.0, 110.0, 115.0, symbol="BTCUSDT"))

    assert state.market_context is not None
    corrs = state.market_context.correlation
    assert "ETHUSDT_pearson" in corrs
    assert "ETHUSDT_spearman" in corrs
    assert round(corrs["ETHUSDT_pearson"], 2) == 1.0
    assert round(corrs["ETHUSDT_spearman"], 2) == 1.0


def test_sprint4_replay_determinism():
    """Verify streaming processing matches historical replay exactly for context and regime."""
    candles = [make_candle(i, 100 + i, 105 + i, 95 + i, 100 + i, vol=100.0) for i in range(25)]

    # Stream
    engine_stream = CoreAnalysisEngine(k=2)
    for c in candles:
        state_stream = engine_stream.analyze_candle(c)

    # Replay
    engine_replay = CoreAnalysisEngine(k=2)
    for c in candles:
        state_replay = engine_replay.analyze_candle(c)

    # Compare contexts
    assert state_stream.market_context.dominant_trend == state_replay.market_context.dominant_trend
    assert state_stream.market_context.regime == state_replay.market_context.regime
    assert state_stream.market_context.alignment.dominant_trend == state_replay.market_context.alignment.dominant_trend


def test_sprint4_performance_latency():
    """Verify mean processing latency remains below 5 milliseconds per candle for the expanded pipeline."""
    candles = [make_candle(i, 100.0, 105.0, 95.0, 100.0, vol=100.0) for i in range(500)]
    engine = CoreAnalysisEngine(k=2)

    # Warmup
    for i in range(50):
        engine.analyze_candle(candles[i])

    # Benchmark
    start_time = time.perf_counter()
    for i in range(50, 500):
        engine.analyze_candle(candles[i])
    end_time = time.perf_counter()

    elapsed_ms = (end_time - start_time) * 1000.0
    mean_latency = elapsed_ms / 450.0

    print(f"Sprint 4 Pipeline latency: {mean_latency:.4f} ms per candle.")
    assert mean_latency < 5.0, f"Latency of {mean_latency:.4f} ms exceeded the 5 ms budget!"
