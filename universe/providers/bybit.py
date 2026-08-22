"""Bybit discovery provider — placeholder for future implementation."""

from __future__ import annotations

from universe.providers.base import BaseDiscoveryProvider


class BybitDiscoveryProvider(BaseDiscoveryProvider):
    """Discover assets from Bybit exchange via Market Gateway.

    This is a placeholder implementation that uses the base class logic.
    Once the Bybit Market Gateway provider is fully implemented,
    override _parse_exchange_info with Bybit-specific response parsing.
    """
