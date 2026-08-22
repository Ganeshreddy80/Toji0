"""Binance discovery provider — reference implementation.

Parses Binance exchangeInfo response to extract full asset metadata
including tick sizes, lot sizes, and min notional constraints.
"""

from __future__ import annotations

import logging
from typing import Any

from market_gateway.core.interfaces import IMarketGatewayProvider
from universe.providers.base import BaseDiscoveryProvider

logger = logging.getLogger(__name__)


class BinanceDiscoveryProvider(BaseDiscoveryProvider):
    """Discover assets from Binance exchange via Market Gateway."""

    def __init__(self, gateway_provider: IMarketGatewayProvider) -> None:
        super().__init__(gateway_provider)

    def _parse_exchange_info(
        self, exchange_info: dict[str, Any]
    ) -> dict[str, dict[str, Any]]:
        """Extract metadata from Binance exchangeInfo response.

        Binance symbols contain:
        - baseAsset / quoteAsset
        - filters: PRICE_FILTER (tickSize), LOT_SIZE (stepSize), MIN_NOTIONAL
        """
        result: dict[str, dict[str, Any]] = {}
        symbols_data = exchange_info.get("symbols", [])

        for sym_info in symbols_data:
            raw_symbol = sym_info.get("symbol", "")
            if not raw_symbol:
                continue

            meta: dict[str, Any] = {
                "base_asset": sym_info.get("baseAsset", ""),
                "quote_asset": sym_info.get("quoteAsset", ""),
                "contract_type": "spot",
            }

            # Parse filters if available
            for filt in sym_info.get("filters", []):
                filt_type = filt.get("filterType", "")
                if filt_type == "PRICE_FILTER":
                    try:
                        meta["tick_size"] = float(filt.get("tickSize", 0))
                    except (ValueError, TypeError):
                        pass
                elif filt_type == "LOT_SIZE":
                    try:
                        meta["lot_size"] = float(filt.get("stepSize", 0))
                    except (ValueError, TypeError):
                        pass
                elif filt_type == "MIN_NOTIONAL" or filt_type == "NOTIONAL":
                    try:
                        meta["min_notional"] = float(filt.get("minNotional", 0))
                    except (ValueError, TypeError):
                        pass

            result[raw_symbol] = meta

        logger.info(
            "Parsed Binance exchange info: %d symbols", len(result)
        )
        return result
