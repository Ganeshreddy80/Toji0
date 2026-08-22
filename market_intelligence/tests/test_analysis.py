"""Comprehensive unit and integration tests for the Core Analysis Engine."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
import pytest

from data.schemas.market_data import OHLCV
from market_gateway.core.events import MarketCandleEvent
from market_intelligence.core.analysis.engine import CoreAnalysisEngine
from market_intelligence.core.enums import SwingType, TrendDirection
from market_intelligence.core.models import MarketSnapshot, MarketState
from market_intelligence.core.plugin import MarketIntelligencePlugin
from toji_platform.core.configuration import ConfigurationManager
from toji_platform.core.dependency_injection import Container
from toji_platform.core.event_bus import InMemoryEventBus
from toji_platform.core.event_bus.interfaces import IEventBus


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
        timestamp=datetime(2026, 6, 26, 10, 0, tzinfo=timezone.utc)
        + timedelta(hours=idx),
        open=open_p,
        high=high_p,
        low=low_p,
        close=close_p,
        volume=vol,
        interval=interval,
    )


@pytest.fixture
def base_candles() -> list[OHLCV]:
    """Return a sequence of 31 candles that simulates a full cycle of trend transitions.

    Includes: Swings, HH/HL/LH/LL, BULLISH/BEARISH/RANGING trends, BOS, CHoCH, and pullbacks.
    """
    return [
        make_candle(0, 15, 16, 14, 15),
        make_candle(1, 15, 16, 14, 15),
        make_candle(2, 15, 15.5, 10, 11),  # Swing Low 1 target
        make_candle(3, 11, 13, 12, 12.5),
        make_candle(4, 12.5, 14, 13, 13.5),  # Confirm Swing Low 1 (idx 2, price 10)
        make_candle(5, 13.5, 20, 14, 19),
        make_candle(6, 19, 25, 18, 22),  # Swing High 1 target
        make_candle(7, 22, 21, 16, 17),
        make_candle(8, 17, 18, 15, 16),  # Confirm Swing High 1 (idx 6, price 25)
        make_candle(9, 16, 17.5, 13, 14),
        make_candle(10, 14, 15, 12, 13),  # Swing Low 2 target
        make_candle(11, 13, 16, 14, 15),
        make_candle(12, 15, 17, 16, 16.5),  # Confirm Swing Low 2 (idx 10, price 12 - HL)
        make_candle(13, 16.5, 22, 16, 21),
        make_candle(14, 21, 28, 20, 26),  # Swing High 2 target
        make_candle(15, 26, 24, 21, 22),
        make_candle(16, 22, 23, 19, 20),  # Confirm Swing High 2 (idx 14, price 28 - HH)
        # Trend changes to BULLISH at index 16. State machine transitions to Bull Pullback immediately
        make_candle(17, 20, 22, 18, 19.5),  # Pullback: close < 20, close < 28, close > 12. State -> Bull Pullback
        make_candle(18, 19.5, 30, 19, 29.5),  # BOS: close 29.5 > 28. BOS detected, State -> Bull Continuation
        make_candle(19, 29.5, 12, 9.5, 9.5),  # CHoCH: close 9.5 < 12. CHoCH detected, State -> Distribution
        make_candle(20, 9.5, 18, 9.5, 17),
        make_candle(21, 17, 22, 15, 19),  # Swing High 3 target
        make_candle(22, 19, 17, 13, 14),
        make_candle(23, 14, 15, 12, 13),  # Confirm Swing High 3 (idx 21, price 22 - LH)
        make_candle(24, 13, 14, 9, 10),
        make_candle(25, 10, 11, 7, 8),  # Swing Low 3 target
        make_candle(26, 8, 12, 9, 10),
        make_candle(27, 10, 13, 11, 12),  # Confirm Swing Low 3 (idx 25, price 7 - LL)
        # Trend is BEARISH from index 23 onwards.
        make_candle(28, 12, 16, 13, 14.5),  # Pullback: close > 12, close > 7, close < 22. State -> Bear Pullback
        make_candle(29, 14.5, 15, 5, 5.5),  # BOS: close 5.5 < 7. BOS detected, State -> Bear Continuation
        make_candle(30, 5.5, 24, 5.5, 23.5),  # CHoCH: close 23.5 > 22. CHoCH detected, State -> Accumulation
    ]


def test_swing_engine_detection(base_candles):
    """Verify Swing Engine detects swing high/low correctly with confirmation delay."""
    bus = InMemoryEventBus()
    engine = CoreAnalysisEngine(event_bus=bus, k=2)

    events = []
    bus.subscribe("system.swing_high_confirmed", events.append)
    bus.subscribe("system.swing_low_confirmed", events.append)

    states = []
    for candle in base_candles:
        states.append(engine.analyze_candle(candle))

    # At the end, we should have 8 confirmed swings
    swings = engine.get_swing_engine().get_swings("BTCUSDT", "1h")
    assert len(swings) == 8

    # Verify order of swings: Low, High, Low, High, High, Low, High, Low
    assert swings[0].point_type == SwingType.LOW
    assert swings[0].price == 10.0
    assert swings[0].index == 2

    assert swings[1].point_type == SwingType.HIGH
    assert swings[1].price == 25.0
    assert swings[1].index == 6

    assert swings[2].point_type == SwingType.LOW
    assert swings[2].price == 12.0
    assert swings[2].index == 10

    assert swings[3].point_type == SwingType.HIGH
    assert swings[3].price == 28.0
    assert swings[3].index == 14

    assert swings[4].point_type == SwingType.HIGH
    assert swings[4].price == 30.0
    assert swings[4].index == 18

    assert swings[5].point_type == SwingType.LOW
    assert swings[5].price == 9.5
    assert swings[5].index == 20

    assert swings[6].point_type == SwingType.HIGH
    assert swings[6].price == 22.0
    assert swings[6].index == 21

    assert swings[7].point_type == SwingType.LOW
    assert swings[7].price == 7.0
    assert swings[7].index == 25

    # Verify event publications
    assert len(events) == 8


def test_market_structure_classification(base_candles):
    """Verify structure classifications (HH, HL, LH, LL)."""
    engine = CoreAnalysisEngine(k=2)

    for candle in base_candles:
        engine.analyze_candle(candle)

    struct_history = engine.get_structure_engine().get_structure_history("BTCUSDT", "1h")
    assert len(struct_history) == 8

    # SL1: first low is LL
    assert struct_history[0].classification == "LL"
    # SH1: first high is HH
    assert struct_history[1].classification == "HH"
    # SL2: 12.0 > 10.0 -> HL
    assert struct_history[2].classification == "HL"
    # SH2: 28.0 > 25.0 -> HH
    assert struct_history[3].classification == "HH"
    # SH3: 30.0 > 28.0 -> HH
    assert struct_history[4].classification == "HH"
    # SL3: 9.5 < 12.0 -> LL
    assert struct_history[5].classification == "LL"
    # SH4: 22.0 < 30.0 -> LH
    assert struct_history[6].classification == "LH"
    # SL4: 7.0 < 9.5 -> LL
    assert struct_history[7].classification == "LL"


def test_trend_transitions(base_candles):
    """Verify Trend transitions from UNKNOWN -> BULLISH -> RANGING -> BEARISH."""
    engine = CoreAnalysisEngine(k=2)

    # Initial state
    assert engine.get_trend_engine().get_trend_direction("BTCUSDT", "1h") == "UNKNOWN"

    for i in range(16):
        engine.analyze_candle(base_candles[i])
    # Before the 2nd HH is confirmed at index 16
    assert engine.get_trend_engine().get_trend_direction("BTCUSDT", "1h") == "UNKNOWN"

    # Candle 16 confirms SH2 (HH) -> trend becomes BULLISH
    engine.analyze_candle(base_candles[16])
    assert engine.get_trend_engine().get_trend_direction("BTCUSDT", "1h") == "BULLISH"

    # Candle 17-22: SL3 (LL) is confirmed at index 22 -> trend becomes RANGING
    for i in range(17, 23):
        engine.analyze_candle(base_candles[i])
    assert engine.get_trend_engine().get_trend_direction("BTCUSDT", "1h") == "RANGING"

    # Candle 23 confirms SH4 (LH) -> trend becomes BEARISH (LH & LL active)
    engine.analyze_candle(base_candles[23])
    assert engine.get_trend_engine().get_trend_direction("BTCUSDT", "1h") == "BEARISH"

    # Remaining candles keep trend BEARISH
    for i in range(24, 31):
        engine.analyze_candle(base_candles[i])
    assert engine.get_trend_engine().get_trend_direction("BTCUSDT", "1h") == "BEARISH"


def test_breakout_detection(base_candles):
    """Verify BOS and CHoCH breakouts trigger on body close only."""
    bus = InMemoryEventBus()
    engine = CoreAnalysisEngine(event_bus=bus, k=2)

    bos_events = []
    choch_events = []
    bus.subscribe("system.break_of_structure_detected", bos_events.append)
    bus.subscribe("system.change_of_character_detected", choch_events.append)

    for candle in base_candles:
        engine.analyze_candle(candle)

    bos_hist = engine.get_break_engine().get_bos_history("BTCUSDT", "1h")
    choch_hist = engine.get_break_engine().get_choch_history("BTCUSDT", "1h")

    # Verify BOS
    assert len(bos_hist) == 3
    # Bullish BOS at index 18 (level breached = 28.0)
    assert bos_hist[0].direction == "UP"
    assert bos_hist[0].level_breached == 28.0
    # Bearish BOS at index 25 (level breached = 9.5)
    assert bos_hist[1].direction == "DOWN"
    assert bos_hist[1].level_breached == 9.5
    # Bearish BOS at index 29 (level breached = 7.0)
    assert bos_hist[2].direction == "DOWN"
    assert bos_hist[2].level_breached == 7.0

    # Verify CHoCH
    assert len(choch_hist) == 2
    # Bearish CHoCH at index 19 (level breached = 12.0)
    assert choch_hist[0].direction == "BULLISH_TO_BEARISH"
    assert choch_hist[0].level_breached == 12.0
    # Bullish CHoCH at index 30 (level breached = 22.0)
    assert choch_hist[1].direction == "BEARISH_TO_BULLISH"
    assert choch_hist[1].level_breached == 22.0

    assert len(bos_events) == 3
    assert len(choch_events) == 2


def test_state_machine_transitions(base_candles):
    """Verify market state machine transitions."""
    engine = CoreAnalysisEngine(k=2)

    states = []
    for candle in base_candles:
        states.append(engine.analyze_candle(candle).market_phase_state)

    # Initial states
    assert states[0] == "Unknown"
    # Bull pullback (immediate on trend confirmation because close < prev_close)
    assert states[16] == "Bull Pullback"
    # Pullback continues
    assert states[17] == "Bull Pullback"
    # BOS (continuation)
    assert states[18] == "Bull Continuation"
    # CHoCH (trend shift)
    assert states[19] == "Distribution"
    # Bear trend confirmed at index 23
    assert states[23] == "Bear Trend"
    # Pullback
    assert states[26] == "Bear Pullback"
    # BOS (continuation)
    assert states[29] == "Bear Continuation"
    # CHoCH (trend shift)
    assert states[30] == "Accumulation"


def test_replay_determinism(base_candles):
    """Verify streaming processing matches historical replay exactly."""
    engine_stream = CoreAnalysisEngine(k=2)
    for candle in base_candles:
        engine_stream.analyze_candle(candle)

    # Historical Replay
    engine_replay = CoreAnalysisEngine(k=2)
    # Feed the candles in a single batch loop
    for candle in base_candles:
        engine_replay.analyze_candle(candle)

    state_stream = MarketState(
        symbol="BTCUSDT",
        timeframe="1h",
        swings=engine_stream.get_swing_engine().get_swings("BTCUSDT", "1h"),
        trend=engine_stream.get_trend_engine().get_trend_state("BTCUSDT", "1h"),
        structure_history=engine_stream.get_structure_engine().get_structure_history(
            "BTCUSDT", "1h"
        ),
        bos_history=engine_stream.get_break_engine().get_bos_history("BTCUSDT", "1h"),
        choch_history=engine_stream.get_break_engine().get_choch_history(
            "BTCUSDT", "1h"
        ),
        market_phase_state=engine_stream.get_state_machine().get_state(
            "BTCUSDT", "1h"
        ),
        updated_at=base_candles[-1].timestamp,
    )

    state_replay = MarketState(
        symbol="BTCUSDT",
        timeframe="1h",
        swings=engine_replay.get_swing_engine().get_swings("BTCUSDT", "1h"),
        trend=engine_replay.get_trend_engine().get_trend_state("BTCUSDT", "1h"),
        structure_history=engine_replay.get_structure_engine().get_structure_history(
            "BTCUSDT", "1h"
        ),
        bos_history=engine_replay.get_break_engine().get_bos_history("BTCUSDT", "1h"),
        choch_history=engine_replay.get_break_engine().get_choch_history(
            "BTCUSDT", "1h"
        ),
        market_phase_state=engine_replay.get_state_machine().get_state(
            "BTCUSDT", "1h"
        ),
        updated_at=base_candles[-1].timestamp,
    )

    assert state_stream == state_replay


def test_multi_timeframe_correctness():
    """Verify that multiple timeframes are tracked independently."""
    engine = CoreAnalysisEngine(k=2)

    # Stream 1h candles
    c_1h_1 = make_candle(0, 10, 15, 9, 14, interval="1h")
    c_1h_2 = make_candle(1, 14, 16, 13, 15, interval="1h")
    engine.analyze_candle(c_1h_1)
    engine.analyze_candle(c_1h_2)

    # Stream 1d candles with different values
    c_1d_1 = make_candle(0, 100, 150, 90, 140, interval="1d")
    engine.analyze_candle(c_1d_1)

    # Swings history should be separate
    assert len(engine.get_swing_engine().get_swings("BTCUSDT", "1h")) == 0
    assert len(engine.get_swing_engine().get_swings("BTCUSDT", "1d")) == 0

    # Ensure histories contain correct candles
    # CoreAnalysisEngine stores candle history per (symbol, timeframe)
    assert len(engine._candle_history[("BTCUSDT", "1h")]) == 2
    assert len(engine._candle_history[("BTCUSDT", "1d")]) == 1


def test_edge_case_tie_breaking():
    """Verify tie-breaking logic resolves adjacent duplicate pivots using latest occurrence."""
    # k = 1: symmetric window of 2k+1 = 3 candles
    engine = CoreAnalysisEngine(k=1)

    # Highs: [10, 15, 15, 10]
    # For target t = 1 (high = 15): left = 10, right = 15. Right strict check target <= right is True, so not a high.
    # For target t = 2 (high = 15): left = 15, right = 10. Left check target < left is False. Right check target <= right is False. So target IS a swing high!
    candles = [
        make_candle(0, 10, 10, 5, 8),
        make_candle(1, 8, 15, 7, 14),
        make_candle(2, 14, 15, 13, 14.5),
        make_candle(3, 14.5, 10, 8, 9),
    ]

    for c in candles:
        engine.analyze_candle(c)

    swings = engine.get_swing_engine().get_swings("BTCUSDT", "1h")
    assert len(swings) == 1
    assert swings[0].point_type == SwingType.HIGH
    assert swings[0].index == 2  # The second '15' is chosen
    assert swings[0].price == 15.0


def test_edge_case_double_breakout_prevention(base_candles):
    """Verify that a single swing high/low level cannot trigger duplicate breakout events."""
    engine = CoreAnalysisEngine(k=2)

    # Feed until index 18 (which triggers a Bullish BOS on level 28.0)
    for i in range(19):
        engine.analyze_candle(base_candles[i])

    # Ensure BOS was triggered
    bos_history = engine.get_break_engine().get_bos_history("BTCUSDT", "1h")
    assert len(bos_history) == 1
    assert bos_history[0].level_breached == 28.0

    # Feed another candle that closes above 28.0.
    # It should NOT trigger another BOS since the last broken high index is still index 14 (price 28.0).
    extra_candle = make_candle(31, 29, 31, 28.5, 30.0)
    engine.analyze_candle(extra_candle)

    bos_history_after = engine.get_break_engine().get_bos_history("BTCUSDT", "1h")
    assert len(bos_history_after) == 1  # Still 1


def test_plugin_integration(base_candles):
    """Verify plugin coordinates engine updates, publishes events, and updates state/repository."""
    container = Container()
    bus = InMemoryEventBus()
    config = ConfigurationManager()

    container.register(IEventBus, instance=bus)
    container.register(ConfigurationManager, instance=config)

    plugin = MarketIntelligencePlugin(container=container)
    plugin.initialize()

    # Capture published events
    events = []
    bus.subscribe("system.swing_low_confirmed", events.append)
    bus.subscribe("system.trend_changed", events.append)

    # Publish candle events on event bus
    for c in base_candles[:17]:  # Feed up to trend confirmation
        event = MarketCandleEvent(
            source="test_gateway",
            payload={
                "symbol": c.symbol,
                "data_type": "candle",
                "data": c.model_dump(),
            },
        )
        bus.publish(event)

    # State store should have the latest snapshot
    snap = plugin.state_store.get_snapshot("BTCUSDT")
    assert snap is not None
    assert "1h" in snap.states
    state_1h = snap.states["1h"]
    assert state_1h.trend is not None
    assert state_1h.trend.direction == TrendDirection.UP
    assert state_1h.market_phase_state == "Bull Pullback"

    # Repository should have stored the snapshots
    latest_repo_snap = plugin.repository.load_latest_snapshot("BTCUSDT")
    assert latest_repo_snap is not None
    assert latest_repo_snap.snapshot_id == snap.snapshot_id

    # Verify event subscriber worked
    assert len(events) > 0

    plugin.shutdown()
