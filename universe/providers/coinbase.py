"""Coinbase discovery provider — placeholder for future implementation."""

from __future__ import annotations

from universe.providers.base import BaseDiscoveryProvider


class CoinbaseDiscoveryProvider(BaseDiscoveryProvider):
    """Discover assets from Coinbase exchange via Market Gateway.

    This is a placeholder implementation that uses the base class logic.
    Once the Coinbase Market Gateway provider is fully implemented,
    override _parse_exchange_info with Coinbase-specific response parsing.
    """
