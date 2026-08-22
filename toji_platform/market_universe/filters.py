"""Market filters implementation."""

from __future__ import annotations
from typing import Any
from toji_platform.market_universe.models import MarketStats

class MarketFilter:
    """Evaluates markets against configured thresholds, with whitelisting and blacklisting support."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.whitelist = set(config.get("whitelist", []))
        self.blacklist = set(config.get("blacklist", []))

    def evaluate(self, stats: MarketStats) -> bool:
        # Whitelist override bypasses all filters
        if stats.symbol in self.whitelist:
            return True
        
        # Blacklist check
        if stats.symbol in self.blacklist:
            return False

        # Quote asset filter
        if self.config.get("quote_asset") and stats.quote_asset != self.config["quote_asset"]:
            return False

        # Trading status check
        if self.config.get("status") and stats.status != self.config["status"]:
            return False

        # Minimum price filter
        if self.config.get("min_price") is not None and stats.price < self.config["min_price"]:
            return False

        # Minimum 24h volume filter
        if self.config.get("min_volume_24h") is not None and stats.volume_24h < self.config["min_volume_24h"]:
            return False

        # Minimum liquidity depth check
        if self.config.get("min_liquidity_usd") is not None and stats.liquidity_usd < self.config["min_liquidity_usd"]:
            return False

        # Maximum spread check
        if self.config.get("max_spread") is not None and stats.spread > self.config["max_spread"]:
            return False

        return True
