"""Unit and integration tests for Phase 12B — Sprint 3."""

from __future__ import annotations

import time
from datetime import datetime, timezone, timedelta
import pytest

from data.schemas.market_data import OHLCV
from market_intelligence.core.analysis.engine import CoreAnalysisEngine
from market_intelligence.core.enums import SwingType, ZoneType, VolumeExpansionState
from market_intelligence.core.models import SwingPoint
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
) -> OHLCV:
    """Helper to generate deterministic OHLCV candles."""
    return OHLCV(
        symbol=symbol,
        timestamp=datetime(2026, 6, 26, 10, 0, tzinfo=timezone.utc) + timedelta(hours=idx),
        open=open_p,
        high=high_p,
        low=low_p,
        close=close_p,
        volume=vol,
        interval=interval,
    )


def test_volume_context_engine():
    """Verify Volume Context Engine tracking: ATR, SMA, RVOL, expansion states, anomalies, and events."""
    bus = InMemoryEventBus()
    engine = CoreAnalysisEngine(event_bus=bus, k=2)

    events = []
    bus.subscribe("system.volume_context_updated", events.append)

    # Feed 20 candles with high volume variance (alternating between 50 and 150)
    for i in range(20):
        vol = 50.0 if i % 2 == 0 else 150.0
        candle = make_candle(i, 100.0, 105.0, 95.0, 100.0, vol=vol)
        engine.analyze_candle(candle)

    # 21st candle has normal volume
    c21 = make_candle(20, 100.0, 105.0, 95.0, 100.0, vol=100.0)
    state = engine.analyze_candle(c21)
    assert state.volume is not None
    assert state.volume.expansion_state == VolumeExpansionState.NORMAL

    # 22nd candle has high volume expansion (>2.0 RVOL) but below 3-sigma climatic limit
    # rolling MA is ~100. vol = 230 -> RVOL ~ 2.11 > 2.0. Stddev is ~50. Mean + 3*stddev is ~250.
    c22 = make_candle(21, 100.0, 105.0, 95.0, 100.0, vol=230.0)
    state = engine.analyze_candle(c22)
    assert state.volume.expansion_state == VolumeExpansionState.EXPANSION
    assert state.volume.normalized_volume > 2.0

    # 23rd candle has climatic volume anomaly (> 3-sigma)
    c23 = make_candle(22, 100.0, 105.0, 95.0, 100.0, vol=1000.0)
    state = engine.analyze_candle(c23)
    assert state.volume.expansion_state == VolumeExpansionState.CLIMATIC

    # Event count should equal number of processed candles
    assert len(events) == 23
    assert events[-1].payload["expansion_state"] == "CLIMATIC"


