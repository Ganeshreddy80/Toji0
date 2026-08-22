"""Unit tests for the Data Quality validation engine."""

from __future__ import annotations

from datetime import UTC, datetime
import pandas as pd
import pytest

from data.quality.analyzer import DataQualityAnalyzer
from data.schemas.market_data import OHLCV


def test_schema_validation():
    analyzer = DataQualityAnalyzer()
    valid_data = [
        {
            "symbol": "BTC/USDT",
            "timestamp": datetime.now(UTC),
            "open": 95000.0,
            "high": 95500.0,
            "low": 94800.0,
            "close": 95200.0,
            "volume": 5.0,
            "interval": "1m",
        }
    ]
    res = analyzer.validate_schema(valid_data, OHLCV)
    assert res.passed is True
    assert len(res.errors) == 0

    # Invalid data
    invalid_data = [{"symbol": "BTC/USDT", "open": -100.0}]  # missing required fields, bad open price
    res_invalid = analyzer.validate_schema(invalid_data, OHLCV)
    assert res_invalid.passed is False
    assert len(res_invalid.errors) > 0


def test_check_missing_gaps():
    analyzer = DataQualityAnalyzer()
    dates = pd.to_datetime(["2026-06-25T12:00:00", "2026-06-25T12:01:00", "2026-06-25T12:03:00"])  # 12:02 is missing
    df = pd.DataFrame({"close": [10.0, 11.0, 12.0]}, index=dates)

    res = analyzer.check_missing(df, "1m")
    assert res.passed is False
    assert res.metrics["missing_count"] == 1.0


def test_check_duplicates():
    analyzer = DataQualityAnalyzer()
    # Duplicate index
    dates = pd.to_datetime(["2026-06-25T12:00:00", "2026-06-25T12:00:00", "2026-06-25T12:01:00"])
    df = pd.DataFrame({"close": [10.0, 11.0, 12.0]}, index=dates)

    res = analyzer.check_duplicates(df)
    assert res.passed is False
    assert res.metrics["duplicate_count"] == 1.0


def test_check_ordering():
    analyzer = DataQualityAnalyzer()
    # Out of order index
    dates = pd.to_datetime(["2026-06-25T12:01:00", "2026-06-25T12:00:00"])
    df = pd.DataFrame({"close": [10.0, 11.0]}, index=dates)

    res = analyzer.check_ordering(df)
    assert res.passed is False


def test_check_integrity():
    analyzer = DataQualityAnalyzer()
    # Valid OHLC
    df_valid = pd.DataFrame(
        {"open": [10.0], "high": [12.0], "low": [9.0], "close": [11.0], "volume": [100.0]},
        index=pd.to_datetime(["2026-06-25T12:00:00"]),
    )
    assert analyzer.check_integrity(df_valid).passed is True

    # High < Low
    df_bad = pd.DataFrame(
        {"open": [10.0], "high": [8.0], "low": [9.0], "close": [11.0]},
        index=pd.to_datetime(["2026-06-25T12:00:00"]),
    )
    assert analyzer.check_integrity(df_bad).passed is False

    # Negative prices
    df_neg = pd.DataFrame(
        {"open": [-10.0], "high": [12.0], "low": [9.0], "close": [11.0]},
        index=pd.to_datetime(["2026-06-25T12:00:00"]),
    )
    assert analyzer.check_integrity(df_neg).passed is False
