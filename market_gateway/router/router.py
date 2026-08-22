"""Router to direct subscribe and query requests to registered providers."""

from __future__ import annotations

import logging
from typing import Any

from market_gateway.core.interfaces import IMarketGatewayProvider

logger = logging.getLogger(__name__)


class MarketDataRouter:
    """Manages provider routing maps for symbols and data types."""

    def __init__(self) -> None:
        self._providers: dict[str, IMarketGatewayProvider] = {}
        # Mapping rules, e.g. symbol -> provider_name
        self._routing_map: dict[str, str] = {}
        self._default_provider_name: str | None = None

    def register_provider(self, provider: IMarketGatewayProvider) -> None:
        """Register a provider in the router registry."""
        name = provider.name
        self._providers[name] = provider
        if not self._default_provider_name:
            self._default_provider_name = name
        logger.info("Router: Registered provider: %s", name)

    def set_default_provider(self, provider_name: str) -> None:
        if provider_name in self._providers:
            self._default_provider_name = provider_name
            logger.info("Router: Set default provider to %s", provider_name)

    def add_routing_rule(self, symbol: str, provider_name: str) -> None:
        """Explicitly route a specific symbol to a provider."""
        if provider_name in self._providers:
            self._routing_map[symbol] = provider_name
            logger.info("Router: Routed symbol %s to provider %s", symbol, provider_name)

    def get_provider(self, symbol: str) -> IMarketGatewayProvider:
        """Resolve which provider should serve queries for a given symbol."""
        name = self._routing_map.get(symbol) or self._default_provider_name
        if not name or name not in self._providers:
            raise ValueError(f"No provider registered or resolved for symbol: {symbol}")
        return self._providers[name]

    def list_providers(self) -> list[IMarketGatewayProvider]:
        return list(self._providers.values())
