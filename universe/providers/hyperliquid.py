"""Hyperliquid discovery provider — placeholder for future implementation."""

from __future__ import annotations

from universe.providers.base import BaseDiscoveryProvider


class HyperliquidDiscoveryProvider(BaseDiscoveryProvider):
    """Discover assets from Hyperliquid exchange via Market Gateway.

    This is a placeholder implementation that uses the base class logic.
    Once the Hyperliquid Market Gateway provider is fully implemented,
    override _parse_exchange_info with Hyperliquid-specific response parsing.
    """
