"""Price Action Engine core interfaces."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime
from research_platform.price_action.models import (
    SwingPoint, MarketStructureChange, LiquiditySweep, BlockStructure, ImbalanceGap, SessionPeriod
)


class IPriceActionOrchestrator:
    """Orchestrates detection of structure and price gaps on tick streams."""

    def process_tick(self, symbol: str, price: float, timestamp: datetime, volume: float = 0.0) -> None:
        """Process an incoming tick updates feed."""
        pass

    def get_swings(self, symbol: str) -> List[SwingPoint]:
        """Retrieve detected swing points."""
        pass

    def get_structure_changes(self, symbol: str) -> List[MarketStructureChange]:
        """Retrieve detected BOS / CHOCH events."""
        pass

    def get_blocks(self, symbol: str) -> List[BlockStructure]:
        """Retrieve detected order, breaker, or mitigation blocks."""
        pass

    def get_gaps(self, symbol: str) -> List[ImbalanceGap]:
        """Retrieve active Fair Value Gaps."""
        pass

    def get_atr(self, symbol: str) -> float:
        """Retrieve calculated Average True Range (ATR)."""
        pass

    def get_vwap(self, symbol: str) -> float:
        """Retrieve calculated Volume Weighted Average Price (VWAP)."""
        pass

    def get_bars(self, symbol: str) -> List[Dict[str, Any]]:
        """Return a defensive copy of the aggregated 1-minute OHLCV bar list for the given symbol.

        Each bar is a dict with keys: timestamp, open, high, low, close, volume.
        Returns an empty list if no bars exist for the symbol.
        Mutating the returned list or any bar dict will NOT affect internal state.
        """
        pass
