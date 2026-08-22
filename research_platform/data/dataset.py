"""DatasetManager module for managing historical trading data and timeframe resamplings.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import pandas as pd
from data.schemas.market_data import OHLCV, Trade


class DatasetManager:
    """Manages loading, validation, resampling, and persistence of historical market data."""

    def __init__(self, data_root: str | Path) -> None:
        self.root = Path(data_root)
        self.root.mkdir(parents=True, exist_ok=True)

    def save_ohlcv_csv(self, filename: str, data: List[OHLCV]) -> Path:
        """Persist a list of OHLCV objects to CSV."""
        filepath = self.root / filename
        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["symbol", "timestamp", "open", "high", "low", "close", "volume", "interval"])
            for row in data:
                writer.writerow([
                    row.symbol,
                    row.timestamp.isoformat(),
                    row.open,
                    row.high,
                    row.low,
                    row.close,
                    row.volume,
                    row.interval
                ])
        return filepath

    def load_ohlcv_csv(self, filename: str) -> List[OHLCV]:
        """Load a CSV file into a list of OHLCV objects."""
        filepath = self.root / filename
        if not filepath.exists():
            raise FileNotFoundError(f"Dataset file not found: {filepath}")

        ohlcv_list = []
        with open(filepath, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ohlcv_list.append(
                    OHLCV(
                        symbol=row["symbol"],
                        timestamp=datetime.fromisoformat(row["timestamp"]),
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        volume=float(row["volume"]),
                        interval=row["interval"]
                    )
                )
        return ohlcv_list

    def resample_ohlcv(self, df_1m: pd.DataFrame, target_interval: str) -> pd.DataFrame:
        """Resample a 1-minute OHLCV DataFrame into a higher resolution timeframe.

        df_1m must have a DateTimeIndex or a 'timestamp' column.
        target_interval is a pandas offset alias (e.g. '5min', '1H', '1D').
        """
        df = df_1m.copy()
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df.set_index("timestamp", inplace=True)
        
        # Aggregate columns
        resampled = df.resample(target_interval).agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
            "symbol": "first"
        }).dropna()
        
        resampled["interval"] = target_interval
        return resampled.reset_index()

    def aggregate_trades_to_ohlcv(self, trades: List[Trade], interval: str = "1min") -> pd.DataFrame:
        """Aggregate raw individual trades into OHLCV bars."""
        if not trades:
            return pd.DataFrame()

        data = []
        for t in trades:
            data.append({
                "timestamp": pd.to_datetime(t.timestamp),
                "price": t.price,
                "volume": t.amount,
                "symbol": t.symbol
            })

        df = pd.DataFrame(data)
        df.set_index("timestamp", inplace=True)

        resampled = df.resample(interval).agg({
            "price": ["first", "max", "min", "last"],
            "volume": "sum",
            "symbol": "first"
        }).dropna()

        resampled.columns = ["open", "high", "low", "close", "volume", "symbol"]
        resampled["interval"] = interval
        return resampled.reset_index()
