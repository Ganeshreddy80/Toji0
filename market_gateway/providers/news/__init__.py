"""News provider placeholder."""

from __future__ import annotations

from market_gateway.providers.base import BaseGatewayProvider


class NewsGatewayProvider(BaseGatewayProvider):
    """News headlines placeholder provider."""

    def __init__(self) -> None:
        super().__init__()
        self._name = "News"
