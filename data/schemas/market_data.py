"""Canonical Pydantic models for market and alternative data schemas."""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field

from toji_platform.core.types import AssetClass


class OHLCV(BaseModel):
    """Open, High, Low, Close, Volume bar schema."""

    symbol: str = Field(..., description="Canonical ticker symbol (e.g. BTC/USDT, AAPL)")
    timestamp: datetime = Field(..., description="Bar start time (UTC)")
    open: float = Field(..., gt=0.0, description="Open price")
    high: float = Field(..., gt=0.0, description="Highest price during interval")
    low: float = Field(..., gt=0.0, description="Lowest price during interval")
    close: float = Field(..., gt=0.0, description="Close price")
    volume: float = Field(..., ge=0.0, description="Total traded volume in base asset")
    interval: str = Field(..., description="Bar timeframe/interval (e.g. 1m, 5m, 1h, 1d)")

    model_config = {
        "frozen": True,
        "json_schema_extra": {
            "example": {
                "symbol": "BTC/USDT",
                "timestamp": "2026-06-25T12:00:00Z",
                "open": 95000.0,
                "high": 95500.0,
                "low": 94800.0,
                "close": 95200.0,
                "volume": 12.54,
                "interval": "1m",
            }
        },
    }


class Trade(BaseModel):
    """Individual trade execution execution schema."""

    symbol: str = Field(...)
    timestamp: datetime = Field(...)
    price: float = Field(..., gt=0.0)
    amount: float = Field(..., gt=0.0)
    side: str = Field(..., pattern="^(buy|sell)$", description="Trade side: 'buy' or 'sell'")
    trade_id: str = Field(...)

    model_config = {"frozen": True}


class OrderBookSnapshot(BaseModel):
    """L2 Order Book Snapshot schema."""

    symbol: str = Field(...)
    timestamp: datetime = Field(...)
    bids: list[tuple[float, float]] = Field(
        ..., description="List of [price, depth_amount] bids sorted high to low"
    )
    asks: list[tuple[float, float]] = Field(
        ..., description="List of [price, depth_amount] asks sorted low to high"
    )
    sequence_number: int | None = Field(default=None, description="Monotonically increasing update id")

    model_config = {"frozen": True}


class FundingRate(BaseModel):
    """Funding Rate schema for perpetual contracts."""

    symbol: str = Field(...)
    timestamp: datetime = Field(...)
    rate: float = Field(..., description="Funding rate fraction (e.g. 0.0001 for 0.01%)")
    next_funding_time: datetime | None = Field(default=None)

    model_config = {"frozen": True}


class OpenInterest(BaseModel):
    """Open Interest schema for derivative markets."""

    symbol: str = Field(...)
    timestamp: datetime = Field(...)
    amount: float = Field(..., ge=0.0, description="Open interest contract quantity")
    value_usd: float | None = Field(default=None, ge=0.0, description="Notional USD value of open interest")

    model_config = {"frozen": True}


class Liquidation(BaseModel):
    """Market liquidation execution schema."""

    symbol: str = Field(...)
    timestamp: datetime = Field(...)
    price: float = Field(..., gt=0.0)
    amount: float = Field(..., gt=0.0)
    side: str = Field(..., pattern="^(buy|sell)$", description="Liquidation order side")
    liquidation_id: str | None = Field(default=None)

    model_config = {"frozen": True}


class NewsEvent(BaseModel):
    """Alternative news and sentiment schema."""

    title: str = Field(...)
    content: str = Field(...)
    source: str = Field(..., description="Publishing platform/agency")
    timestamp: datetime = Field(...)
    sentiment: float | None = Field(default=None, ge=-1.0, le=1.0, description="Normalized sentiment score")
    url: str | None = Field(default=None)
    associated_symbols: list[str] = Field(default_factory=list)

    model_config = {"frozen": True}


class EconomicEvent(BaseModel):
    """Macroeconomic calendar event schema."""

    event_name: str = Field(..., description="Name of report/event (e.g. CPI, Non-farm payroll)")
    country: str = Field(..., description="ISO 2-character country code (e.g. US, EU)")
    actual: float | None = Field(default=None)
    forecast: float | None = Field(default=None)
    previous: float | None = Field(default=None)
    timestamp: datetime = Field(...)
    importance: str = Field(..., pattern="^(low|medium|high)$", description="Impact grading")

    model_config = {"frozen": True}


class MarketRegime(BaseModel):
    """Derived market regime metadata schema."""

    regime_name: str = Field(..., description="Structural classification (e.g. bullish, ranging)")
    volatility_level: str = Field(..., pattern="^(low|medium|high)$")
    timestamp: datetime = Field(...)
    symbol: str | None = Field(default=None, description="Optional symbol if asset-specific")
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    model_config = {"frozen": True}


class AssetMetadata(BaseModel):
    """Asset properties and configurations schema."""

    symbol: str = Field(..., description="Canonical asset identifier")
    asset_class: AssetClass = Field(...)
    base_asset: str = Field(...)
    quote_asset: str = Field(...)
    tick_size: float | None = Field(default=None, gt=0.0)
    lot_size: float | None = Field(default=None, gt=0.0)
    exchange: str | None = Field(default=None)

    model_config = {"frozen": True}
