"""Normalizer for mapping raw provider messages into canonical Toji Pydantic schemas."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from data.schemas.market_data import (
    OHLCV,
    EconomicEvent,
    FundingRate,
    Liquidation,
    NewsEvent,
    OpenInterest,
    OrderBookSnapshot,
    Trade,
)

logger = logging.getLogger(__name__)


class MarketDataNormalizer:
    """Normalizes raw market payloads from various exchanges/sources into canonical formats."""

    @staticmethod
    def normalize_binance_candle(raw: dict[str, Any] | list[Any], symbol: str = "", interval: str = "") -> OHLCV:
        """Normalize Binance kline data from WebSocket or REST API."""
        if isinstance(raw, list):
            # REST kline response format:
            # [open_time, open, high, low, close, volume, close_time, ...]
            return OHLCV(
                symbol=symbol,
                timestamp=datetime.fromtimestamp(raw[0] / 1000.0, tz=UTC),
                open=float(raw[1]),
                high=float(raw[2]),
                low=float(raw[3]),
                close=float(raw[4]),
                volume=float(raw[5]),
                interval=interval,
            )
        elif isinstance(raw, dict):
            # WebSocket kline event format
            k = raw["k"]
            return OHLCV(
                symbol=raw.get("s", symbol),
                timestamp=datetime.fromtimestamp(k["t"] / 1000.0, tz=UTC),
                open=float(k["o"]),
                high=float(k["h"]),
                low=float(k["l"]),
                close=float(k["c"]),
                volume=float(k["v"]),
                interval=k.get("i", interval),
            )
        raise ValueError(f"Unknown Binance candle structure: {raw}")

    @staticmethod
    def normalize_binance_trade(raw: dict[str, Any], symbol: str = "") -> Trade:
        """Normalize Binance trade event from WebSocket."""
        # WebSocket trade format:
        # { "e": "trade", "E": 123, "s": "BTCUSDT", "t": 12345, "p": "0.001", "q": "100", "T": 12345, "m": true }
        # Note: 'm' means buyer is maker -> indicates a sell order executed against a buy maker order
        side = "sell" if raw.get("m") else "buy"
        return Trade(
            symbol=raw.get("s", symbol),
            timestamp=datetime.fromtimestamp(raw["T"] / 1000.0, tz=UTC),
            price=float(raw["p"]),
            amount=float(raw["q"]),
            side=side,
            trade_id=str(raw["t"]),
        )

    @staticmethod
    def normalize_binance_order_book(raw: dict[str, Any], symbol: str = "") -> OrderBookSnapshot:
        """Normalize Binance L2 depth snapshot or update."""
        # raw: { "lastUpdateId": 123, "bids": [[price, qty]], "asks": [[price, qty]] }
        # WebSocket depthUpdate has "u" for sequence, "b" for bids, "a" for asks
        seq = raw.get("lastUpdateId") or raw.get("u")
        bids = [(float(b[0]), float(b[1])) for b in raw.get("bids", raw.get("b", []))]
        asks = [(float(a[0]), float(a[1])) for a in raw.get("asks", raw.get("a", []))]
        return OrderBookSnapshot(
            symbol=raw.get("s", symbol),
            timestamp=datetime.fromtimestamp(raw.get("E", datetime.now(UTC).timestamp() * 1000) / 1000.0, tz=UTC),
            bids=bids,
            asks=asks,
            sequence_number=seq,
        )

    @staticmethod
    def normalize_tradingview_alert(raw: dict[str, Any]) -> OHLCV | NewsEvent | EconomicEvent:
        """Normalize TradingView alert payloads into canonical schemas."""
        # Supported format 1: Simple OHLCV alert
        if "close" in raw or "price" in raw:
            symbol = raw.get("symbol", "TV_ALERT")
            # If standard OHLCV fields are missing, populate defaults
            return OHLCV(
                symbol=symbol,
                timestamp=datetime.now(UTC),
                open=float(raw.get("open") or raw.get("price") or 1.0),
                high=float(raw.get("high") or raw.get("price") or 1.0),
                low=float(raw.get("low") or raw.get("price") or 1.0),
                close=float(raw.get("close") or raw.get("price") or 1.0),
                volume=float(raw.get("volume", 0.0)),
                interval=str(raw.get("interval", "1m")),
            )
        
        # Supported format 2: Alternative News/Sentiment Alert
        if "news" in raw or "message" in raw:
            content = raw.get("news") or raw.get("message", "")
            return NewsEvent(
                title=raw.get("title", "TradingView Alert"),
                content=content,
                source="TradingView Webhook",
                timestamp=datetime.now(UTC),
                sentiment=float(raw.get("sentiment", 0.0)),
                url=raw.get("url"),
                associated_symbols=raw.get("associated_symbols") or [raw.get("symbol", "TV_ALERT")],
            )

        # Fallback to general news event
        return NewsEvent(
            title="TradingView Webhook Trigger",
            content=str(raw),
            source="TradingView Webhook",
            timestamp=datetime.now(UTC),
            sentiment=0.0,
            associated_symbols=[raw.get("symbol", "GLOBAL")],
        )

    @staticmethod
    def normalize_bybit_candle(raw: dict[str, Any], symbol: str = "", interval: str = "") -> OHLCV:
        """Placeholder for Bybit candle normalizer."""
        return OHLCV(
            symbol=symbol,
            timestamp=datetime.now(UTC),
            open=float(raw.get("open", 1.0)),
            high=float(raw.get("high", 1.0)),
            low=float(raw.get("low", 1.0)),
            close=float(raw.get("close", 1.0)),
            volume=float(raw.get("volume", 0.0)),
            interval=interval,
        )

    @staticmethod
    def normalize_coinbase_candle(raw: dict[str, Any], symbol: str = "", interval: str = "") -> OHLCV:
        """Placeholder for Coinbase candle normalizer."""
        return OHLCV(
            symbol=symbol,
            timestamp=datetime.now(UTC),
            open=float(raw.get("open", 1.0)),
            high=float(raw.get("high", 1.0)),
            low=float(raw.get("low", 1.0)),
            close=float(raw.get("close", 1.0)),
            volume=float(raw.get("volume", 0.0)),
            interval=interval,
        )

    @staticmethod
    def normalize_hyperliquid_candle(raw: dict[str, Any], symbol: str = "", interval: str = "") -> OHLCV:
        """Placeholder for Hyperliquid candle normalizer."""
        return OHLCV(
            symbol=symbol,
            timestamp=datetime.now(UTC),
            open=float(raw.get("open", 1.0)),
            high=float(raw.get("high", 1.0)),
            low=float(raw.get("low", 1.0)),
            close=float(raw.get("close", 1.0)),
            volume=float(raw.get("volume", 0.0)),
            interval=interval,
        )
