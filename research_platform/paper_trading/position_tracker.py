"""Position tracker monitoring size, entries cost, and current asset valuations.
"""

from __future__ import annotations

import logging
from typing import Dict
from research_platform.paper_trading.models import PaperPosition

logger = logging.getLogger(__name__)


class PositionTracker:
    """Tracks net position exposures across virtual assets."""

    def __init__(self) -> None:
        self._positions: Dict[str, PaperPosition] = {}

    def update_position_on_fill(self, symbol: str, quantity: float, price: float, side: str) -> PaperPosition:
        existing = self._positions.get(symbol)
        
        if side == "BUY":
            qty_delta = quantity
        else:
            qty_delta = -quantity

        if not existing:
            new_position = PaperPosition(
                symbol=symbol,
                quantity=qty_delta,
                entry_price=price,
                current_price=price,
                realized_pnl=0.0,
                unrealized_pnl=0.0
            )
        else:
            new_qty = existing.quantity + qty_delta
            if new_qty == 0.0:
                # Position closed
                new_position = PaperPosition(
                    symbol=symbol,
                    quantity=0.0,
                    entry_price=0.0,
                    current_price=price,
                    realized_pnl=existing.realized_pnl,
                    unrealized_pnl=0.0
                )
            else:
                # Update entry price using weighted average on buys
                if side == "BUY" and existing.quantity > 0:
                    total_cost = (existing.quantity * existing.entry_price) + (quantity * price)
                    new_entry = total_cost / new_qty
                else:
                    new_entry = existing.entry_price

                new_position = PaperPosition(
                    symbol=symbol,
                    quantity=new_qty,
                    entry_price=new_entry,
                    current_price=price,
                    realized_pnl=existing.realized_pnl,
                    unrealized_pnl=0.0
                )

        self._positions[symbol] = new_position
        return new_position
