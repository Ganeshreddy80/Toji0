"""Immutable Pydantic V2 market data models for Sprint 9B."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Tuple
from pydantic import BaseModel, ConfigDict, Field


class MarketTick(BaseModel):
    """Immutable market price/volume tick."""

    symbol: str = Field(..., description="Target asset trading pair symbol.")
    price: float = Field(..., gt=0.0, description="Executed tick trade price.")
    volume: float = Field(..., ge=0.0, description="Executed tick trade volume.")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Tick creation timestamp.",
    )

    model_config = ConfigDict(frozen=True)


class MarketCandle(BaseModel):
    """Immutable OHLCV market bar candle."""

    symbol: str = Field(..., description="Target asset trading pair symbol.")
    timeframe: str = Field(..., description="Candle timeframe interval (e.g., '1m', '5m', '15m', '1h').")
    open: float = Field(..., gt=0.0, description="Bar open price.")
    high: float = Field(..., gt=0.0, description="Bar high price.")
    low: float = Field(..., gt=0.0, description="Bar low price.")
    close: float = Field(..., gt=0.0, description="Bar close price.")
    volume: float = Field(..., ge=0.0, description="Cumulative bar volume.")
    open_time: datetime = Field(..., description="Bar interval open timestamp.")
    close_time: datetime = Field(..., description="Bar interval close timestamp.")

    model_config = ConfigDict(frozen=True)


class OrderBookSnapshot(BaseModel):
    """Immutable order book depth snapshot."""

    symbol: str = Field(..., description="Target asset trading pair symbol.")
    bids: List[Tuple[float, float]] = Field(default_factory=list, description="Bid price levels list of (price, size).")
    asks: List[Tuple[float, float]] = Field(default_factory=list, description="Ask price levels list of (price, size).")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Snapshot timestamp.",
    )

    model_config = ConfigDict(frozen=True)


class FeedStatus(BaseModel):
    """Immutable feed status and connection state telemetry."""

    connected: bool = Field(default=False, description="Feed active connection status flag.")
    latency_ms: float = Field(default=0.0, ge=0.0, description="Calculated feed round-trip latency in milliseconds.")
    heartbeat_time: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp of last recorded feed heartbeat.",
    )
    reconnect_count: int = Field(default=0, ge=0, description="Cumulative reconnection attempt counter.")

    model_config = ConfigDict(frozen=True)
