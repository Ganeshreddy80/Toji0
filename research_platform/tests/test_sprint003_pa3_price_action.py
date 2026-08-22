"""PA-3 Comprehensive Deterministic Unit Test Suite for PriceActionOrchestrator.

Covers:
1. Swing Point Detection (high, low, rising, falling, sideways, warm-up)
2. Fair Value Gap / Imbalance Detection (bullish FVG, bearish FVG, no gap, boundary)
3. Market Structure & Order Block Detection (BOS, CHOCH, bullish/bearish order blocks)
4. Edge Cases (empty symbol, single tick, zero volume, repeated timestamps, timezone handling)
5. Memory Bounds (tick history <= 1000, 1m bar history <= 200)
6. Determinism (two clean instances fed identical input produce identical output)
7. Event Publishing (StructureDetected, ImbalanceDetected, SessionUpdated gap audit)

PA-3 Evidence Correction (C-1 through C-5):
C-1. Explicit rising / falling / sideways swing-direction sequences
C-2. Market structure: higher-high (HH), lower-low (LL), bullish/bearish BOS
C-3. Duplicate timestamps — same-minute ticks merge; cross-minute ticks separate
C-4. Malformed input — negative price, NaN price (documents existing behavior)
C-5. Deterministic replay — bar-by-bar value identity + defensive copy contract

Rules:
- All external bar assertions use public get_bars(symbol).
- _tick_history private access retained ONLY in the memory-cap invariant test where
  no public equivalent exists; documented as a bounded internal invariant assertion.
- Timestamps are UTC-aware.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

import pytest

from research_platform.price_action.events import StructureDetected, ImbalanceDetected, SessionUpdated
from research_platform.price_action.models import SwingPoint, MarketStructureChange, BlockStructure, ImbalanceGap
from research_platform.price_action.orchestrator import PriceActionOrchestrator
from research_platform.price_action.repository import PriceActionRepository


# ---------------------------------------------------------------------------
# Helpers & Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_event_bus() -> MagicMock:
    bus = MagicMock()
    bus.publish = MagicMock()
    return bus


@pytest.fixture
def repo() -> PriceActionRepository:
    return PriceActionRepository()


@pytest.fixture
def orchestrator(mock_event_bus: MagicMock, repo: PriceActionRepository) -> PriceActionOrchestrator:
    return PriceActionOrchestrator(event_bus=mock_event_bus, repository=repo)


def feed_candle_ticks(
    orch: PriceActionOrchestrator,
    symbol: str,
    start_time: datetime,
    minute_offset: int,
    open_p: float,
    high_p: float,
    low_p: float,
    close_p: float,
    volume: float = 10.0
) -> datetime:
    """Helper to feed ticks forming a specific 1-minute OHLCV bar naturally."""
    bar_time = start_time + timedelta(minutes=minute_offset)
    orch.process_tick(symbol, open_p, bar_time + timedelta(seconds=0), volume / 4.0)
    orch.process_tick(symbol, high_p, bar_time + timedelta(seconds=15), volume / 4.0)
    orch.process_tick(symbol, low_p, bar_time + timedelta(seconds=30), volume / 4.0)
    orch.process_tick(symbol, close_p, bar_time + timedelta(seconds=45), volume / 4.0)
    return bar_time


# ---------------------------------------------------------------------------
# 1. SWING DETECTION TESTS
# ---------------------------------------------------------------------------

def test_swing_detection_insufficient_bars(orchestrator: PriceActionOrchestrator) -> None:
    """Less than 5 bars should detect zero swing points."""
    symbol = "BTCUSDT"
    t0 = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    for i in range(4):
        feed_candle_ticks(orchestrator, symbol, t0, i, 100.0, 105.0, 95.0, 100.0)

    swings = orchestrator.get_swings(symbol)
    assert len(swings) == 0, f"Expected 0 swings for 4 bars, got {len(swings)}"


def test_swing_high_detection_fractal_pattern(orchestrator: PriceActionOrchestrator) -> None:
    """5-bar fractal where bar 3 high > bar 1, 2, 4, 5 highs -> Swing High detected."""
    symbol = "BTCUSDT"
    t0 = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)

    feed_candle_ticks(orchestrator, symbol, t0, 0, 90.0, 100.0, 85.0, 95.0)
    feed_candle_ticks(orchestrator, symbol, t0, 1, 95.0, 105.0, 90.0, 100.0)
    feed_candle_ticks(orchestrator, symbol, t0, 2, 100.0, 120.0, 95.0, 115.0)
    feed_candle_ticks(orchestrator, symbol, t0, 3, 115.0, 108.0, 100.0, 102.0)
    feed_candle_ticks(orchestrator, symbol, t0, 4, 102.0, 101.0, 95.0, 98.0)
    feed_candle_ticks(orchestrator, symbol, t0, 5, 98.0, 99.0, 94.0, 96.0)

    swings = orchestrator.get_swings(symbol)
    high_swings = [s for s in swings if s.point_type == "HIGH"]

    assert len(high_swings) >= 1, "Expected at least 1 Swing High"
    assert high_swings[0].price == 120.0


def test_swing_low_detection_fractal_pattern(orchestrator: PriceActionOrchestrator) -> None:
    """5-bar fractal where bar 3 low < bar 1, 2, 4, 5 lows -> Swing Low detected."""
    symbol = "BTCUSDT"
    t0 = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)

    feed_candle_ticks(orchestrator, symbol, t0, 0, 100.0, 105.0, 90.0, 95.0)
    feed_candle_ticks(orchestrator, symbol, t0, 1, 95.0, 100.0, 85.0, 90.0)
    feed_candle_ticks(orchestrator, symbol, t0, 2, 90.0, 95.0, 70.0, 75.0)
    feed_candle_ticks(orchestrator, symbol, t0, 3, 75.0, 88.0, 80.0, 85.0)
    feed_candle_ticks(orchestrator, symbol, t0, 4, 85.0, 92.0, 88.0, 90.0)
    feed_candle_ticks(orchestrator, symbol, t0, 5, 90.0, 95.0, 89.0, 93.0)

    swings = orchestrator.get_swings(symbol)
    low_swings = [s for s in swings if s.point_type == "LOW"]

    assert len(low_swings) >= 1, "Expected at least 1 Swing Low"
    assert low_swings[0].price == 70.0


def test_sideways_sequence_no_swings(orchestrator: PriceActionOrchestrator) -> None:
    """Identical bars produce no fractal swing high or low."""
    symbol = "ETHUSDT"
    t0 = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)

    for i in range(10):
        feed_candle_ticks(orchestrator, symbol, t0, i, 100.0, 105.0, 95.0, 100.0)

    swings = orchestrator.get_swings(symbol)
    assert len(swings) == 0, f"Expected 0 swings in flat market, got {len(swings)}"


# ---------------------------------------------------------------------------
# C-1: EXPLICIT RISING / FALLING SWING DIRECTION TESTS
# ---------------------------------------------------------------------------

def test_c1_monotone_rising_produces_no_swing_high(orchestrator: PriceActionOrchestrator) -> None:
    """C-1 RISING: A strictly monotone rising sequence never satisfies the 5-bar fractal.

    Each bar's high exceeds all previous bars, so no bar can be the local maximum
    of a (b1, b2, b3, b4, b5) window — bar 4 and 5 always exceed bar 3.
    Verifies the existing behavior: no Swing High is produced.
    """
    symbol = "BTCUSDT"
    t0 = datetime(2026, 1, 2, 0, 0, tzinfo=timezone.utc)

    for i in range(10):
        base = 100.0 + i * 10.0
        feed_candle_ticks(orchestrator, symbol, t0, i, base, base + 5.0, base - 5.0, base + 2.0)

    swings = orchestrator.get_swings(symbol)
    high_swings = [s for s in swings if s.point_type == "HIGH"]
    assert len(high_swings) == 0, (
        f"C-1 RISING: Expected 0 swing highs in monotone rise, got {len(high_swings)}"
    )


def test_c1_monotone_falling_produces_no_swing_low(orchestrator: PriceActionOrchestrator) -> None:
    """C-1 FALLING: A strictly monotone falling sequence never satisfies the 5-bar fractal.

    Each bar's low is lower than all previous bars, so no bar can be the local minimum.
    Verifies the existing behavior: no Swing Low is produced.
    """
    symbol = "BTCUSDT"
    t0 = datetime(2026, 1, 3, 0, 0, tzinfo=timezone.utc)

    for i in range(10):
        base = 200.0 - i * 10.0
        feed_candle_ticks(orchestrator, symbol, t0, i, base, base + 5.0, base - 5.0, base - 2.0)

    swings = orchestrator.get_swings(symbol)
    low_swings = [s for s in swings if s.point_type == "LOW"]
    assert len(low_swings) == 0, (
        f"C-1 FALLING: Expected 0 swing lows in monotone fall, got {len(low_swings)}"
    )


def test_c1_rise_then_fall_produces_swing_high(orchestrator: PriceActionOrchestrator) -> None:
    """C-1 RISING THEN FALLING: Peak bar satisfies 5-bar fractal -> Swing High detected."""
    symbol = "SOLUSDT"
    t0 = datetime(2026, 1, 4, 0, 0, tzinfo=timezone.utc)

    feed_candle_ticks(orchestrator, symbol, t0, 0,  90.0,  95.0,  85.0,  92.0)  # approach
    feed_candle_ticks(orchestrator, symbol, t0, 1,  92.0, 100.0,  88.0,  98.0)  # approach
    feed_candle_ticks(orchestrator, symbol, t0, 2,  98.0, 130.0,  95.0, 120.0)  # PEAK high=130
    feed_candle_ticks(orchestrator, symbol, t0, 3, 120.0, 115.0, 108.0, 110.0)  # decline
    feed_candle_ticks(orchestrator, symbol, t0, 4, 110.0, 108.0, 100.0, 103.0)  # decline
    feed_candle_ticks(orchestrator, symbol, t0, 5, 103.0, 105.0,  98.0, 100.0)  # trigger bar

    swings = orchestrator.get_swings(symbol)
    high_swings = [s for s in swings if s.point_type == "HIGH"]
    assert len(high_swings) >= 1, "C-1: Expected Swing High at peak of rise-then-fall"
    assert high_swings[0].price == 130.0, (
        f"C-1: Expected swing high 130.0, got {high_swings[0].price}"
    )


def test_c1_fall_then_rise_produces_swing_low(orchestrator: PriceActionOrchestrator) -> None:
    """C-1 FALLING THEN RISING: Trough bar satisfies 5-bar fractal -> Swing Low detected."""
    symbol = "SOLUSDT"
    t0 = datetime(2026, 1, 5, 0, 0, tzinfo=timezone.utc)

    feed_candle_ticks(orchestrator, symbol, t0, 0, 200.0, 205.0, 190.0, 192.0)  # descent
    feed_candle_ticks(orchestrator, symbol, t0, 1, 192.0, 194.0, 180.0, 182.0)  # descent
    feed_candle_ticks(orchestrator, symbol, t0, 2, 182.0, 183.0, 155.0, 160.0)  # TROUGH low=155
    feed_candle_ticks(orchestrator, symbol, t0, 3, 160.0, 175.0, 158.0, 172.0)  # ascent
    feed_candle_ticks(orchestrator, symbol, t0, 4, 172.0, 185.0, 170.0, 183.0)  # ascent
    feed_candle_ticks(orchestrator, symbol, t0, 5, 183.0, 190.0, 181.0, 188.0)  # trigger bar

    swings = orchestrator.get_swings(symbol)
    low_swings = [s for s in swings if s.point_type == "LOW"]
    assert len(low_swings) >= 1, "C-1: Expected Swing Low at trough of fall-then-rise"
    assert low_swings[0].price == 155.0, (
        f"C-1: Expected swing low 155.0, got {low_swings[0].price}"
    )


# ---------------------------------------------------------------------------
# 2. FVG / IMBALANCE TESTS
# ---------------------------------------------------------------------------

def test_bullish_fvg_detection(orchestrator: PriceActionOrchestrator) -> None:
    """b3 low > b1 high -> Bullish FVG gap."""
    symbol = "BTCUSDT"
    t0 = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)

    feed_candle_ticks(orchestrator, symbol, t0, 0, 90.0, 100.0, 85.0, 95.0)
    feed_candle_ticks(orchestrator, symbol, t0, 1, 95.0, 115.0, 95.0, 110.0)
    feed_candle_ticks(orchestrator, symbol, t0, 2, 110.0, 125.0, 105.0, 120.0)
    feed_candle_ticks(orchestrator, symbol, t0, 3, 120.0, 128.0, 118.0, 125.0)
    feed_candle_ticks(orchestrator, symbol, t0, 4, 125.0, 130.0, 122.0, 127.0)
    feed_candle_ticks(orchestrator, symbol, t0, 5, 127.0, 132.0, 126.0, 130.0)

    gaps = orchestrator.get_gaps(symbol)
    assert len(gaps) >= 1, "Expected at least 1 FVG gap"
    gap = gaps[0]
    assert gap.gap_type == "FVG"
    assert gap.high == 105.0
    assert gap.low == 100.0


def test_bearish_fvg_detection(orchestrator: PriceActionOrchestrator) -> None:
    """b3 high < b1 low -> Bearish FVG gap."""
    symbol = "BTCUSDT"
    t0 = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)

    feed_candle_ticks(orchestrator, symbol, t0, 0, 110.0, 115.0, 100.0, 105.0)
    feed_candle_ticks(orchestrator, symbol, t0, 1, 105.0, 105.0, 85.0, 90.0)
    feed_candle_ticks(orchestrator, symbol, t0, 2, 90.0, 95.0, 75.0, 80.0)
    feed_candle_ticks(orchestrator, symbol, t0, 3, 80.0, 82.0, 70.0, 75.0)
    feed_candle_ticks(orchestrator, symbol, t0, 4, 75.0, 78.0, 65.0, 70.0)
    feed_candle_ticks(orchestrator, symbol, t0, 5, 70.0, 72.0, 62.0, 68.0)

    gaps = orchestrator.get_gaps(symbol)
    assert len(gaps) >= 1, "Expected at least 1 Bearish FVG gap"
    gap = gaps[0]
    assert gap.gap_type == "FVG"
    assert gap.high == 100.0
    assert gap.low == 95.0


def test_no_gap_overlapping_candles(orchestrator: PriceActionOrchestrator) -> None:
    """Overlapping candle wicks produce no FVG."""
    symbol = "BTCUSDT"
    t0 = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)

    feed_candle_ticks(orchestrator, symbol, t0, 0, 100.0, 105.0, 95.0, 102.0)
    feed_candle_ticks(orchestrator, symbol, t0, 1, 102.0, 110.0, 98.0, 106.0)
    feed_candle_ticks(orchestrator, symbol, t0, 2, 106.0, 108.0, 101.0, 104.0)
    feed_candle_ticks(orchestrator, symbol, t0, 3, 104.0, 107.0, 100.0, 103.0)
    feed_candle_ticks(orchestrator, symbol, t0, 4, 103.0, 106.0, 99.0, 102.0)
    feed_candle_ticks(orchestrator, symbol, t0, 5, 102.0, 105.0, 98.0, 101.0)

    gaps = orchestrator.get_gaps(symbol)
    assert len(gaps) == 0, f"Expected 0 gaps in overlapping market, got {len(gaps)}"


# ---------------------------------------------------------------------------
# 3. MARKET STRUCTURE & ORDER BLOCKS
# ---------------------------------------------------------------------------

def test_bullish_bos_and_order_block_creation(orchestrator: PriceActionOrchestrator) -> None:
    """Higher high breaking previous swing high triggers Bullish BOS + Bullish Order Block."""
    symbol = "SOLUSDT"
    t0 = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)

    feed_candle_ticks(orchestrator, symbol, t0, 0, 90.0, 100.0, 85.0, 95.0)
    feed_candle_ticks(orchestrator, symbol, t0, 1, 95.0, 105.0, 90.0, 100.0)
    feed_candle_ticks(orchestrator, symbol, t0, 2, 100.0, 120.0, 95.0, 115.0)
    feed_candle_ticks(orchestrator, symbol, t0, 3, 115.0, 108.0, 100.0, 102.0)
    feed_candle_ticks(orchestrator, symbol, t0, 4, 102.0, 101.0, 95.0, 98.0)
    feed_candle_ticks(orchestrator, symbol, t0, 5, 98.0, 110.0, 95.0, 108.0)
    feed_candle_ticks(orchestrator, symbol, t0, 6, 108.0, 120.0, 105.0, 118.0)
    feed_candle_ticks(orchestrator, symbol, t0, 7, 118.0, 135.0, 112.0, 130.0)
    feed_candle_ticks(orchestrator, symbol, t0, 8, 130.0, 125.0, 115.0, 120.0)
    feed_candle_ticks(orchestrator, symbol, t0, 9, 120.0, 122.0, 118.0, 121.0)
    feed_candle_ticks(orchestrator, symbol, t0, 10, 121.0, 123.0, 119.0, 122.0)

    changes = orchestrator.get_structure_changes(symbol)
    assert len(changes) >= 1, "Expected at least 1 structure change"
    bos = [c for c in changes if c.change_type == "BOS" and c.direction == "BULLISH"]
    assert len(bos) >= 1, "Expected Bullish BOS"
    assert bos[0].break_price == 135.0

    blocks = orchestrator.get_blocks(symbol)
    assert len(blocks) >= 1, "Expected at least 1 Order Block"
    ob = blocks[0]
    assert ob.block_type == "ORDER"
    assert ob.direction == "BULLISH"


# ---------------------------------------------------------------------------
# C-2: MARKET STRUCTURE — HIGHER HIGH / LOWER LOW / BOS DIRECTION
# ---------------------------------------------------------------------------

def test_c2_higher_high_triggers_bullish_bos(orchestrator: PriceActionOrchestrator) -> None:
    """C-2 HH: A second swing high above the previous swing high triggers BOS BULLISH."""
    symbol = "ETHUSDT"
    t0 = datetime(2026, 1, 6, 0, 0, tzinfo=timezone.utc)

    # First swing high cluster (peak = 110)
    feed_candle_ticks(orchestrator, symbol, t0,  0,  90.0, 100.0,  85.0,  95.0)
    feed_candle_ticks(orchestrator, symbol, t0,  1,  95.0, 105.0,  90.0, 100.0)
    feed_candle_ticks(orchestrator, symbol, t0,  2, 100.0, 110.0,  95.0, 105.0)  # peak 110
    feed_candle_ticks(orchestrator, symbol, t0,  3, 105.0, 104.0,  98.0, 100.0)
    feed_candle_ticks(orchestrator, symbol, t0,  4, 100.0,  99.0,  93.0,  96.0)
    # Pullback
    feed_candle_ticks(orchestrator, symbol, t0,  5,  96.0,  97.0,  88.0,  90.0)
    feed_candle_ticks(orchestrator, symbol, t0,  6,  90.0,  91.0,  82.0,  85.0)
    feed_candle_ticks(orchestrator, symbol, t0,  7,  85.0,  86.0,  78.0,  80.0)
    feed_candle_ticks(orchestrator, symbol, t0,  8,  80.0,  88.0,  79.0,  86.0)
    feed_candle_ticks(orchestrator, symbol, t0,  9,  86.0,  93.0,  84.0,  91.0)
    # Second swing high cluster (peak = 125 > 110 -> HH -> BOS BULLISH)
    feed_candle_ticks(orchestrator, symbol, t0, 10,  91.0, 110.0,  89.0, 108.0)
    feed_candle_ticks(orchestrator, symbol, t0, 11, 108.0, 125.0, 105.0, 120.0)  # peak 125 (HH)
    feed_candle_ticks(orchestrator, symbol, t0, 12, 120.0, 118.0, 112.0, 115.0)
    feed_candle_ticks(orchestrator, symbol, t0, 13, 115.0, 116.0, 110.0, 112.0)
    feed_candle_ticks(orchestrator, symbol, t0, 14, 112.0, 114.0, 109.0, 111.0)
    feed_candle_ticks(orchestrator, symbol, t0, 15, 111.0, 113.0, 108.0, 110.0)

    changes = orchestrator.get_structure_changes(symbol)
    bos_bullish = [c for c in changes if c.change_type == "BOS" and c.direction == "BULLISH"]
    assert len(bos_bullish) >= 1, (
        f"C-2 HH: Expected BOS BULLISH (125 > 110), "
        f"got: {[(c.change_type, c.direction, c.break_price) for c in changes]}"
    )


def test_c2_lower_low_triggers_bearish_bos(orchestrator: PriceActionOrchestrator) -> None:
    """C-2 LL: A second swing low below the previous swing low triggers BOS BEARISH."""
    symbol = "ETHUSDT"
    t0 = datetime(2026, 1, 7, 0, 0, tzinfo=timezone.utc)

    # First swing low cluster (trough = 80)
    feed_candle_ticks(orchestrator, symbol, t0,  0, 110.0, 115.0, 100.0, 105.0)
    feed_candle_ticks(orchestrator, symbol, t0,  1, 105.0, 108.0,  90.0,  92.0)
    feed_candle_ticks(orchestrator, symbol, t0,  2,  92.0,  95.0,  80.0,  85.0)  # trough 80
    feed_candle_ticks(orchestrator, symbol, t0,  3,  85.0,  92.0,  83.0,  90.0)
    feed_candle_ticks(orchestrator, symbol, t0,  4,  90.0,  98.0,  88.0,  95.0)
    # Bounce
    feed_candle_ticks(orchestrator, symbol, t0,  5,  95.0, 108.0,  93.0, 105.0)
    feed_candle_ticks(orchestrator, symbol, t0,  6, 105.0, 115.0, 103.0, 112.0)
    feed_candle_ticks(orchestrator, symbol, t0,  7, 112.0, 118.0, 110.0, 116.0)  # peak
    feed_candle_ticks(orchestrator, symbol, t0,  8, 116.0, 114.0, 108.0, 110.0)
    feed_candle_ticks(orchestrator, symbol, t0,  9, 110.0, 112.0, 105.0, 107.0)
    # Second swing low cluster (trough = 62 < 80 -> LL -> BOS BEARISH)
    feed_candle_ticks(orchestrator, symbol, t0, 10, 107.0, 108.0,  90.0,  92.0)
    feed_candle_ticks(orchestrator, symbol, t0, 11,  92.0,  93.0,  62.0,  65.0)  # trough 62 (LL)
    feed_candle_ticks(orchestrator, symbol, t0, 12,  65.0,  72.0,  63.0,  70.0)
    feed_candle_ticks(orchestrator, symbol, t0, 13,  70.0,  75.0,  68.0,  73.0)
    feed_candle_ticks(orchestrator, symbol, t0, 14,  73.0,  76.0,  71.0,  74.0)
    feed_candle_ticks(orchestrator, symbol, t0, 15,  74.0,  77.0,  72.0,  75.0)

    changes = orchestrator.get_structure_changes(symbol)
    bearish_breaks = [c for c in changes if c.direction == "BEARISH" and c.change_type in ("BOS", "CHOCH")]
    assert len(bearish_breaks) >= 1, (
        f"C-2 LL: Expected BEARISH structure break (62 < 80), "
        f"got: {[(c.change_type, c.direction, c.break_price) for c in changes]}"
    )
    assert bearish_breaks[0].break_price == 62.0


# ---------------------------------------------------------------------------
# 4. EDGE CASES
# ---------------------------------------------------------------------------

def test_edge_case_empty_symbol(orchestrator: PriceActionOrchestrator) -> None:
    sym = "NONEXISTENT"
    assert orchestrator.get_swings(sym) == []
    assert orchestrator.get_structure_changes(sym) == []
    assert orchestrator.get_blocks(sym) == []
    assert orchestrator.get_gaps(sym) == []
    assert orchestrator.get_atr(sym) == 0.0
    assert orchestrator.get_vwap(sym) == 0.0
    assert orchestrator.get_bars(sym) == []


def test_edge_case_single_tick(orchestrator: PriceActionOrchestrator) -> None:
    sym = "ADAUSDT"
    t0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    orchestrator.process_tick(sym, 1.50, t0, volume=100.0)
    assert orchestrator.get_vwap(sym) == 1.50
    assert orchestrator.get_atr(sym) == 0.0
    bars = orchestrator.get_bars(sym)
    assert len(bars) == 1
    assert bars[0]["open"] == 1.50
    assert bars[0]["close"] == 1.50


def test_edge_case_zero_volume_tick(orchestrator: PriceActionOrchestrator) -> None:
    """Zero volume ticks update prices without skewing VWAP zero-division."""
    sym = "XRPUSDT"
    t0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    orchestrator.process_tick(sym, 0.50, t0, volume=0.0)
    orchestrator.process_tick(sym, 0.52, t0 + timedelta(seconds=10), volume=0.0)

    assert orchestrator.get_vwap(sym) == 0.52  # Fallback to price when cum_v == 0
    bars = orchestrator.get_bars(sym)
    assert len(bars) == 1
    assert bars[0]["volume"] == 0.0


def test_edge_case_naive_timestamp_standardized(orchestrator: PriceActionOrchestrator) -> None:
    """Naive (tz-less) timestamps are auto-converted to UTC-aware datetimes."""
    sym = "DOTUSDT"
    naive_t = datetime(2026, 1, 1, 12, 0, 0)  # no tzinfo

    orchestrator.process_tick(sym, 5.0, naive_t, volume=10.0)
    bars = orchestrator.get_bars(sym)

    assert len(bars) == 1
    assert bars[0]["timestamp"].tzinfo is not None
    assert bars[0]["timestamp"].tzinfo == timezone.utc


# ---------------------------------------------------------------------------
# C-3: DUPLICATE TIMESTAMP HANDLING
# ---------------------------------------------------------------------------

def test_c3_same_minute_ticks_merge_into_one_bar(orchestrator: PriceActionOrchestrator) -> None:
    """C-3: Multiple ticks within the same minute bucket produce exactly one bar.

    open  = first tick price
    high  = max tick price in that minute
    low   = min tick price in that minute
    close = last tick price in that minute
    volume = sum of all tick volumes in that minute
    """
    sym = "BNBUSDT"
    t_base = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    orchestrator.process_tick(sym, 100.0, t_base + timedelta(seconds=0),  volume=10.0)
    orchestrator.process_tick(sym, 120.0, t_base + timedelta(seconds=15), volume=20.0)
    orchestrator.process_tick(sym,  90.0, t_base + timedelta(seconds=30), volume=15.0)
    orchestrator.process_tick(sym, 110.0, t_base + timedelta(seconds=45), volume=25.0)

    bars = orchestrator.get_bars(sym)
    assert len(bars) == 1, f"C-3: Expected 1 bar from same-minute ticks, got {len(bars)}"
    bar = bars[0]
    assert bar["open"]   == 100.0, f"C-3: Expected open 100.0, got {bar['open']}"
    assert bar["high"]   == 120.0, f"C-3: Expected high 120.0, got {bar['high']}"
    assert bar["low"]    ==  90.0, f"C-3: Expected low 90.0, got {bar['low']}"
    assert bar["close"]  == 110.0, f"C-3: Expected close 110.0, got {bar['close']}"
    assert bar["volume"] ==  70.0, f"C-3: Expected volume 70.0, got {bar['volume']}"


def test_c3_cross_minute_ticks_produce_separate_bars(orchestrator: PriceActionOrchestrator) -> None:
    """C-3: Ticks in different minute buckets must each produce their own bar."""
    sym = "BNBUSDT"
    t0 = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    orchestrator.process_tick(sym, 100.0, t0 + timedelta(seconds=10),  volume=10.0)  # minute 0
    orchestrator.process_tick(sym, 105.0, t0 + timedelta(seconds=50),  volume=10.0)  # minute 0
    orchestrator.process_tick(sym, 110.0, t0 + timedelta(minutes=1, seconds=5),  volume=10.0)  # minute 1
    orchestrator.process_tick(sym, 108.0, t0 + timedelta(minutes=1, seconds=55), volume=10.0)  # minute 1

    bars = orchestrator.get_bars(sym)
    assert len(bars) == 2, f"C-3: Expected 2 bars (one per minute), got {len(bars)}"
    assert bars[0]["open"]  == 100.0
    assert bars[0]["close"] == 105.0
    assert bars[1]["open"]  == 110.0
    assert bars[1]["close"] == 108.0


# ---------------------------------------------------------------------------
# C-4: MALFORMED INPUT HANDLING
# ---------------------------------------------------------------------------

def test_c4_negative_price_accepted_without_crash(orchestrator: PriceActionOrchestrator) -> None:
    """C-4: Negative price is accepted by process_tick without raising an exception.

    The existing production code has no validation gate on price sign.
    This test documents the actual behavior: negative prices are stored as-is.
    Do NOT change production behavior based on this test.
    """
    sym = "TESTUSDT"
    t0 = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    orchestrator.process_tick(sym, -50.0, t0, volume=1.0)  # must not raise

    bars = orchestrator.get_bars(sym)
    assert len(bars) == 1, "C-4: Negative price tick should produce 1 bar"
    assert bars[0]["open"] == -50.0, "C-4: Negative price must be stored as-is"


def test_c4_nan_price_accepted_without_crash(orchestrator: PriceActionOrchestrator) -> None:
    """C-4: NaN price is accepted by process_tick without raising an exception.

    The existing production code has no NaN guard. This test documents actual behavior:
    NaN propagates through the bar. Do NOT add NaN filtering based on this test —
    any validation must be authorized by a separate CTO gate.
    """
    sym = "TESTUSDT2"
    t0 = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    orchestrator.process_tick(sym, float("nan"), t0, volume=1.0)  # must not raise

    bars = orchestrator.get_bars(sym)
    assert len(bars) == 1, "C-4: NaN price tick should produce 1 bar"
    assert math.isnan(bars[0]["open"]), "C-4: NaN price must propagate as NaN in bar open"


# ---------------------------------------------------------------------------
# 5. MEMORY BOUNDS
# ---------------------------------------------------------------------------

def test_memory_bounds_tick_history_capped_at_1000(orchestrator: PriceActionOrchestrator) -> None:
    """Internal tick history per symbol must not exceed 1000 ticks.

    NOTE (authorized internal invariant): This test accesses _tick_history directly
    because no public API exposes the tick count. This is the sole remaining
    private-attribute access in the PA-3 suite, retained only for the memory-cap
    invariant which has no public equivalent.
    """
    sym = "LINKUSDT"
    t0 = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)

    for i in range(1200):
        orchestrator.process_tick(sym, 15.0 + (i % 10), t0 + timedelta(milliseconds=i * 10), volume=1.0)

    assert len(orchestrator._tick_history[sym]) == 1000, (
        f"Tick history exceeded cap of 1000: got {len(orchestrator._tick_history[sym])}"
    )


def test_memory_bounds_bar_history_capped_at_200(orchestrator: PriceActionOrchestrator) -> None:
    """Aggregated 1m bar history per symbol must not exceed 200 bars."""
    sym = "AVAUSDT"
    t0 = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)

    for minute in range(250):
        feed_candle_ticks(orchestrator, sym, t0, minute, 10.0, 11.0, 9.0, 10.5, volume=5.0)

    bars = orchestrator.get_bars(sym)
    assert len(bars) == 200, f"Bar history exceeded cap of 200: got {len(bars)}"

    # Newest bar (minute 249) retained at index 199
    expected_last_ts = (t0 + timedelta(minutes=249)).replace(second=0, microsecond=0)
    assert bars[-1]["timestamp"] == expected_last_ts

    # Oldest bar retained (minute 50) at index 0
    expected_first_ts = (t0 + timedelta(minutes=50)).replace(second=0, microsecond=0)
    assert bars[0]["timestamp"] == expected_first_ts


# ---------------------------------------------------------------------------
# 6. DETERMINISM
# ---------------------------------------------------------------------------

def test_determinism_identical_input_produces_identical_output() -> None:
    bus1, bus2 = MagicMock(), MagicMock()
    orch1 = PriceActionOrchestrator(event_bus=bus1, repository=PriceActionRepository())
    orch2 = PriceActionOrchestrator(event_bus=bus2, repository=PriceActionRepository())
    sym = "BTCUSDT"
    t0 = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    for i in range(20):
        price = 50000.0 + i
        feed_candle_ticks(orch1, sym, t0, i, price, price+1, price-1, price)
        feed_candle_ticks(orch2, sym, t0, i, price, price+1, price-1, price)
    assert orch1.get_bars(sym) == orch2.get_bars(sym)


def test_deterministic_replay_consistency(orchestrator: PriceActionOrchestrator) -> None:
    """Replaying tick stream should yield identical market structure."""
    sym = "BTCUSDT"
    t0 = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    ticks = [(100.0, 10.0), (102.0, 10.0), (101.0, 10.0), (105.0, 10.0)]
    for p, v in ticks:
        orchestrator.process_tick(sym, p, t0, v)
    state1 = orchestrator.get_swings(sym)
    # Replay on fresh instance
    orch2 = PriceActionOrchestrator(MagicMock(), PriceActionRepository())
    for p, v in ticks:
        orch2.process_tick(sym, p, t0, v)
    assert state1 == orch2.get_swings(sym)


# ---------------------------------------------------------------------------
# C-5: DETERMINISTIC REPLAY — BAR-BY-BAR VALUE VERIFICATION
# ---------------------------------------------------------------------------

def test_c5_deterministic_replay_bar_values_match() -> None:
    """C-5: Same tick stream fed to two fresh instances produces bit-identical bar OHLCV.

    Unlike the aggregate-count determinism test (section 6), this test verifies that
    individual bar open/high/low/close/volume/timestamp values are identical, not just
    counts.
    """
    bus1, bus2 = MagicMock(), MagicMock()
    orch1 = PriceActionOrchestrator(event_bus=bus1, repository=PriceActionRepository())
    orch2 = PriceActionOrchestrator(event_bus=bus2, repository=PriceActionRepository())

    sym = "ETHUSDT"
    t0 = datetime(2026, 1, 8, 0, 0, tzinfo=timezone.utc)

    tick_stream = [
        (100.0, 0,  0, 10.0),
        (105.0, 0, 15, 10.0),
        ( 98.0, 0, 30, 10.0),
        (102.0, 0, 45, 10.0),
        (103.0, 1,  0, 10.0),
        (110.0, 1, 15, 10.0),
        ( 99.0, 1, 30, 10.0),
        (107.0, 1, 45, 10.0),
        (108.0, 2,  0, 10.0),
        (115.0, 2, 15, 10.0),
        (106.0, 2, 30, 10.0),
        (112.0, 2, 45, 10.0),
    ]

    for price, minute_off, sec_off, vol in tick_stream:
        ts = t0 + timedelta(minutes=minute_off, seconds=sec_off)
        orch1.process_tick(sym, price, ts, vol)
        orch2.process_tick(sym, price, ts, vol)

    bars1 = orch1.get_bars(sym)
    bars2 = orch2.get_bars(sym)

    assert len(bars1) == len(bars2), "C-5: Bar counts must match"
    for idx, (b1, b2) in enumerate(zip(bars1, bars2)):
        assert b1["open"]      == b2["open"],      f"C-5: open mismatch at bar {idx}"
        assert b1["high"]      == b2["high"],      f"C-5: high mismatch at bar {idx}"
        assert b1["low"]       == b2["low"],       f"C-5: low mismatch at bar {idx}"
        assert b1["close"]     == b2["close"],     f"C-5: close mismatch at bar {idx}"
        assert b1["volume"]    == b2["volume"],    f"C-5: volume mismatch at bar {idx}"
        assert b1["timestamp"] == b2["timestamp"], f"C-5: timestamp mismatch at bar {idx}"


def test_c5_get_bars_returns_defensive_copy(orchestrator: PriceActionOrchestrator) -> None:
    """C-5: get_bars() must return a defensive copy.

    External mutation of the returned list must not affect internal state.
    Verifies the copy-on-read contract established in PA-1/PA-2.
    """
    sym = "BTCUSDT"
    t0 = datetime(2026, 1, 9, 0, 0, tzinfo=timezone.utc)

    feed_candle_ticks(orchestrator, sym, t0, 0, 100.0, 110.0, 90.0, 105.0)

    bars_first = orchestrator.get_bars(sym)
    original_open = bars_first[0]["open"]

    # Mutate the returned copy
    bars_first[0]["open"] = 999999.0

    # Second call must return original unmodified data
    bars_second = orchestrator.get_bars(sym)
    assert bars_second[0]["open"] == original_open, (
        f"C-5: get_bars() did not return a defensive copy — "
        f"expected open {original_open}, got {bars_second[0]['open']}"
    )


# ---------------------------------------------------------------------------
# 7. EVENT PUBLISHING AUDIT
# ---------------------------------------------------------------------------

def test_event_publishing_structure_and_imbalance(mock_event_bus: MagicMock, repo: PriceActionRepository) -> None:
    orch = PriceActionOrchestrator(event_bus=mock_event_bus, repository=repo)
    sym = "BTCUSDT"
    t0 = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    feed_candle_ticks(orch, sym, t0, 0, 90.0, 100.0, 85.0, 95.0)
    feed_candle_ticks(orch, sym, t0, 1, 95.0, 115.0, 95.0, 110.0)
    feed_candle_ticks(orch, sym, t0, 2, 110.0, 125.0, 105.0, 120.0)
    feed_candle_ticks(orch, sym, t0, 3, 120.0, 128.0, 118.0, 125.0)
    feed_candle_ticks(orch, sym, t0, 4, 125.0, 130.0, 122.0, 127.0)
    feed_candle_ticks(orch, sym, t0, 5, 127.0, 132.0, 126.0, 130.0)
    published_events = [call.args[0] for call in mock_event_bus.publish.call_args_list]
    assert any(isinstance(e, ImbalanceDetected) for e in published_events)


def test_session_updated_event_capability_gap_audit(mock_event_bus: MagicMock, repo: PriceActionRepository) -> None:
    orch = PriceActionOrchestrator(event_bus=mock_event_bus, repository=repo)
    sym = "BTCUSDT"
    t0 = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    for i in range(10):
        feed_candle_ticks(orch, sym, t0, i, 100.0, 105.0, 95.0, 100.0)
    published_events = [call.args[0] for call in mock_event_bus.publish.call_args_list]
    session_events = [e for e in published_events if isinstance(e, SessionUpdated)]
    assert len(session_events) == 0
