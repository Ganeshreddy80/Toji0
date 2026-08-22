"""Matching engine matching asks/bids levels.
"""

from __future__ import annotations

from typing import List, Tuple
from research_platform.execution_simulator.models import OrderBookSlice


class MatchingEngine:
    """Matches orders against L2 orderbook bids and asks levels."""

    def match_against_book(
        self,
        book: OrderBookSlice,
        quantity: float,
        side: str
    ) -> List[Tuple[float, float]]:
        # Returns list of matched (price, quantity) tuples
        fills = []
        remaining = quantity
        levels = book.asks if side == "BUY" else book.bids

        for price, size in levels:
            if remaining <= 0.0:
                break
            matched = min(remaining, size)
            fills.append((price, matched))
            remaining -= matched

        return fills
