"""Incremental and resumable historical market data downloader."""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from typing import Any

from data.schemas.market_data import OHLCV
from market_gateway.core.interfaces import IMarketGatewayProvider

logger = logging.getLogger(__name__)


class HistoricalDataDownloader:
    """Incremental & resumable downloader for market history."""

    def __init__(
        self,
        provider: IMarketGatewayProvider,
        storage_dir: str = "data/datasets",
        checkpoint_file: str = "data/datasets/download_checkpoints.json",
    ) -> None:
        self.provider = provider
        self.storage_dir = storage_dir
        self.checkpoint_file = checkpoint_file
        self._checkpoints: dict[str, str] = {}
        
        # Ensure directories exist
        os.makedirs(self.storage_dir, exist_ok=True)
        self._load_checkpoints()

    def _load_checkpoints(self) -> None:
        if os.path.exists(self.checkpoint_file):
            try:
                with open(self.checkpoint_file) as f:
                    self._checkpoints = json.load(f)
            except Exception as e:
                logger.error("Failed to load checkpoints file: %s", e)
                self._checkpoints = {}

    def _save_checkpoint(self, key: str, timestamp: datetime) -> None:
        self._checkpoints[key] = timestamp.isoformat()
        try:
            with open(self.checkpoint_file, "w") as f:
                json.dump(self._checkpoints, f, indent=2)
        except Exception as e:
            logger.error("Failed to save checkpoint: %s", e)

    def get_last_timestamp(self, key: str, default_start: datetime) -> datetime:
        """Return the last saved timestamp or the default start time."""
        val = self._checkpoints.get(key)
        if val:
            try:
                return datetime.fromisoformat(val)
            except Exception:
                pass
        return default_start

    def download_candles(
        self,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list[OHLCV]:
        """Incremental download of OHLCV candles, updating checkpoints."""
        checkpoint_key = f"{symbol}_ohlcv_{interval}"
        actual_start = self.get_last_timestamp(checkpoint_key, start_time)

        if actual_start >= end_time:
            logger.info("Candles for %s %s are already up to date.", symbol, interval)
            return []

        logger.info("Downloading historical candles for %s %s starting from %s", symbol, interval, actual_start)
        
        # Ingest from provider
        data = self.provider.get_historical_candles(symbol, interval, actual_start, end_time)
        if not data:
            return []

        # Store to dataset file
        file_path = os.path.join(self.storage_dir, f"{symbol}_ohlcv_{interval}.json")
        self._append_to_file(file_path, [bar.model_dump() for bar in data])

        # Update checkpoint to the last bar timestamp
        last_bar_time = max(bar.timestamp for bar in data)
        self._save_checkpoint(checkpoint_key, last_bar_time)

        return data

    def download_alternative_data(
        self,
        symbol: str,
        data_type: str,  # "funding", "open_interest", "liquidations", "news", "macro"
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Incremental sync for alternative market indicators."""
        checkpoint_key = f"{symbol}_{data_type}"
        actual_start = self.get_last_timestamp(checkpoint_key, start_time)

        if actual_start >= end_time:
            logger.info("%s data for %s is already up to date.", data_type, symbol)
            return []

        # Mock download alternative data from provider or client
        logger.info("Downloading alternative %s data for %s starting from %s", data_type, symbol, actual_start)
        
        # Simulate download response points
        simulated_data = [
            {
                "symbol": symbol,
                "data_type": data_type,
                "timestamp": end_time.isoformat(),
                "value": 100.0 if data_type != "funding" else 0.0001,
            }
        ]

        file_path = os.path.join(self.storage_dir, f"{symbol}_{data_type}.json")
        self._append_to_file(file_path, simulated_data)
        self._save_checkpoint(checkpoint_key, end_time)

        return simulated_data

    def _append_to_file(self, file_path: str, new_rows: list[dict[str, Any]]) -> None:
        existing = []
        if os.path.exists(file_path):
            try:
                with open(file_path) as f:
                    existing = json.load(f)
            except Exception:
                existing = []
        
        # Merge rows based on uniqueness
        # Uniqueness key: timestamp + symbol
        seen = set()
        merged = []
        for r in existing + new_rows:
            # handle datetime/string conversions safely
            ts = r.get("timestamp")
            if isinstance(ts, datetime):
                ts = ts.isoformat()
            uid = (r.get("symbol", ""), ts)
            if uid not in seen:
                seen.add(uid)
                merged.append(r)

        # Sort by timestamp
        merged.sort(key=lambda x: x.get("timestamp", ""))

        try:
            with open(file_path, "w") as f:
                json.dump(merged, f, indent=2)
        except Exception as e:
            logger.error("Failed to write dataset file: %s", e)
