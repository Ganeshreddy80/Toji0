"""Sprint 003 — PA-4 Historical Validation & Deterministic Replay Test Suite.

Verifies deterministic, bit-identical, and reproducible Price Action behavior
over an extended 1,440-minute (24-hour) OHLCV replay sequence across independent
PriceActionOrchestrator instances.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple
from unittest.mock import MagicMock

import pytest
from research_platform.price_action.models import (
    BlockStructure,
    ImbalanceGap,
    MarketStructureChange,
    SwingPoint,
)
from research_platform.price_action.orchestrator import PriceActionOrchestrator
from research_platform.price_action.repository import PriceActionRepository


# ---------------------------------------------------------------------------
# DETERMINISTIC DATASET GENERATOR
# ---------------------------------------------------------------------------

def generate_deterministic_historical_ticks(
    num_candles: int = 1440,
    symbol: str = "BTCUSDT",
    start_time: datetime | None = None,
    start_price: float = 50000.0,
    seed: int = 42
) -> List[Tuple[str, float, datetime, float]]:
    """Generates a deterministic 1-minute OHLCV tick sequence over a given window.

    Classification: Synthetic Historical-Replay Determinism Validation Dataset.
    Source: Mathematical multi-regime wave equation (trend, range, selloff, recovery).
    Timeframe: 1m resolution (4 ticks per candle: Open, High, Low, Close).
    Candle Count: num_candles (default 1,440 = 24 continuous hours).
    Timestamp Range: start_time to start_time + num_candles minutes.
    Timezone: UTC (timezone-aware).

    Returns list of tuples: (symbol, price, timestamp, volume).
    """
    if start_time is None:
        start_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    ticks: List[Tuple[str, float, datetime, float]] = []

    for i in range(num_candles):
        bar_time = start_time + timedelta(minutes=i)

        # Multi-regime deterministic price curve
        if i < 300:
            # Regime 1: Steady uptrend (50,000 -> 53,000)
            base = start_price + (i * 10.0) + (150.0 * math.sin(i / 10.0))
        elif i < 600:
            # Regime 2: Sideways range (53,000 +/- 200)
            base = start_price + 3000.0 + (200.0 * math.cos((i - 300) / 15.0))
        elif i < 900:
            # Regime 3: Sharp selloff / FVG creation (53,000 -> 46,000)
            base = start_price + 3000.0 - ((i - 600) * 23.33) + (100.0 * math.sin(i / 5.0))
        elif i < 1200:
            # Regime 4: Bullish reversal & structure break (46,000 -> 51,500)
            base = 46000.0 + ((i - 900) * 18.33) + (120.0 * math.cos(i / 8.0))
        else:
            # Regime 5: High volatility consolidation (51,500 +/- 350)
            base = 51500.0 + (350.0 * math.sin((i - 1200) / 12.0))

        # Synthetic OHLC bounds derived deterministically
        delta = abs(math.sin(i * 0.73 + seed)) * 40.0 + 10.0
        open_p = base
        high_p = max(base + delta, base + 5.0)
        low_p = min(base - delta, base - 5.0)
        close_p = base + (delta * 0.3 if i % 2 == 0 else -delta * 0.3)
        volume = 10.0 + (abs(math.cos(i * 0.5)) * 50.0)

        # 4 ticks per 1m candle (Open, High, Low, Close) within the minute
        ticks.append((symbol, open_p, bar_time, volume * 0.25))
        ticks.append((symbol, high_p, bar_time + timedelta(seconds=15), volume * 0.25))
        ticks.append((symbol, low_p, bar_time + timedelta(seconds=30), volume * 0.25))
        ticks.append((symbol, close_p, bar_time + timedelta(seconds=45), volume * 0.25))

    return ticks


def serialize_output_canonical(
    bars: List[Dict[str, Any]],
    vwap: float,
    atr: float,
    swings: List[SwingPoint],
    gaps: List[ImbalanceGap],
    structure_changes: List[MarketStructureChange],
    blocks: List[BlockStructure]
) -> str:
    """Serializes Price Action outputs into a canonical, deterministic JSON string."""
    payload = {
        "bars": [
            {
                "timestamp": b["timestamp"].isoformat() if isinstance(b["timestamp"], datetime) else str(b["timestamp"]),
                "open": round(b["open"], 6),
                "high": round(b["high"], 6),
                "low": round(b["low"], 6),
                "close": round(b["close"], 6),
                "volume": round(b["volume"], 6),
            }
            for b in bars
        ],
        "vwap": round(vwap, 6),
        "atr": round(atr, 6),
        "swings": [
            {
                "point_type": s.point_type,
                "price": round(s.price, 6),
                "timestamp": s.timestamp.isoformat() if isinstance(s.timestamp, datetime) else str(s.timestamp),
            }
            for s in swings
        ],
        "gaps": [
            {
                "gap_type": g.gap_type,
                "high": round(g.high, 6),
                "low": round(g.low, 6),
                "timestamp": g.timestamp.isoformat() if isinstance(g.timestamp, datetime) else str(g.timestamp),
            }
            for g in gaps
        ],
        "structure_changes": [
            {
                "change_type": sc.change_type,
                "direction": sc.direction,
                "break_price": round(sc.break_price, 6),
                "trigger_price": round(sc.trigger_price, 6),
                "timestamp": sc.timestamp.isoformat() if isinstance(sc.timestamp, datetime) else str(sc.timestamp),
            }
            for sc in structure_changes
        ],
        "blocks": [
            {
                "block_type": bl.block_type,
                "direction": bl.direction,
                "high": round(bl.high, 6),
                "low": round(bl.low, 6),
                "volume": round(bl.volume, 6),
                "timestamp": bl.timestamp.isoformat() if isinstance(bl.timestamp, datetime) else str(bl.timestamp),
            }
            for bl in blocks
        ],
    }
    return json.dumps(payload, sort_keys=True)


# ---------------------------------------------------------------------------
# PA-4 HISTORICAL REPLAY TESTS
# ---------------------------------------------------------------------------

def test_1_historical_replay_execution() -> None:
    """Requirement 1: Extended 1,440-minute historical replay executes cleanly."""
    sym = "BTCUSDT"
    repo = PriceActionRepository()
    orch = PriceActionOrchestrator(event_bus=MagicMock(), repository=repo)

    ticks = generate_deterministic_historical_ticks(num_candles=1440, symbol=sym)
    assert len(ticks) == 5760  # 1440 candles * 4 ticks per candle

    for tick_sym, price, ts, vol in ticks:
        orch.process_tick(tick_sym, price, ts, vol)

    bars = orch.get_bars(sym)
    assert len(bars) == 200  # Capped by memory bound at 200 bars after 1440 minutes
    assert orch.get_vwap(sym) > 0.0
    assert orch.get_atr(sym) > 0.0
    assert len(orch.get_swings(sym)) > 0
    assert len(orch.get_gaps(sym)) > 0
    assert len(orch.get_structure_changes(sym)) > 0
    assert len(orch.get_blocks(sym)) > 0


def test_2_two_pass_deterministic_replay() -> None:
    """Requirement 2 & 3: Two independent instances fed identical 1,440m replay

    produce bit-for-bit identical outputs with zero tolerance deviation.
    """
    sym = "BTCUSDT"
    ticks = generate_deterministic_historical_ticks(num_candles=1440, symbol=sym)

    # Pass A
    repo_a = PriceActionRepository()
    orch_a = PriceActionOrchestrator(event_bus=MagicMock(), repository=repo_a)
    for tick_sym, price, ts, vol in ticks:
        orch_a.process_tick(tick_sym, price, ts, vol)

    # Pass B
    repo_b = PriceActionRepository()
    orch_b = PriceActionOrchestrator(event_bus=MagicMock(), repository=repo_b)
    for tick_sym, price, ts, vol in ticks:
        orch_b.process_tick(tick_sym, price, ts, vol)

    # Bit-for-bit direct output assertions
    assert orch_a.get_bars(sym) == orch_b.get_bars(sym)
    assert orch_a.get_vwap(sym) == orch_b.get_vwap(sym)
    assert orch_a.get_atr(sym) == orch_b.get_atr(sym)
    assert orch_a.get_swings(sym) == orch_b.get_swings(sym)
    assert orch_a.get_gaps(sym) == orch_b.get_gaps(sym)
    assert orch_a.get_structure_changes(sym) == orch_b.get_structure_changes(sym)
    assert orch_a.get_blocks(sym) == orch_b.get_blocks(sym)


def test_3_output_fingerprint_sha256() -> None:
    """Requirement 3: Canonical JSON serialization of Run A and Run B yields

    an identical full 64-character SHA-256 fingerprint hash.
    """
    sym = "BTCUSDT"
    ticks = generate_deterministic_historical_ticks(num_candles=1440, symbol=sym)

    orch_a = PriceActionOrchestrator(event_bus=MagicMock(), repository=PriceActionRepository())
    for tick_sym, price, ts, vol in ticks:
        orch_a.process_tick(tick_sym, price, ts, vol)

    orch_b = PriceActionOrchestrator(event_bus=MagicMock(), repository=PriceActionRepository())
    for tick_sym, price, ts, vol in ticks:
        orch_b.process_tick(tick_sym, price, ts, vol)

    str_a = serialize_output_canonical(
        orch_a.get_bars(sym), orch_a.get_vwap(sym), orch_a.get_atr(sym),
        orch_a.get_swings(sym), orch_a.get_gaps(sym),
        orch_a.get_structure_changes(sym), orch_a.get_blocks(sym)
    )
    str_b = serialize_output_canonical(
        orch_b.get_bars(sym), orch_b.get_vwap(sym), orch_b.get_atr(sym),
        orch_b.get_swings(sym), orch_b.get_gaps(sym),
        orch_b.get_structure_changes(sym), orch_b.get_blocks(sym)
    )

    hash_a = hashlib.sha256(str_a.encode("utf-8")).hexdigest()
    hash_b = hashlib.sha256(str_b.encode("utf-8")).hexdigest()

    # Print full 64-char hashes for report capture
    print(f"\nRun A SHA-256 = {hash_a}")
    print(f"Run B SHA-256 = {hash_b}")

    assert hash_a == hash_b
    assert len(hash_a) == 64


def test_4_event_sequence_identity() -> None:
    """Requirement 4: Event publishing sequence, type ordering, and payloads

    are 100% identical between independent replay runs.
    """
    sym = "BTCUSDT"
    ticks = generate_deterministic_historical_ticks(num_candles=1440, symbol=sym)

    bus_a = MagicMock()
    orch_a = PriceActionOrchestrator(event_bus=bus_a, repository=PriceActionRepository())
    for tick_sym, price, ts, vol in ticks:
        orch_a.process_tick(tick_sym, price, ts, vol)

    bus_b = MagicMock()
    orch_b = PriceActionOrchestrator(event_bus=bus_b, repository=PriceActionRepository())
    for tick_sym, price, ts, vol in ticks:
        orch_b.process_tick(tick_sym, price, ts, vol)

    events_a = [call.args[0] for call in bus_a.publish.call_args_list]
    events_b = [call.args[0] for call in bus_b.publish.call_args_list]

    assert len(events_a) == len(events_b)
    assert len(events_a) > 0

    for ev_a, ev_b in zip(events_a, events_b):
        assert type(ev_a) is type(ev_b)
        assert ev_a.source == ev_b.source
        assert ev_a.payload == ev_b.payload


def test_5_memory_boundary_and_retained_window() -> None:
    """Requirement 5 & Correction 4: Memory boundaries are strictly maintained during continuous

    1,440-candle replay:
    - len(_tick_history[symbol]) <= 1000 at all times
    - len(get_bars(symbol)) <= 200 during warmup (minutes 1 to 200)
    - len(get_bars(symbol)) == 200 after minute 200
    - Retained 200-bar window is identical across runs.
    """
    sym = "BTCUSDT"
    ticks = generate_deterministic_historical_ticks(num_candles=1440, symbol=sym)

    orch_a = PriceActionOrchestrator(event_bus=MagicMock(), repository=PriceActionRepository())
    orch_b = PriceActionOrchestrator(event_bus=MagicMock(), repository=PriceActionRepository())

    for tick_idx, (tick_sym, price, ts, vol) in enumerate(ticks):
        orch_a.process_tick(tick_sym, price, ts, vol)
        orch_b.process_tick(tick_sym, price, ts, vol)

        # Invariant 1: Tick history <= 1000 at all times
        assert len(orch_a._tick_history[sym]) <= 1000
        assert len(orch_b._tick_history[sym]) <= 1000

        # Invariant 2: Bar history <= 200 at all times
        assert len(orch_a.get_bars(sym)) <= 200
        assert len(orch_b.get_bars(sym)) <= 200

    bars_a = orch_a.get_bars(sym)
    bars_b = orch_b.get_bars(sym)

    # Invariant 3: Bar history == 200 after 1,440 minutes processed
    assert len(bars_a) == 200
    assert len(bars_b) == 200
    assert bars_a == bars_b

    # Verify retained window timestamps (minute 1240 to minute 1439)
    start_ts = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    expected_oldest_retained = start_ts + timedelta(minutes=1240)
    expected_newest_retained = start_ts + timedelta(minutes=1439)

    assert bars_a[0]["timestamp"] == expected_oldest_retained
    assert bars_a[-1]["timestamp"] == expected_newest_retained


def test_6_timestamp_ordering_validation() -> None:
    """Requirement 6: Replaying ticks with monotonically increasing timestamps

    aggregates bars deterministically into 1-minute buckets.
    """
    sym = "ETHUSDT"
    orch = PriceActionOrchestrator(event_bus=MagicMock(), repository=PriceActionRepository())
    t0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    # 10 minutes of sequential ticks
    for m in range(10):
        bar_ts = t0 + timedelta(minutes=m)
        orch.process_tick(sym, 3000.0 + m, bar_ts, 1.0)

    bars = orch.get_bars(sym)
    assert len(bars) == 10
    for idx, bar in enumerate(bars):
        assert bar["timestamp"] == t0 + timedelta(minutes=idx)
        assert bar["close"] == 3000.0 + idx


def test_7_duplicate_timestamp_behavior_validation() -> None:
    """Requirement 7: Duplicate timestamp ticks within the same minute merge

    into the active 1-minute bar deterministically without duplicating bars.
    """
    sym = "SOLUSDT"
    orch = PriceActionOrchestrator(event_bus=MagicMock(), repository=PriceActionRepository())
    t0 = datetime(2026, 1, 1, 15, 30, 0, tzinfo=timezone.utc)

    # 5 ticks with identical minute timestamps
    orch.process_tick(sym, 100.0, t0, 10.0)
    orch.process_tick(sym, 105.0, t0 + timedelta(seconds=10), 15.0)
    orch.process_tick(sym, 98.0, t0 + timedelta(seconds=20), 5.0)
    orch.process_tick(sym, 102.0, t0 + timedelta(seconds=30), 20.0)
    orch.process_tick(sym, 103.0, t0 + timedelta(seconds=45), 10.0)

    bars = orch.get_bars(sym)
    assert len(bars) == 1
    assert bars[0]["open"] == 100.0
    assert bars[0]["high"] == 105.0
    assert bars[0]["low"] == 98.0
    assert bars[0]["close"] == 103.0
    assert bars[0]["volume"] == 60.0


def test_8_missing_and_invalid_candle_characterization() -> None:
    """Requirement 8: Characterizes deterministic system behavior when encountering

    timestamp gaps (missing minutes), zero volume, negative prices, and NaN values.
    """
    sym = "BTCUSDT"
    orch = PriceActionOrchestrator(event_bus=MagicMock(), repository=PriceActionRepository())
    t0 = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)

    # Minute 0: normal
    orch.process_tick(sym, 50000.0, t0, 1.0)

    # Minute 5: gap of 4 minutes
    orch.process_tick(sym, 50500.0, t0 + timedelta(minutes=5), 1.0)

    # Minute 6: zero volume tick
    orch.process_tick(sym, 50600.0, t0 + timedelta(minutes=6), 0.0)

    # Minute 7: negative price tick (stored without crash)
    orch.process_tick(sym, -10.0, t0 + timedelta(minutes=7), 1.0)

    # Minute 8: NaN price tick (stored without crash)
    orch.process_tick(sym, float("nan"), t0 + timedelta(minutes=8), 1.0)

    bars = orch.get_bars(sym)
    assert len(bars) == 5
    assert bars[0]["timestamp"] == t0
    assert bars[1]["timestamp"] == t0 + timedelta(minutes=5)
    assert bars[2]["volume"] == 0.0
    assert bars[3]["close"] == -10.0
    assert math.isnan(bars[4]["close"])
