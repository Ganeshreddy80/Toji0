"""Unit tests for the Data Quality Validation engine."""

from __future__ import annotations

from datetime import UTC, datetime
import pytest

from data.schemas.market_data import OHLCV, OrderBookSnapshot, Trade
from market_gateway.validation.validator import MarketDataValidator


def test_validator_ohlcv_bounds():
    validator = MarketDataValidator()

    # Valid candle
    valid_bar = OHLCV(
        symbol="BTCUSDT",
        timestamp=datetime.now(UTC),
        open=95000.0,
        high=95500.0,
        low=94800.0,
        close=95200.0,
        volume=12.5,
        interval="1m",
    )
    errors = validator.validate_event(valid_bar)
    assert len(errors) == 0

    # Non-UTC timezone violation
    invalid_tz = OHLCV(
        symbol="BTCUSDT",
        timestamp=datetime.now(),  # naive local time
        open=95000.0,
        high=95500.0,
        low=94800.0,
        close=95200.0,
        volume=12.5,
        interval="1m",
    )
    errors = validator.validate_event(invalid_tz)
    assert any("Timezone inconsistency" in err for err in errors)

    # Invalid high/low bound crossed
    invalid_bounds = OHLCV(
        symbol="BTCUSDT",
        timestamp=datetime.now(UTC),
        open=95000.0,
        high=94000.0,  # high below open/low
        low=94500.0,
        close=94800.0,
        volume=12.5,
        interval="1m",
    )
    errors = validator.validate_event(invalid_bounds)
    assert any("High" in err and "below" in err for err in errors)


def test_validator_order_book():
    validator = MarketDataValidator()

    # Crossed spread bids/asks crossed
    crossed_book = OrderBookSnapshot(
        symbol="BTCUSDT",
        timestamp=datetime.now(UTC),
        bids=[(95000.0, 1.0), (94900.0, 2.0)],
        asks=[(94800.0, 1.5), (95100.0, 2.5)],  # ask below bid
    )
    errors = validator.validate_event(crossed_book)
    assert any("crossed" in err.lower() for err in errors)


def test_validator_sequence_and_duplicates():
    validator = MarketDataValidator()
    ts = datetime.now(UTC)

    bar1 = OHLCV(
        symbol="BTCUSDT",
        timestamp=ts,
        open=95000.0,
        high=95500.0,
        low=94800.0,
        close=95200.0,
        volume=12.5,
        interval="1m",
    )
    # First candle passes
    errors = validator.validate_event(bar1)
    assert len(errors) == 0

    # Second candle with exact same timestamp -> Duplicate violation
    errors = validator.validate_event(bar1)
    assert any("Duplicate event" in err for err in errors)

    # Third candle with older timestamp -> Sequence ordering violation
    bar_old = OHLCV(
        symbol="BTCUSDT",
        timestamp=ts - float(30.0) * datetime.now().resolution, # older time
        open=95000.0,
        high=95500.0,
        low=94800.0,
        close=95200.0,
        volume=12.5,
        interval="1m",
    )
    errors = validator.validate_event(bar_old)
    assert any("Sequence ordering violation" in err for err in errors)
