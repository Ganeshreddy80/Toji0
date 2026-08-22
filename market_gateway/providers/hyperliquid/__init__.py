"""Hyperliquid provider placeholder."""

from __future__ import annotations

from market_gateway.providers.base import BaseGatewayProvider


class HyperliquidGatewayProvider(BaseGatewayProvider):
    """Hyperliquid DEX perpetuals placeholder provider."""

    def __init__(self) -> None:
        super().__init__()
        self._name = "Hyperliquid"
