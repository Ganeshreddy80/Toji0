"""Data Provider framework and interfaces for Toji."""

from data.providers.base import BaseProvider
from data.providers.implementations import (
    BinanceProvider,
    BybitProvider,
    CoinbaseProvider,
    CoinGlassProvider,
    EconomicCalendarProvider,
    FearAndGreedProvider,
    HyperliquidProvider,
    NewsProvider,
    OnChainProvider,
    TradingViewProvider,
    WhaleAlertsProvider,
)
from data.providers.interfaces import (
    IAlternativeDataProvider,
    IMarketDataProvider,
    IProvider,
)

__all__ = [
    "IProvider",
    "IMarketDataProvider",
    "IAlternativeDataProvider",
    "BaseProvider",
    "BinanceProvider",
    "BybitProvider",
    "CoinbaseProvider",
    "HyperliquidProvider",
    "TradingViewProvider",
    "CoinGlassProvider",
    "NewsProvider",
    "FearAndGreedProvider",
    "EconomicCalendarProvider",
    "OnChainProvider",
    "WhaleAlertsProvider",
]
