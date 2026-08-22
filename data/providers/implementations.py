"""Concrete placeholder implementations for all target data providers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Callable

from data.providers.base import BaseProvider
from data.providers.interfaces import IAlternativeDataProvider, IMarketDataProvider
from data.schemas.market_data import (
    OHLCV,
    EconomicEvent,
    NewsEvent,
    Trade,
)


# ── Market Data Providers ──────────────────────────────────────────────────


class BinanceProvider(BaseProvider, IMarketDataProvider):
    """Binance Spot/Futures market data provider."""

    @property
    def name(self) -> str:
        return "Binance"

    def subscribe_trades(self, symbol: str, callback: Callable[[Trade], None]) -> None:
        pass

    def subscribe_ohlcv(
        self, symbol: str, interval: str, callback: Callable[[OHLCV], None]
    ) -> None:
        pass

    def get_historical_ohlcv(
        self, symbol: str, interval: str, start: datetime, end: datetime
    ) -> list[OHLCV]:
        # Return mock OHLCV
        return [
            OHLCV(
                symbol=symbol,
                timestamp=start,
                open=95000.0,
                high=95500.0,
                low=94800.0,
                close=95200.0,
                volume=10.0,
                interval=interval,
            )
        ]


class BybitProvider(BaseProvider, IMarketDataProvider):
    """Bybit perpetuals market data provider."""

    @property
    def name(self) -> str:
        return "Bybit"

    def subscribe_trades(self, symbol: str, callback: Callable[[Trade], None]) -> None:
        pass

    def subscribe_ohlcv(
        self, symbol: str, interval: str, callback: Callable[[OHLCV], None]
    ) -> None:
        pass

    def get_historical_ohlcv(
        self, symbol: str, interval: str, start: datetime, end: datetime
    ) -> list[OHLCV]:
        return []


class CoinbaseProvider(BaseProvider, IMarketDataProvider):
    """Coinbase Exchange fiat/crypto market data provider."""

    @property
    def name(self) -> str:
        return "Coinbase"

    def subscribe_trades(self, symbol: str, callback: Callable[[Trade], None]) -> None:
        pass

    def subscribe_ohlcv(
        self, symbol: str, interval: str, callback: Callable[[OHLCV], None]
    ) -> None:
        pass

    def get_historical_ohlcv(
        self, symbol: str, interval: str, start: datetime, end: datetime
    ) -> list[OHLCV]:
        return []


class HyperliquidProvider(BaseProvider, IMarketDataProvider):
    """Hyperliquid DEX perpetuals market data provider."""

    @property
    def name(self) -> str:
        return "Hyperliquid"

    def subscribe_trades(self, symbol: str, callback: Callable[[Trade], None]) -> None:
        pass

    def subscribe_ohlcv(
        self, symbol: str, interval: str, callback: Callable[[OHLCV], None]
    ) -> None:
        pass

    def get_historical_ohlcv(
        self, symbol: str, interval: str, start: datetime, end: datetime
    ) -> list[OHLCV]:
        return []


class TradingViewProvider(BaseProvider, IMarketDataProvider):
    """TradingView charting and indicator provider."""

    @property
    def name(self) -> str:
        return "TradingView"

    def subscribe_trades(self, symbol: str, callback: Callable[[Trade], None]) -> None:
        pass

    def subscribe_ohlcv(
        self, symbol: str, interval: str, callback: Callable[[OHLCV], None]
    ) -> None:
        pass

    def get_historical_ohlcv(
        self, symbol: str, interval: str, start: datetime, end: datetime
    ) -> list[OHLCV]:
        return []


# ── Alternative Data Providers ─────────────────────────────────────────────


class CoinGlassProvider(BaseProvider, IAlternativeDataProvider):
    """CoinGlass liquidation, funding, and open interest statistics provider."""

    @property
    def name(self) -> str:
        return "CoinGlass"

    def get_latest_news(self, symbol: str | None = None) -> list[NewsEvent]:
        return []

    def get_economic_calendar(
        self, start: datetime, end: datetime
    ) -> list[EconomicEvent]:
        return []


class NewsProvider(BaseProvider, IAlternativeDataProvider):
    """General news headlines and market news provider."""

    @property
    def name(self) -> str:
        return "News"

    def get_latest_news(self, symbol: str | None = None) -> list[NewsEvent]:
        symbols = [symbol] if symbol else ["GLOBAL"]
        return [
            NewsEvent(
                title="Market update",
                content="Bitcoin consolidates near highs",
                source="Toji Analytics",
                timestamp=datetime.now(UTC),
                sentiment=0.5,
                associated_symbols=symbols,
            )
        ]

    def get_economic_calendar(
        self, start: datetime, end: datetime
    ) -> list[EconomicEvent]:
        return []


class FearAndGreedProvider(BaseProvider, IAlternativeDataProvider):
    """Fear and Greed sentiment index provider."""

    @property
    def name(self) -> str:
        return "Fear & Greed"

    def get_latest_news(self, symbol: str | None = None) -> list[NewsEvent]:
        return []

    def get_economic_calendar(
        self, start: datetime, end: datetime
    ) -> list[EconomicEvent]:
        return []


class EconomicCalendarProvider(BaseProvider, IAlternativeDataProvider):
    """Macroeconomic calendar and indicators provider."""

    @property
    def name(self) -> str:
        return "Economic Calendar"

    def get_latest_news(self, symbol: str | None = None) -> list[NewsEvent]:
        return []

    def get_economic_calendar(
        self, start: datetime, end: datetime
    ) -> list[EconomicEvent]:
        return [
            EconomicEvent(
                event_name="US CPI YoY",
                country="US",
                actual=3.1,
                forecast=3.0,
                previous=3.2,
                timestamp=start,
                importance="high",
            )
        ]


class OnChainProvider(BaseProvider, IAlternativeDataProvider):
    """Blockchain-native on-chain metrics provider."""

    @property
    def name(self) -> str:
        return "On-chain"

    def get_latest_news(self, symbol: str | None = None) -> list[NewsEvent]:
        return []

    def get_economic_calendar(
        self, start: datetime, end: datetime
    ) -> list[EconomicEvent]:
        return []


class WhaleAlertsProvider(BaseProvider, IAlternativeDataProvider):
    """Large transaction whale alerts monitor provider."""

    @property
    def name(self) -> str:
        return "Whale Alerts"

    def get_latest_news(self, symbol: str | None = None) -> list[NewsEvent]:
        return []

    def get_economic_calendar(
        self, start: datetime, end: datetime
    ) -> list[EconomicEvent]:
        return []
