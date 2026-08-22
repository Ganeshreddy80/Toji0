"""Unit tests for the TOJI Research Platform foundation.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from data.schemas.market_data import OHLCV, Trade
from research_platform.data.dataset import DatasetManager
from research_platform.data.pit import PointInTimeDataManager
from research_platform.kernel import ResearchKernel
from research_platform.workspace.workspace import ResearchWorkspace


@pytest.fixture
def temp_dir():
    dirpath = tempfile.mkdtemp()
    yield Path(dirpath)
    shutil.rmtree(dirpath)


def test_research_kernel_di():
    """Verify ResearchKernel boots DI containers and core managers correctly."""
    kernel = ResearchKernel({"app.log.level": "DEBUG"})
    kernel.boot()
    assert kernel.container is not None
    assert kernel.event_bus is not None
    assert kernel.config is not None
    kernel.shutdown()


def test_research_workspace(temp_dir):
    """Verify workspace creates directory layouts and persists metadata."""
    workspace = ResearchWorkspace(temp_dir)
    meta = workspace.initialize_workspace(
        name="Arbitrage Research",
        description="Exploring cross-venue arbitrage strategies",
        authors=["Alice", "Bob"]
    )

    assert meta.name == "Arbitrage Research"
    assert len(meta.authors) == 2
    assert (temp_dir / "datasets").exists()
    assert (temp_dir / "strategies").exists()
    assert (temp_dir / "project.json").exists()

    # Load back
    loaded = workspace.load_metadata()
    assert loaded.name == "Arbitrage Research"
    assert loaded.description == "Exploring cross-venue arbitrage strategies"

    # Register strategy
    workspace.register_strategy(
        strategy_id="strat_v1",
        code_path="dummy_path.py",
        parameters={"alpha": 0.5, "lookback": 20}
    )

    meta_updated = workspace.load_metadata()
    assert "strat_v1" in meta_updated.strategies
    assert meta_updated.strategies["strat_v1"]["parameters"]["lookback"] == 20


def test_dataset_manager_ohlcv_csv(temp_dir):
    """Verify DatasetManager loads/saves OHLCV datasets and performs timeframe resamplings."""
    mgr = DatasetManager(temp_dir)
    now = datetime.now(timezone.utc)

    bars = [
        OHLCV(symbol="BTC/USDT", timestamp=now, open=100.0, high=105.0, low=95.0, close=102.0, volume=10.0, interval="1m"),
        OHLCV(symbol="BTC/USDT", timestamp=now, open=102.0, high=108.0, low=101.0, close=107.0, volume=15.0, interval="1m"),
    ]

    filepath = mgr.save_ohlcv_csv("btc_test.csv", bars)
    assert filepath.exists()

    loaded = mgr.load_ohlcv_csv("btc_test.csv")
    assert len(loaded) == 2
    assert loaded[0].symbol == "BTC/USDT"
    assert loaded[1].close == 107.0


def test_dataset_manager_resample(temp_dir):
    """Verify resampling 1m bars to 5m timeframe."""
    mgr = DatasetManager(temp_dir)
    
    # Create 5 contiguous minutes
    times = pd.date_range("2026-06-25 12:00:00", periods=5, freq="1min")
    data = []
    for i, t in enumerate(times):
        data.append({
            "timestamp": t,
            "open": 100.0 + i,
            "high": 105.0 + i,
            "low": 95.0 + i,
            "close": 101.0 + i,
            "volume": 10.0,
            "symbol": "BTC/USDT",
            "interval": "1m"
        })
    df_1m = pd.DataFrame(data)

    resampled = mgr.resample_ohlcv(df_1m, "5min")
    assert len(resampled) == 1
    assert resampled.loc[0, "open"] == 100.0   # first open
    assert resampled.loc[0, "high"] == 109.0   # max high is 105 + 4
    assert resampled.loc[0, "low"] == 95.0     # min low is 95 + 0
    assert resampled.loc[0, "close"] == 105.0  # last close is 101 + 4
    assert resampled.loc[0, "volume"] == 50.0  # sum volume is 10 * 5


def test_dataset_manager_aggregate_trades(temp_dir):
    """Verify trades aggregation to 1-minute bars."""
    mgr = DatasetManager(temp_dir)
    now = datetime(2026, 6, 25, 12, 0, 30, tzinfo=timezone.utc)

    trades = [
        Trade(symbol="BTC/USDT", timestamp=now, price=100.0, amount=2.0, side="buy", trade_id="t1"),
        Trade(symbol="BTC/USDT", timestamp=now, price=105.0, amount=3.0, side="buy", trade_id="t2"),
    ]

    df = mgr.aggregate_trades_to_ohlcv(trades, "1min")
    assert len(df) == 1
    assert df.loc[0, "open"] == 100.0
    assert df.loc[0, "high"] == 105.0
    assert df.loc[0, "low"] == 100.0
    assert df.loc[0, "close"] == 105.0
    assert df.loc[0, "volume"] == 5.0


def test_point_in_time_alignment():
    """Verify point-in-time merge avoids lookahead bias."""
    # Market data observations
    obs_df = pd.DataFrame([
        {"timestamp": "2026-06-25 12:00:00", "symbol": "BTC/USDT", "price": 95000.0},
        {"timestamp": "2026-06-25 12:01:00", "symbol": "BTC/USDT", "price": 95200.0},
        {"timestamp": "2026-06-25 12:02:00", "symbol": "BTC/USDT", "price": 95400.0},
    ])

    # Features calculated and made available (as_of)
    # The feature was effective at 11:59:00, but only calculated and available as of 12:00:30
    features_df = pd.DataFrame([
        {
            "effective_time": "2026-06-25 11:59:00",
            "as_of": "2026-06-25 12:00:30",
            "symbol": "BTC/USDT",
            "alpha_score": 0.8
        }
    ])

    aligned = PointInTimeDataManager.align_features(obs_df, features_df, on_key="symbol")

    # For 12:00:00 observation: feature as_of is 12:00:30, which is FUTURE. Should be NaN.
    assert pd.isna(aligned.loc[0, "alpha_score"])

    # For 12:01:00 observation: feature as_of 12:00:30 is in the past. Should align 0.8.
    assert aligned.loc[1, "alpha_score"] == 0.8

    # For 12:02:00 observation: should remain 0.8
    assert aligned.loc[2, "alpha_score"] == 0.8
