"""Unit tests for the Historical Data Downloader."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime, timedelta

from market_gateway.historical.downloader import HistoricalDataDownloader
from market_gateway.providers.binance.client import BinanceGatewayProvider


def test_historical_downloader_checkpoints(tmp_path):
    async def _run():
        provider = BinanceGatewayProvider(use_mock=True)
        provider.initialize()

        storage_dir = str(tmp_path / "datasets")
        checkpoint_file = str(tmp_path / "download_checkpoints.json")

        downloader = HistoricalDataDownloader(
            provider=provider,
            storage_dir=storage_dir,
            checkpoint_file=checkpoint_file,
        )

        end_time = datetime.now(UTC)
        start_time = end_time - timedelta(minutes=5)

        # Initial download
        data = downloader.download_candles("BTCUSDT", "1m", start_time, end_time)
        assert len(data) > 0

        # Verify checkpoint is written
        assert os.path.exists(checkpoint_file)
        with open(checkpoint_file) as f:
            checkpoints = json.load(f)
        assert "BTCUSDT_ohlcv_1m" in checkpoints

        # Load checkpointed time
        last_ts = datetime.fromisoformat(checkpoints["BTCUSDT_ohlcv_1m"])

        # Download again, should pick up from the checkpoint and see no new candles (since start = last_ts)
        new_data = downloader.download_candles("BTCUSDT", "1m", start_time, last_ts)
        assert len(new_data) == 0

        # Download alternative data
        alt_data = downloader.download_alternative_data("BTCUSDT", "funding", start_time, end_time)
        assert len(alt_data) == 1

        provider.shutdown()
        await asyncio.sleep(0.01)

    asyncio.run(_run())
