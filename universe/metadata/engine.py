"""Metadata enrichment engine for discovered assets.

Sources additional metadata from gateway providers' exchange info
to populate tick_size, lot_size, contract_type, fee_tier, and asset_class.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from toji_platform.core.types import AssetClass
from universe.core.interfaces import IMetadataEnricher
from universe.core.models import ContractType, UniverseAsset

logger = logging.getLogger(__name__)


class MetadataEngine(IMetadataEnricher):
    """Enriches discovered assets with detailed metadata.

    Operates on the list of UniverseAsset objects post-discovery,
    filling in any missing metadata fields using supplementary
    data sources or heuristics.
    """

    def __init__(
        self,
        supplementary_data: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        """Initialize the metadata engine.

        Args:
            supplementary_data: Optional override map of symbol → metadata
                               for testing or manual enrichment.
        """
        self._supplementary = supplementary_data or {}

    def enrich(self, assets: list[UniverseAsset]) -> list[UniverseAsset]:
        """Attach detailed metadata to each asset.

        Enrichment strategy:
        1. Apply supplementary data overrides (if any)
        2. Infer asset_class from quote asset naming conventions
        3. Estimate contract_type from symbol patterns
        4. Default fee_tier based on exchange
        """
        enriched: list[UniverseAsset] = []
        now = datetime.now(UTC)

        for asset in assets:
            supp = self._supplementary.get(asset.symbol, {})

            enriched_asset = UniverseAsset(
                symbol=asset.symbol,
                base_asset=asset.base_asset,
                quote_asset=asset.quote_asset,
                exchanges=asset.exchanges,
                asset_class=self._infer_asset_class(asset, supp),
                contract_type=self._infer_contract_type(asset, supp),
                tick_size=supp.get("tick_size") or asset.tick_size,
                lot_size=supp.get("lot_size") or asset.lot_size,
                min_notional=supp.get("min_notional") or asset.min_notional,
                fee_tier=supp.get("fee_tier") or asset.fee_tier or self._default_fee_tier(asset),
                launch_date=asset.launch_date,
                volume_24h_usd=supp.get("volume_24h_usd", asset.volume_24h_usd),
                price_usd=supp.get("price_usd", asset.price_usd),
                price_change_pct_24h=supp.get("price_change_pct_24h", asset.price_change_pct_24h),
                volatility=supp.get("volatility", asset.volatility),
                score=asset.score,
                rank=asset.rank,
                discovered_at=asset.discovered_at,
                last_updated=now,
            )
            enriched.append(enriched_asset)

        logger.info("Metadata: Enriched %d assets", len(enriched))
        return enriched

    def _infer_asset_class(
        self, asset: UniverseAsset, supp: dict[str, Any]
    ) -> AssetClass:
        """Infer asset class from symbol characteristics."""
        if "asset_class" in supp:
            try:
                return AssetClass(supp["asset_class"])
            except ValueError:
                pass

        # Heuristic: if quote is a fiat currency, could be forex
        fiat_quotes = {"USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF"}
        if asset.base_asset in fiat_quotes and asset.quote_asset in fiat_quotes:
            return AssetClass.FOREX

        # Default for crypto pairs
        return asset.asset_class

    def _infer_contract_type(
        self, asset: UniverseAsset, supp: dict[str, Any]
    ) -> ContractType:
        """Infer contract type from symbol patterns."""
        if "contract_type" in supp:
            try:
                return ContractType(supp["contract_type"])
            except ValueError:
                pass

        symbol_upper = asset.symbol.upper()
        if "PERP" in symbol_upper:
            return ContractType.PERPETUAL
        if any(q in symbol_upper for q in ("_QUARTER", "_BIQUARTER", "-SWAP")):
            return ContractType.FUTURES

        return asset.contract_type

    def _default_fee_tier(self, asset: UniverseAsset) -> str:
        """Assign a default fee tier based on exchange name."""
        exchange_fees = {
            "Binance": "standard",
            "Bybit": "standard",
            "Coinbase": "advanced",
            "Hyperliquid": "maker-rebate",
        }
        for exchange in asset.exchanges:
            if exchange in exchange_fees:
                return exchange_fees[exchange]
        return "standard"
