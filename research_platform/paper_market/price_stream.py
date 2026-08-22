"""Price stream provider wrapping the state cache.
"""

from __future__ import annotations

from typing import Optional
from research_platform.paper_market.market_state_cache import MarketStateCache


class PriceStream:
    """Interface providing current pricing feeds details."""

    def __init__(self, cache: MarketStateCache) -> None:
        self._cache = cache

    def get_latest_price(self, symbol: str) -> Optional[float]:
        return self._cache.get_price(symbol)