def test_liquidity_sweeps():
    """Verify Buy-side and Sell-side sweeps detect wicks exceeding swings with close back inside and volume filter."""
    bus = InMemoryEventBus()
    engine = CoreAnalysisEngine(event_bus=bus, k=2)

    sweep_events = []
    bus.subscribe("system.liquidity_swept", sweep_events.append)

    # 1. Establish a Swing High at index 2 (k=2)
    # Swings are checked at t-k (i.e. index 2 is checked after index 4 is processed)
    # Ensure high of index 2 is a pivot high and low is not a pivot low.
    candles = [
        make_candle(0, 10, 12, 8, 10, vol=100.0),
        make_candle(1, 10, 11, 8, 10, vol=100.0),
        make_candle(2, 10, 20, 8, 15, vol=100.0),  # Target Swing High (Price 20)
        make_candle(3, 15, 14, 8, 12, vol=100.0),
        make_candle(4, 12, 13, 8, 12, vol=100.0),  # Confirms Swing High at index 2
    ]

    for c in candles:
        engine.analyze_candle(c)

    # Verify Swing High is confirmed
    swings = engine.get_swing_engine().get_swings("BTCUSDT", "1h")
    assert len(swings) == 1
    assert swings[0].point_type == SwingType.HIGH
    assert swings[0].price == 20.0

    # 2. Sweep this Swing High with high volume (RVOL > 1.5)
    # Current SMA volume is 100. Let's make volume 300 (RVOL = 3)
    # Wick goes to 22.0, close is 18.0 (back inside 20.0)
    sweep_candle = make_candle(5, 15, 22, 14, 18, vol=300.0)
    state = engine.analyze_candle(sweep_candle)

    # Verify sweep event published
    assert len(sweep_events) == 1
    assert sweep_events[0].payload["level_swept"] == 20.0
    assert sweep_events[0].payload["pool_type"] == "BUY_SIDE"

    # Pool should be removed from active buy side pools
    assert 20.0 not in state.liquidity.buy_side_pools
    assert 20.0 in state.liquidity.swept_levels

    # 3. Establish a Swing Low at index 8 (confirmed at index 10)
    # Ensure high of index 8 is not a pivot high (less than neighbors) and low is a pivot low.
    candles_low = [
        make_candle(6, 10, 15, 9, 10, vol=100.0),
        make_candle(7, 10, 14, 9, 10, vol=100.0),
        make_candle(8, 10, 12, 5, 8, vol=100.0),   # Target Swing Low (Price 5, High=12 < 14/13)
        make_candle(9, 8, 13, 7, 9, vol=100.0),
        make_candle(10, 9, 13, 8, 10, vol=100.0),  # Confirms Swing Low at index 8
    ]
    for c in candles_low:
        engine.analyze_candle(c)

    swings = engine.get_swing_engine().get_swings("BTCUSDT", "1h")
    # Swings include: SH1 at index 2 (20.0), SL1 at index 4 (8.0), SH2 at index 5 (22.0), SL2 at index 8 (5.0)
    assert len(swings) == 4
    assert swings[3].point_type == SwingType.LOW
    assert swings[3].price == 5.0

    # 4. Sweep this Swing Low with high volume (RVOL > 1.5)
    # Low goes to 4.0, close is 6.0 (back inside 5.0)
    sweep_low_candle = make_candle(11, 10, 12, 4, 6, vol=300.0)
    state = engine.analyze_candle(sweep_low_candle)

    assert len(sweep_events) == 2
    assert sweep_events[1].payload["level_swept"] == 5.0
    assert sweep_events[1].payload["pool_type"] == "SELL_SIDE"
    assert 5.0 not in state.liquidity.sell_side_pools
    assert 5.0 in state.liquidity.swept_levels


