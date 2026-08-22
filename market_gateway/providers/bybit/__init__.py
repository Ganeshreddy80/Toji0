"""Bybit provider placeholder."""

from __future__ import annotations

from market_gateway.providers.base import BaseGatewayProvider


class BybitGatewayProvider(BaseGatewayProvider):
    """Bybit perpetuals placeholder provider."""

    def __init__(self) -> None:
        super().__init__()
        self._name = "Bybit"
