"""Coinbase provider placeholder."""

from __future__ import annotations

from market_gateway.providers.base import BaseGatewayProvider


class CoinbaseGatewayProvider(BaseGatewayProvider):
    """Coinbase Exchange placeholder provider."""

    def __init__(self) -> None:
        super().__init__()
        self._name = "Coinbase"