def test_supply_demand_zones():
    """Verify creation, mitigation, and invalidation of Supply and Demand zones with ATR validation."""
    bus = InMemoryEventBus()
    engine = CoreAnalysisEngine(event_bus=bus, k=2)

    created_supply = []
    created_demand = []
    mitigated = []
    invalidated = []

    bus.subscribe("system.supply_zone_created", created_supply.append)
    bus.subscribe("system.demand_zone_created", created_demand.append)
    bus.subscribe("system.zone_mitigated", mitigated.append)
    bus.subscribe("system.zone_invalidated", invalidated.append)

    # Establish baseline ATR. We feed 14 candles to build a reasonable ATR.
    # True range of each is 10. ATR will converge to 10.
    for i in range(14):
        engine.analyze_candle(make_candle(i, 100, 105, 95, 100))

    # Current ATR should be calculated
    atr = engine.get_volume_engine().get_atr("BTCUSDT", "1h")
    assert atr > 0.0

    # 1. Bearish Displacement -> Supply Zone Creation
    # Base candle at index 14: high 100, close 90
    # Next 2 candles are bearish (displacement_bars = 2).
    # Cumulative decline = (90 - 80) + (80 - 60) = 30.
    # If ATR is ~10, cumulative decline of 30 is > 2.0 * ATR (20).
    engine.analyze_candle(make_candle(14, 90, 100, 85, 90))  # Base candle (high=100, close=90)
    engine.analyze_candle(make_candle(15, 90, 92, 78, 80))   # Bearish 1 (close=80, decline=10)
    state = engine.analyze_candle(make_candle(16, 80, 82, 58, 60))   # Bearish 2 (close=60, decline=20)

    # Verify Supply Zone created
    assert len(created_supply) == 1
    # Bounds: upper = max(base.high, next.high) = max(100, 92) = 100. Lower = base.close = 90.
    assert state.zones[0].zone_type == ZoneType.SUPPLY
    assert state.zones[0].upper_bound == 100.0
    assert state.zones[0].lower_bound == 90.0
    assert state.zones[0].mitigations_count == 0
    assert not state.zones[0].is_invalidated

    # 2. Touch/Mitigate Supply Zone
    # Wick goes to 95 (within bounds [90, 100]), close is 65 (keep it bearish to avoid creating demand zone here).
    state = engine.analyze_candle(make_candle(17, 70, 95, 60, 65))
    assert len(mitigated) == 1
    assert state.zones[0].mitigations_count == 1
    assert not state.zones[0].is_invalidated

    # 3. Invalidate Supply Zone
    # Close is 105 (> upper bound of 100)
    state = engine.analyze_candle(make_candle(18, 85, 110, 80, 105))
    assert len(invalidated) == 1
    assert state.zones[0].is_invalidated

    # 4. Bullish Displacement -> Demand Zone Creation
    # Base candle at index 19: low 100, close 110
    # Next 2 candles are bullish.
    # Cumulative rise = (120 - 110) + (145 - 120) = 35.
    # ATR is ~10-15. Cumulative rise of 35 is > 2.0 * ATR.
    engine.analyze_candle(make_candle(19, 105, 112, 100, 110))  # Base (low=100, close=110)
    engine.analyze_candle(make_candle(20, 110, 122, 108, 120))  # Bullish 1
    state = engine.analyze_candle(make_candle(21, 120, 146, 118, 145))  # Bullish 2

    # Demand Zone created
    assert len(created_demand) == 1
    # Bounds: lower = min(base.low, next.low) = min(100, 108) = 100. Upper = base.close = 110.
    demand_zone = state.zones[1]
    assert demand_zone.zone_type == ZoneType.DEMAND
    assert demand_zone.upper_bound == 110.0
    assert demand_zone.lower_bound == 100.0

    # 5. Touch/Mitigate Demand Zone
    # Wick goes to 105, close is 115
    state = engine.analyze_candle(make_candle(22, 140, 142, 105, 115))
    assert len(mitigated) == 2
    assert state.zones[1].mitigations_count == 1

    # 6. Invalidate Demand Zone
    # Close is 95 (< lower bound of 100)
    state = engine.analyze_candle(make_candle(23, 110, 112, 90, 95))
    assert len(invalidated) == 2
    assert state.zones[1].is_invalidated


