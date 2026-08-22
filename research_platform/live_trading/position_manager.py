"""Position Manager tracking open entry prices and Stop Loss / Take Profit parameters.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from research_platform.live_trading.interfaces import IPositionManager
from research_platform.live_trading.models import ClosedPosition, OpenPosition

logger = logging.getLogger(__name__)


class PositionManager(IPositionManager):
    """Tracks position entry costs, unrealized gains, and closes records."""

    def __init__(self) -> None:
        self._positions: Dict[str, OpenPosition] = {}
        self._closed_history: List[ClosedPosition] = []
        self._realized_pnl = 0.0

    @property
    def realized_pnl(self) -> float:
        return self._realized_pnl

    def update_position(
        self,
        symbol: str,
        quantity: float,
        price: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> OpenPosition:
        """Update position quantity and average price."""
        if quantity == 0.0:
            # Closing position
            curr = self._positions.pop(symbol, None)
            if curr:
                pnl = (price - curr.entry_price) * curr.quantity
                self._realized_pnl += pnl
                self._closed_history.append(
                    ClosedPosition(
                        symbol=symbol,
                        quantity=curr.quantity,
                        entry_price=curr.entry_price,
                        exit_price=price,
                        realized_pnl=pnl
                    )
                )
            return OpenPosition(
                symbol=symbol,
                quantity=0.0,
                entry_price=0.0,
                current_price=price,
                unrealized_pnl=0.0
            )

        # Update or create position
        curr = self._positions.get(symbol)
        if not curr:
            new_pos = OpenPosition(
                symbol=symbol,
                quantity=quantity,
                entry_price=price,
                current_price=price,
                unrealized_pnl=0.0,
                stop_loss=stop_loss,
                take_profit=take_profit
            )
            self._positions[symbol] = new_pos
            return new_pos
        else:
            # Average entry price calculation
            total_qty = curr.quantity + quantity
            if abs(total_qty) < 1e-9:
                # Closed position
                self._positions.pop(symbol, None)
                pnl = (price - curr.entry_price) * curr.quantity
                self._realized_pnl += pnl
                self._closed_history.append(
                    ClosedPosition(
                        symbol=symbol,
                        quantity=curr.quantity,
                        entry_price=curr.entry_price,
                        exit_price=price,
                        realized_pnl=pnl
                    )
                )
                return OpenPosition(
                    symbol=symbol,
                    quantity=0.0,
                    entry_price=0.0,
                    current_price=price,
                    unrealized_pnl=0.0
                )

            avg_entry = ((curr.entry_price * curr.quantity) + (price * quantity)) / total_qty
            new_pos = OpenPosition(
                symbol=symbol,
                quantity=total_qty,
                entry_price=avg_entry,
                current_price=price,
                unrealized_pnl=(price - avg_entry) * total_qty,
                stop_loss=stop_loss,
                take_profit=take_profit
            )
            self._positions[symbol] = new_pos
            return new_pos

    def get_position(self, symbol: str) -> Optional[OpenPosition]:
        return self._positions.get(symbol)

    def list_positions(self) -> List[OpenPosition]:
        return list(self._positions.values())
