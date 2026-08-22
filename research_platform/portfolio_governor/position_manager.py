"""Thread-safe in-memory position registry for the Portfolio Governor."""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional

from research_platform.portfolio_governor.models import GovernedPosition

logger = logging.getLogger(__name__)


class PositionManager:
    """Maintains a thread-safe registry of all currently open governed positions."""

    def __init__(self) -> None:
        self._positions: Dict[str, GovernedPosition] = {}
        self._lock = threading.RLock()

    # ── Public API ────────────────────────────────────────────────────────────

    def get_position(self, symbol: str) -> Optional[GovernedPosition]:
        """Return the open position for the given symbol, or None."""
        with self._lock:
            return self._positions.get(symbol)

    def get_all_positions(self) -> List[GovernedPosition]:
        """Return a snapshot list of all open positions."""
        with self._lock:
            return list(self._positions.values())

    def open_count(self) -> int:
        """Return the number of currently open positions."""
        with self._lock:
            return len(self._positions)

    def open_position(
        self,
        symbol: str,
        side: str,            # "LONG" or "SHORT"
        quantity: float,
        entry_price: float,
    ) -> GovernedPosition:
        """Record a new open position after a confirmed fill.

        If a position already exists for the symbol (e.g. adding to it),
        a weighted average entry price is computed.
        """
        with self._lock:
            existing = self._positions.get(symbol)
            if existing is None:
                pos = GovernedPosition(
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    average_entry_price=entry_price,
                    current_price=entry_price,
                )
                self._positions[symbol] = pos
                logger.info(
                    "PositionManager: opened %s %s qty=%.4f @ %.2f",
                    side, symbol, quantity, entry_price,
                )
                return pos

            # Add to existing position — weighted average
            total_qty = existing.quantity + quantity
            avg_price = (
                (existing.average_entry_price * existing.quantity + entry_price * quantity)
                / total_qty
            )
            existing.quantity = total_qty
            existing.average_entry_price = avg_price
            existing.current_price = entry_price
            existing.updated_at = datetime.now(timezone.utc)
            logger.info(
                "PositionManager: added to %s %s qty=%.4f (total=%.4f) @ avg=%.2f",
                side, symbol, quantity, total_qty, avg_price,
            )
            return existing

    def reduce_position(
        self,
        symbol: str,
        quantity: float,
        exit_price: float,
    ) -> Optional[GovernedPosition]:
        """Reduce (or close) a position by the given quantity.

        Returns the updated position, or None if the position did not exist.
        Removes the entry when quantity reaches zero.
        """
        with self._lock:
            pos = self._positions.get(symbol)
            if pos is None:
                logger.warning("PositionManager: reduce_position called for unknown symbol %s", symbol)
                return None

            if quantity >= pos.quantity:
                # Full close — compute realized PnL
                if pos.side == "LONG":
                    realized = (exit_price - pos.average_entry_price) * pos.quantity
                else:
                    realized = (pos.average_entry_price - exit_price) * pos.quantity
                pos.realized_pnl += realized
                pos.quantity = 0.0
                del self._positions[symbol]
                logger.info(
                    "PositionManager: closed %s %s realized_pnl=%.2f",
                    symbol, pos.side, realized,
                )
            else:
                # Partial close
                if pos.side == "LONG":
                    realized = (exit_price - pos.average_entry_price) * quantity
                else:
                    realized = (pos.average_entry_price - exit_price) * quantity
                pos.realized_pnl += realized
                pos.quantity -= quantity
                pos.current_price = exit_price
                pos.updated_at = datetime.now(timezone.utc)
                logger.info(
                    "PositionManager: partial close %s remaining=%.4f realized_pnl=%.2f",
                    symbol, pos.quantity, realized,
                )
            return pos

    def update_price(self, symbol: str, price: float) -> None:
        """Push a market price update to the held position (unrealized PnL refresh)."""
        with self._lock:
            pos = self._positions.get(symbol)
            if pos:
                pos.update_price(price)
