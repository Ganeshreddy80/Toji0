"""Base discovery provider with common symbol normalization and caching."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from market_gateway.core.interfaces import IMarketGatewayProvider
from toji_platform.core.types import AssetClass
from universe.core.interfaces import IDiscoveryProvider
from universe.core.models import ContractType, UniverseAsset

logger = logging.getLogger(__name__)


class BaseDiscoveryProvider(IDiscoveryProvider):
    """Abstract base for exchange-specific discovery providers.

    Wraps an IMarketGatewayProvider and provides shared logic for
    symbol normalization, caching, and asset construction.
    """

    def __init__(self, gateway_provider: IMarketGatewayProvider) -> None:
        self._gateway = gateway_provider
        self._cached_assets: list[UniverseAsset] = []
        self._last_discovery: datetime | None = None

    @property
    def exchange_name(self) -> str:
        return self._gateway.name

    def is_available(self) -> bool:
        """Check provider availability via health check."""
        try:
            health = self._gateway.check_health()
            return health.get("status") in ("connected", "degraded")
        except Exception:
            return False

    def discover(self) -> list[UniverseAsset]:
        """Discover assets from the gateway provider.

        Subclasses should override _parse_exchange_info for exchange-specific
        metadata extraction.
        """
        try:
            symbols = self._gateway.get_symbols()
            exchange_info = self._gateway.get_exchange_info()
        except Exception as e:
            logger.error(
                "Discovery failed for %s: %s", self.exchange_name, e
            )
            return self._cached_assets

        now = datetime.now(UTC)
        symbol_metadata = self._parse_exchange_info(exchange_info)
        assets: list[UniverseAsset] = []

        for raw_symbol in symbols:
            meta = symbol_metadata.get(raw_symbol, {})
            canonical = self._normalize_symbol(
                raw_symbol,
                meta.get("base_asset", ""),
                meta.get("quote_asset", ""),
            )
            if not canonical:
                continue

            asset = UniverseAsset(
                symbol=canonical,
                base_asset=meta.get("base_asset", raw_symbol),
                quote_asset=meta.get("quote_asset", "USDT"),
                exchanges=[self.exchange_name],
                asset_class=AssetClass.CRYPTO,
                contract_type=ContractType(meta.get("contract_type", "spot")),
                tick_size=meta.get("tick_size"),
                lot_size=meta.get("lot_size"),
                discovered_at=now,
                last_updated=now,
            )
            assets.append(asset)

        self._cached_assets = assets
        self._last_discovery = now
        logger.info(
            "Discovered %d assets on %s", len(assets), self.exchange_name
        )
        return assets

    def _normalize_symbol(
        self, raw_symbol: str, base: str, quote: str
    ) -> str:
        """Normalize exchange symbol to canonical format: BASE/QUOTE."""
        if base and quote:
            return f"{base}/{quote}"

        # Fallback heuristic: try common quote suffixes
        for suffix in ("USDT", "BUSD", "USD", "USDC", "BTC", "ETH"):
            if raw_symbol.endswith(suffix):
                base_part = raw_symbol[: -len(suffix)]
                if base_part:
                    return f"{base_part}/{suffix}"

        return ""

    def _parse_exchange_info(
        self, exchange_info: dict[str, Any]
    ) -> dict[str, dict[str, Any]]:
        """Parse exchange-specific metadata.

        Subclasses override this to extract base/quote/tick/lot from
        exchange-specific response formats.

        Returns a map of raw_symbol → metadata dict.
        """
        return {}
