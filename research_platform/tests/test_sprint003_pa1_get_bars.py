"""PA-1 focused tests for the get_bars() public contract.

Verifies:
1. Unknown symbol returns empty list.
2. Correct 1m OHLCV bars are returned after deterministic tick ingestion.
3. Defensive-copy guarantee — mutating returned list or bar dict does not affect internal state.

Rules:
- Do NOT access orch._bars directly in any assertion.
- Do NOT access any other private attribute of PriceActionOrchestrator.
- All tick timestamps are UTC-aware.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

import pytest

from research_platform.price_action.orchestrator import PriceActionOrchestrator
from research_platform.price_action.repository import PriceActionRepository


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_event_bus() -> MagicMock:
    """Minimal EventBus stub — just needs a callable publish()."""
    bus = MagicMock()
    bus.publish = MagicMock()
    return bus


@pytest.fixture
def orchestrator(mock_event_bus: MagicMock) -> PriceActionOrchestrator:
    """Fresh PriceActionOrchestrator with an in-memory repository."""
    repo = PriceActionRepository()
    return PriceActionOrchestrator(event_bus=mock_event_bus, repository=repo)


# ---------------------------------------------------------------------------
# Test 1 — Unknown symbol returns empty list
# ---------------------------------------------------------------------------

def test_get_bars_unknown_symbol_returns_empty_list(orchestrator: PriceActionOrchestrator) -> None:
    """get_bars() on a symbol that has never received a tick must return []."""
    result = orchestrator.get_bars("UNKNOWN_SYMBOL_XYZZY")
    assert result == [], f"Expected [], got {result!r}"


# ---------------------------------------------------------------------------
# Test 2 — Correct bars after deterministic tick ingestion
# ---------------------------------------------------------------------------

def test_get_bars_returns_correct_bars_after_tick_ingestion(orchestrator: PriceActionOrchestrator) -> None:
    """Feed deterministic ticks and verify the returned OHLCV bar structure.

    Strategy:
    - All ticks in the first minute go into bar 0.
    - Ticks in the second minute go into bar 1.
    - We verify open, high, low, close, volume, and timestamp correctness.
    """
    symbol = "BTCUSDT"
    t0 = datetime(2026, 1, 1, 9, 0, 0, tzinfo=timezone.utc)   # minute 0: 09:00
    t1 = datetime(2026, 1, 1, 9, 1, 0, tzinfo=timezone.utc)   # minute 1: 09:01

    # ── Minute 0 ticks ──────────────────────────────────────────────────────
    # open=100 (first price), high=105 (max), low=98 (min), close=103 (last)
    orchestrator.process_tick(symbol, 100.0, t0 + timedelta(seconds=0),  volume=10.0)
    orchestrator.process_tick(symbol, 105.0, t0 + timedelta(seconds=15), volume=5.0)
    orchestrator.process_tick(symbol, 98.0,  t0 + timedelta(seconds=30), volume=8.0)
    orchestrator.process_tick(symbol, 103.0, t0 + timedelta(seconds=45), volume=7.0)

    # ── Minute 1 ticks — opens a new bar ────────────────────────────────────
    # open=103, high=110, low=103, close=110
    orchestrator.process_tick(symbol, 103.0, t1 + timedelta(seconds=0),  volume=6.0)
    orchestrator.process_tick(symbol, 110.0, t1 + timedelta(seconds=30), volume=4.0)

    bars = orchestrator.get_bars(symbol)

    # Must have exactly 2 bars
    assert len(bars) == 2, f"Expected 2 bars, got {len(bars)}"

    # ── Bar 0 assertions ────────────────────────────────────────────────────
    bar0 = bars[0]
    assert bar0["open"]   == 100.0, f"bar0 open: expected 100.0, got {bar0['open']}"
    assert bar0["high"]   == 105.0, f"bar0 high: expected 105.0, got {bar0['high']}"
    assert bar0["low"]    == 98.0,  f"bar0 low:  expected 98.0, got {bar0['low']}"
    assert bar0["close"]  == 103.0, f"bar0 close: expected 103.0, got {bar0['close']}"
    assert bar0["volume"] == 30.0,  f"bar0 volume: expected 30.0, got {bar0['volume']}"

    # Timestamp must be the minute-truncated UTC time (second=0, microsecond=0)
    expected_ts0 = t0.replace(second=0, microsecond=0)
    assert bar0["timestamp"] == expected_ts0, (
        f"bar0 timestamp: expected {expected_ts0}, got {bar0['timestamp']}"
    )

    # ── Bar 1 assertions ────────────────────────────────────────────────────
    bar1 = bars[1]
    assert bar1["open"]   == 103.0, f"bar1 open: expected 103.0, got {bar1['open']}"
    assert bar1["high"]   == 110.0, f"bar1 high: expected 110.0, got {bar1['high']}"
    assert bar1["low"]    == 103.0, f"bar1 low:  expected 103.0, got {bar1['low']}"
    assert bar1["close"]  == 110.0, f"bar1 close: expected 110.0, got {bar1['close']}"
    assert bar1["volume"] == 10.0,  f"bar1 volume: expected 10.0, got {bar1['volume']}"

    expected_ts1 = t1.replace(second=0, microsecond=0)
    assert bar1["timestamp"] == expected_ts1, (
        f"bar1 timestamp: expected {expected_ts1}, got {bar1['timestamp']}"
    )

    # ── Required keys present in every bar ──────────────────────────────────
    required_keys = {"timestamp", "open", "high", "low", "close", "volume"}
    for i, bar in enumerate(bars):
        missing = required_keys - bar.keys()
        assert not missing, f"bar[{i}] missing keys: {missing}"


# ---------------------------------------------------------------------------
# Test 3a — Defensive copy: mutating returned list does not affect state
# ---------------------------------------------------------------------------

def test_get_bars_list_mutation_does_not_affect_internal_state(orchestrator: PriceActionOrchestrator) -> None:
    """Appending to or clearing the returned list must not change what get_bars() returns next."""
    symbol = "ETHUSDT"
    t0 = datetime(2026, 1, 1, 9, 0, 0, tzinfo=timezone.utc)

    orchestrator.process_tick(symbol, 3000.0, t0, volume=1.0)
    orchestrator.process_tick(symbol, 3001.0, t0 + timedelta(minutes=1), volume=1.0)

    # Snapshot the current result (reference snapshot, not a reference to internal state)
    original = orchestrator.get_bars(symbol)
    original_len = len(original)

    # Mutate the returned list
    mutated = orchestrator.get_bars(symbol)
    mutated.append({"fake": True})
    mutated.clear()

    # Internal state must be unchanged
    after = orchestrator.get_bars(symbol)
    assert len(after) == original_len, (
        f"Internal bar count changed after list mutation. "
        f"Expected {original_len}, got {len(after)}"
    )


# ---------------------------------------------------------------------------
# Test 3b — Defensive copy: mutating returned bar dict does not affect state
# ---------------------------------------------------------------------------

def test_get_bars_dict_mutation_does_not_affect_internal_state(orchestrator: PriceActionOrchestrator) -> None:
    """Modifying a field in a returned bar dict must not change what get_bars() returns next."""
    symbol = "SOLUSDT"
    t0 = datetime(2026, 1, 1, 9, 0, 0, tzinfo=timezone.utc)

    orchestrator.process_tick(symbol, 150.0, t0, volume=5.0)
    # Force a second bar so bar[0] is fully closed
    orchestrator.process_tick(symbol, 155.0, t0 + timedelta(minutes=1), volume=3.0)

    original_close = orchestrator.get_bars(symbol)[0]["close"]

    # Mutate the returned bar dict
    bars = orchestrator.get_bars(symbol)
    bars[0]["close"] = 999_999.0

    # Internal state must not be affected
    close_after = orchestrator.get_bars(symbol)[0]["close"]
    assert close_after == original_close, (
        f"Internal bar close changed after dict mutation. "
        f"Expected {original_close}, got {close_after}"
    )
    assert close_after != 999_999.0, "Internal state was mutated via returned dict!"
