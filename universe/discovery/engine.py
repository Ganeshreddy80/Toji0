"""Multi-provider asset discovery aggregation engine.

Aggregates results from all registered discovery providers,
performs cross-exchange deduplication, and returns a unified
list of UniverseAssets with multi-venue exchange lists.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from universe.core.interfaces import IDiscoveryProvider
from universe.core.models import UniverseAsset

logger = logging.getLogger(__name__)


class DiscoveryEngine:
    """Aggregates asset discovery across multiple exchange providers.

    Key responsibilities:
    - Invoke each registered provider's discover()
    - Cross-exchange deduplication (BTC/USDT on Binance + Bybit = one asset)
    - Merge exchange lists and metadata (prefer most complete)
    - Return a unified, deduplicated list of UniverseAsset
    """

    def __init__(self, providers: list[IDiscoveryProvider] | None = None) -> None:
        self._providers: list[IDiscoveryProvider] = providers or []

    def register_provider(self, provider: IDiscoveryProvider) -> None:
        """Add a discovery provider to the aggregation pool."""
        self._providers.append(provider)
        logger.info("Discovery: Registered provider '%s'", provider.exchange_name)

    def discover_all(self) -> list[UniverseAsset]:
        """Run discovery across all providers and merge results.

        Assets are deduplicated by canonical symbol. When the same
        symbol appears on multiple exchanges:
        - Exchange lists are merged
        - Metadata is merged (most complete wins per field)
        - Timestamps reflect the earliest discovery
        """
        # Collect raw assets from all providers
        all_assets: list[UniverseAsset] = []
        provider_statuses: dict[str, str] = {}

        for provider in self._providers:
            try:
                if not provider.is_available():
                    logger.warning(
                        "Discovery: Provider '%s' unavailable, using cache",
                        provider.exchange_name,
                    )
                    provider_statuses[provider.exchange_name] = "unavailable"

                assets = provider.discover()
                all_assets.extend(assets)
                provider_statuses[provider.exchange_name] = "ok"
                logger.info(
                    "Discovery: Provider '%s' returned %d assets",
                    provider.exchange_name,
                    len(assets),
                )
            except Exception as e:
                logger.error(
                    "Discovery: Provider '%s' failed: %s",
                    provider.exchange_name,
                    e,
                )
                provider_statuses[provider.exchange_name] = f"error: {e}"

        # Deduplicate by canonical symbol
        merged = self._merge_assets(all_assets)
        logger.info(
            "Discovery: Total discovered=%d, after dedup=%d, providers=%d",
            len(all_assets),
            len(merged),
            len(self._providers),
        )
        return merged

    @property
    def provider_count(self) -> int:
        """Number of registered discovery providers."""
        return len(self._providers)

    def _merge_assets(self, assets: list[UniverseAsset]) -> list[UniverseAsset]:
        """Deduplicate assets by symbol and merge metadata."""
        symbol_map: dict[str, UniverseAsset] = {}

        for asset in assets:
            key = asset.symbol
            if key in symbol_map:
                existing = symbol_map[key]
                # Merge exchange lists
                merged_exchanges = list(
                    set(existing.exchanges + asset.exchanges)
                )
                # Prefer most complete metadata (non-None wins)
                symbol_map[key] = UniverseAsset(
                    symbol=existing.symbol,
                    base_asset=existing.base_asset or asset.base_asset,
                    quote_asset=existing.quote_asset or asset.quote_asset,
                    exchanges=merged_exchanges,
                    asset_class=existing.asset_class,
                    contract_type=existing.contract_type,
                    tick_size=existing.tick_size or asset.tick_size,
                    lot_size=existing.lot_size or asset.lot_size,
                    min_notional=existing.min_notional or asset.min_notional,
                    fee_tier=existing.fee_tier or asset.fee_tier,
                    launch_date=existing.launch_date or asset.launch_date,
                    volume_24h_usd=max(existing.volume_24h_usd, asset.volume_24h_usd),
                    price_usd=existing.price_usd or asset.price_usd,
                    price_change_pct_24h=existing.price_change_pct_24h or asset.price_change_pct_24h,
                    volatility=max(existing.volatility, asset.volatility),
                    score=existing.score,
                    rank=existing.rank,
                    discovered_at=min(
                        existing.discovered_at or asset.discovered_at or datetime.now(UTC),
                        asset.discovered_at or existing.discovered_at or datetime.now(UTC),
                    ),
                    last_updated=datetime.now(UTC),
                )
            else:
                symbol_map[key] = asset

        return list(symbol_map.values())
