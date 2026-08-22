"""Unit tests for market data Pydantic schemas."""

from __future__ import annotations

from datetime import UTC, datetime
import pytest
from pydantic import ValidationError

from data.schemas.market_data import (
    OHLCV,
    AssetMetadata,
    EconomicEvent,
    FundingRate,
    Liquidation,
    MarketRegime,
    NewsEvent,
    OpenInterest,
    OrderBookSnapshot,
    Trade,
)
from toji_platform.core.types import AssetClass


def test_ohlcv_validation_success():
    ohlcv = OHLCV(
        symbol="BTC/USDT",
        timestamp=datetime.now(UTC),
        open=95000.0,
        high=95500.0,
        low=94800.0,
        close=95200.0,
        volume=12.5,
        interval="1m",
    )
    assert ohlcv.open == 95000.0
    assert ohlcv.volume == 12.5


def test_ohlcv_validation_fail_bounds():
    with pytest.raises(ValidationError):
        OHLCV(
            symbol="BTC/USDT",
            timestamp=datetime.now(UTC),
            open=-500.0,  # invalid price
            high=95500.0,
            low=94800.0,
            close=95200.0,
            volume=12.5,
            interval="1m",
        )


def test_trade_validation():
    trade = Trade(
        symbol="ETH/USDT",
        timestamp=datetime.now(UTC),
        price=3500.0,
        amount=1.5,
        side="buy",
        trade_id="tx_123",
    )
    assert trade.side == "buy"

    # Invalid side
    with pytest.raises(ValidationError):
        Trade(
            symbol="ETH/USDT",
            timestamp=datetime.now(UTC),
            price=3500.0,
            amount=1.5,
            side="hold",  # invalid
            trade_id="tx_123",
        )


def test_order_book_snapshot():
    ob = OrderBookSnapshot(
        symbol="BTC/USDT",
        timestamp=datetime.now(UTC),
        bids=[(95000.0, 0.5), (94990.0, 1.2)],
        asks=[(95010.0, 0.8), (95020.0, 2.5)],
    )
    assert len(ob.bids) == 2
    assert ob.asks[0][0] == 95010.0


def test_news_event():
    news = NewsEvent(
        title="Fed decision",
        content="Rates remain unchanged",
        source="Reuters",
        timestamp=datetime.now(UTC),
        sentiment=-0.1,
    )
    assert news.source == "Reuters"
    assert news.sentiment == -0.1


def test_economic_event():
    evt = EconomicEvent(
        event_name="US CPI",
        country="US",
        actual=3.1,
        forecast=3.0,
        timestamp=datetime.now(UTC),
        importance="high",
    )
    assert evt.importance == "high"


def test_asset_metadata():
    meta = AssetMetadata(
        symbol="BTC/USDT",
        asset_class=AssetClass.CRYPTO,
        base_asset="BTC",
        quote_asset="USDT",
    )
    assert meta.asset_class == AssetClass.CRYPTO
