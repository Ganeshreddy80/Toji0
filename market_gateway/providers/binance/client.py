"""Binance Gateway Provider subclassing BinanceExchangeProvider for backward compatibility."""

from __future__ import annotations

from market_gateway.providers.binance.exchange import BinanceExchangeProvider


class BinanceGatewayProvider(BinanceExchangeProvider):
    """Reference adapter class to preserve existing public interface."""
    pass