def test_support_resistance_clustering():
    """Verify clustering of unbroken swings into horizontal levels with strength and type voting."""
    bus = InMemoryEventBus()
    engine = CoreAnalysisEngine(event_bus=bus, k=2)

    updated_events = []
    bus.subscribe("system.support_resistance_updated", updated_events.append)

    # Build sequence of candles confirming Swing Highs at 100 and 101, Swing Lows at 50 and 51.
    # Keep high/low coordinates clean to prevent double pivot detections.
    candles = [
        # Swing High 1 (Price 100) at index 2
        make_candle(0, 70, 90, 80, 85),
        make_candle(1, 85, 90, 80, 85),
        make_candle(2, 85, 100, 80, 90), # Target Swing High (High=100)
        make_candle(3, 90, 90, 80, 85),
        make_candle(4, 85, 90, 80, 85),

        # Swing Low 1 (Price 50) at index 7
        make_candle(5, 85, 90, 60, 70),
        make_candle(6, 70, 90, 60, 70),
        make_candle(7, 70, 90, 50, 60),  # Target Swing Low (Low=50)
        make_candle(8, 60, 90, 60, 70),
        make_candle(9, 70, 90, 60, 70),

        # Swing High 2 (Price 101) at index 12
        make_candle(10, 70, 90, 80, 85),
        make_candle(11, 85, 90, 80, 85),
        make_candle(12, 85, 101, 80, 90), # Target Swing High (High=101)
        make_candle(13, 90, 90, 80, 85),
        make_candle(14, 85, 90, 80, 85),

        # Swing Low 2 (Price 51) at index 17
        make_candle(15, 85, 90, 60, 70),
        make_candle(16, 70, 90, 60, 70),
        make_candle(17, 70, 90, 51, 60),  # Target Swing Low (Low=51)
        make_candle(18, 60, 90, 60, 70),
        make_candle(19, 70, 90, 60, 70),
    ]

    for c in candles:
        state = engine.analyze_candle(c)

    # At the end, we have 4 confirmed swings:
    # SH1: 100.0, SL1: 50.0, SH2: 101.0, SL2: 51.0
    swings = engine.get_swing_engine().get_swings("BTCUSDT", "1h")
    assert len(swings) == 4

    # ATR is calculated as ~30-40. The clustering threshold will group
    # 100.0 and 101.0 into RESISTANCE level (mean = 100.5, touch_count = 2)
    # 50.0 and 51.0 into SUPPORT level (mean = 50.5, touch_count = 2)
    assert len(state.sr_levels) == 2
    
    levels_sorted = sorted(state.sr_levels, key=lambda l: l.price)
    
    # Verify SUPPORT level
    assert levels_sorted[0].level_type == "SUPPORT"
    assert levels_sorted[0].price == 50.5
    assert levels_sorted[0].touch_count == 2
    assert levels_sorted[0].strength == 2.0

    # Verify RESISTANCE level
    assert levels_sorted[1].level_type == "RESISTANCE"
    assert levels_sorted[1].price == 100.5
    assert levels_sorted[1].touch_count == 2
    assert levels_sorted[1].strength == 2.0

    # Verify event published
    assert len(updated_events) > 0
    assert len(updated_events[-1].payload["levels"]) == 2


def test_sprint3_replay_determinism():
    """Verify replay determinism: batch replay yields identical states to stream processing."""
    # Build list of 30 candles
    candles = [make_candle(i, 100 + i, 105 + i, 95 + i, 100 + i, vol=100 + (i % 5)*50) for i in range(30)]

    # Stream processing
    engine_stream = CoreAnalysisEngine(k=2)
    for c in candles:
        state_stream = engine_stream.analyze_candle(c)

    # Batch/Replay processing
    engine_replay = CoreAnalysisEngine(k=2)
    for c in candles:
        state_replay = engine_replay.analyze_candle(c)

    # Compare results
    assert state_stream.volume == state_replay.volume
    assert state_stream.liquidity == state_replay.liquidity
    assert len(state_stream.zones) == len(state_replay.zones)
    for z1, z2 in zip(state_stream.zones, state_replay.zones):
        assert z1.upper_bound == z2.upper_bound
        assert z1.lower_bound == z2.lower_bound
        assert z1.zone_type == z2.zone_type
        assert z1.is_invalidated == z2.is_invalidated
        assert z1.mitigations_count == z2.mitigations_count

    assert len(state_stream.sr_levels) == len(state_replay.sr_levels)
    for l1, l2 in zip(state_stream.sr_levels, state_replay.sr_levels):
        assert l1.price == l2.price
        assert l1.level_type == l2.level_type
        assert l1.touch_count == l2.touch_count


def test_sprint3_performance_latency():
    """Verify mean processing latency remains below 5 milliseconds per candle."""
    candles = [make_candle(i, 100.0, 105.0, 95.0, 100.0, vol=100.0) for i in range(1000)]
    engine = CoreAnalysisEngine(k=2)

    # Warmup
    for i in range(50):
        engine.analyze_candle(candles[i])

    # Benchmark
    start_time = time.perf_counter()
    for i in range(50, 1000):
        engine.analyze_candle(candles[i])
    end_time = time.perf_counter()

    elapsed_ms = (end_time - start_time) * 1000.0
    mean_latency = elapsed_ms / 950.0

    print(f"Mean processing latency: {mean_latency:.4f} ms per candle.")
    assert mean_latency < 5.0, f"Latency of {mean_latency:.4f} ms exceeded the 5 ms budget!"
