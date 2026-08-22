"""Configuration model for Binance endpoints, acting as a single source of truth."""

from __future__ import annotations


class BinanceEndpointConfig:
    """Binance Endpoint Configuration Model."""

    def __init__(
        self,
        provider: str,
        rest_url: str,
        ws_url: str,
        is_live: bool,
        is_testnet: bool,
    ) -> None:
        self.provider = provider
        self.rest_url = rest_url
        self.ws_url = ws_url
        self.is_live = is_live
        self.is_testnet = is_testnet

    @classmethod
    def from_provider(cls, provider: str) -> BinanceEndpointConfig:
        """Resolve config parameters from provider name."""
        provider_lower = provider.lower()
        if provider_lower == "binance_live":
            return cls(
                provider="binance_live",
                rest_url="https://api.binance.com/api",
                ws_url="wss://stream.binance.com:9443/ws",
                is_live=True,
                is_testnet=False,
            )
        elif provider_lower == "binance_testnet":
            return cls(
                provider="binance_testnet",
                rest_url="https://testnet.binance.vision/api",
                ws_url="wss://testnet.binance.vision/ws",
                is_live=False,
                is_testnet=True,
            )
        elif provider_lower == "demo":
            return cls(
                provider="demo",
                rest_url="https://demo-api.binance.com/api",
                ws_url="wss://demo-stream.binance.com/ws",
                is_live=False,
                is_testnet=False,
            )
        else:
            raise ValueError(f"Unsupported MARKET_PROVIDER value: {provider}")
