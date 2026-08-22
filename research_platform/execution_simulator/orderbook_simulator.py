"""Orderbook simulator generating simulated L2 snapshots.
"""

from __future__ import annotations

from typing import List, Tuple
from research_platform.execution_simulator.models import OrderBookSlice


class OrderBookSimulator:
    """Generates L2 slices with asks and bids levels."""

    def generate_slice(self, mid_price: float) -> OrderBookSlice:
        asks: List[Tuple[float, float]] = []
        bids: List[Tuple[float, float]] = []

        # Generate 5 levels
        for idx in range(5):
            asks.append((mid_price + 0.05 * (idx + 1), 100.0 + idx * 50.0))
            bids.append((mid_price - 0.05 * (idx + 1), 100.0 + idx * 50.0))

        return OrderBookSlice(asks=asks, bids=bids)
