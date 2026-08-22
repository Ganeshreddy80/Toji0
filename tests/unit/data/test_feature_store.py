"""Unit tests for the Feature Store calculations, caching, and registry."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import numpy as np
import pandas as pd
import pytest

from data.feature_store.cache import FeatureCache
from data.feature_store.definitions import (
    ADXFeature,
    ATRFeature,
    EMAFeature,
    FundingFeature,
    LiquidityFeature,
    MACDFeature,
    MomentumFeature,
    OpenInterestFeature,
    RSIFeature,
    VolatilityFeature,
    VolumeProfileFeature,
    VWAPFeature,
)
from data.feature_store.registry import FeatureRegistry


@pytest.fixture
def sample_market_data() -> pd.DataFrame:
    """Generate dummy OHLCV price series dataframe."""
    dates = pd.date_range(start="2026-06-01", periods=100, freq="1h", tz="UTC")
    np.random.seed(42)
    close = 100.0 + np.random.randn(100).cumsum()
    high = close + np.random.rand(100) * 2.0
    low = close - np.random.rand(100) * 2.0
    open_val = close + np.random.randn(100)
    volume = 100.0 + np.random.rand(100) * 1000.0

    return pd.DataFrame(
        {
            "open": open_val,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "funding_rate": 0.0001,
            "open_interest": 50000.0,
        },
        index=dates,
    )


def test_feature_registry():
    registry = FeatureRegistry()
    ema = EMAFeature()
    registry.register(ema)

    assert registry.get("EMA", "1.0.0") == ema

    # Duplicate registration raises error
    with pytest.raises(ValueError):
        registry.register(ema)

    # Missing registry key raises error
    with pytest.raises(KeyError):
        registry.get("RSI", "1.0.0")


def test_feature_cache(sample_market_data):
    cache = FeatureCache()
    start = datetime(2026, 6, 1, tzinfo=UTC)
    end = start + timedelta(hours=10)

    # Save feature df
    df_feat = pd.DataFrame({"rsi": np.random.rand(11)}, index=sample_market_data.index[:11])
    cache.save_features("BTC/USDT", "RSI", "1.0.0", df_feat)

    # Retrieve combined
    res = cache.get_features("BTC/USDT", [("RSI", "1.0.0")], start, end)
    assert not res.empty
    assert "rsi" in res.columns
    assert len(res) == 11


def test_ema_calculation(sample_market_data):
    feat = EMAFeature(period=10)
    res = feat.calculate(sample_market_data)
    assert "ema" in res.columns
    assert not res["ema"].isna().all()


def test_rsi_calculation(sample_market_data):
    feat = RSIFeature(period=14)
    res = feat.calculate(sample_market_data)
    assert "rsi" in res.columns
    # RSI values should lie in [0, 100] range
    valid_range = res["rsi"].dropna()
    assert (valid_range >= 0.0).all() and (valid_range <= 100.0).all()


def test_atr_calculation(sample_market_data):
    feat = ATRFeature(period=14)
    res = feat.calculate(sample_market_data)
    assert "atr" in res.columns
    assert (res["atr"].dropna() >= 0.0).all()


def test_vwap_calculation(sample_market_data):
    feat = VWAPFeature()
    res = feat.calculate(sample_market_data)
    assert "vwap" in res.columns
    assert (res["vwap"].dropna() > 0.0).all()


def test_macd_calculation(sample_market_data):
    feat = MACDFeature()
    res = feat.calculate(sample_market_data)
    assert "macd" in res.columns
    assert "macd_signal" in res.columns
    assert "macd_hist" in res.columns


def test_adx_calculation(sample_market_data):
    feat = ADXFeature(period=14)
    res = feat.calculate(sample_market_data)
    assert "adx" in res.columns


def test_momentum_calculation(sample_market_data):
    feat = MomentumFeature(period=10)
    res = feat.calculate(sample_market_data)
    assert "momentum" in res.columns


def test_volatility_calculation(sample_market_data):
    feat = VolatilityFeature(period=10)
    res = feat.calculate(sample_market_data)
    assert "volatility" in res.columns


def test_volume_profile_calculation(sample_market_data):
    feat = VolumeProfileFeature(period=10)
    res = feat.calculate(sample_market_data)
    assert "volume_profile_poc" in res.columns


def test_alternative_features_calculations(sample_market_data):
    funding = FundingFeature().calculate(sample_market_data)
    oi = OpenInterestFeature().calculate(sample_market_data)
    liq = LiquidityFeature().calculate(sample_market_data)

    assert "funding_rate" in funding.columns
    assert "open_interest" in oi.columns
    assert "liquidity" in liq.columns
