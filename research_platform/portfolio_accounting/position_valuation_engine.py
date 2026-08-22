"""Position Valuation Engine — per-position price and PnL tracking.

Updated on every market tick and every fill event.
Thread-safe: uses RLock (same thread as EventBus dispatch, but RLock is safe).
Performance: O(1) per-tick update; O(positions) only on snapshot read.
"""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from research_platform.portfolio_accounting.interfaces import IPositionValuationEngine
from research_platform.portfolio_accounting.models import (
    PositionHistoryEntry,
    ValuatedPosition,
)

logger = logging.getLogger(__name__)


class PositionValuationEngine(IPositionValuationEngine):
    """Maintains a live registry of ValuatedPositions.

    on_tick()  — called on every market price update (hot path, must be fast)
    on_fill()  — called after confirmed order fill
    on_close() — called when position is fully or partially closed
    """

    def __init__(self) -> None:
        self._positions: Dict[str, ValuatedPosition] = {}
        self._history: List[PositionHistoryEntry] = []
        self._lock = threading.RLock()

    # ── IPositionValuationEngine ──────────────────────────────────────────────

    def on_tick(self, symbol: str, price: float) -> Optional[ValuatedPosition]:
        """Update the position for symbol on a new market price.  O(1), no I/O."""
        with self._lock:
            pos = self._positions.get(symbol)
            if pos is None:
                return None
            pos.tick_update(price)
            # NOTE: history writes only on fill/close events (not every tick)
            # to keep the hot path at O(1) with no allocations.
            return pos

    def on_fill(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        commission: float = 0.0,
    ) -> ValuatedPosition:
        """Open or extend a position after a confirmed fill."""
        with self._lock:
            existing = self._positions.get(symbol)
            pos_side = "LONG" if side == "BUY" else "SHORT"

            if existing is None:
                pos = ValuatedPosition(
                    symbol=symbol,
                    side=pos_side,
                    quantity=quantity,
                    average_entry=price,
                    current_price=price,
                    market_value=quantity * price,
                    highest_price_seen=price,
                    lowest_price_seen=price,
                )
                self._positions[symbol] = pos
                self._append_history(symbol, "OPEN", quantity, quantity, price, 0.0, 0.0)
                logger.info("PositionValuationEngine: opened %s %s qty=%.4f @ %.4f", pos_side, symbol, quantity, price)
            else:
                # Weighted average entry
                total_qty = existing.quantity + quantity
                avg = (existing.average_entry * existing.quantity + price * quantity) / total_qty
                existing.quantity = total_qty
                existing.average_entry = avg
                existing.tick_update(price)
                self._append_history(symbol, "UPDATE", quantity, total_qty, price,
                                     existing.unrealized_pnl, existing.realized_pnl)
                logger.info("PositionValuationEngine: added to %s qty=%.4f (total=%.4f) avg=%.4f",
                            symbol, quantity, total_qty, avg)
                pos = existing

            return pos

    def on_close(
        self,
        symbol: str,
        quantity: float,
        exit_price: float,
        commission: float = 0.0,
    ) -> Tuple[Optional[ValuatedPosition], float]:
        """Reduce or fully close a position.

        Returns:
            (updated_position_or_None, realized_pnl_this_close)
        """
        with self._lock:
            pos = self._positions.get(symbol)
            if pos is None:
                logger.warning("PositionValuationEngine: on_close for unknown symbol %s", symbol)
                return None, 0.0

            if pos.side == "LONG":
                realized = (exit_price - pos.average_entry) * min(quantity, pos.quantity)
            else:
                realized = (pos.average_entry - exit_price) * min(quantity, pos.quantity)

            realized -= commission
            pos.realized_pnl += realized

            if quantity >= pos.quantity:
                # Full close
                remaining = 0.0
                del self._positions[symbol]
                self._append_history(symbol, "CLOSE", -pos.quantity, 0.0, exit_price,
                                     0.0, pos.realized_pnl)
                logger.info("PositionValuationEngine: closed %s realized_pnl=%.2f", symbol, realized)
                return None, realized
            else:
                # Partial close
                pos.quantity -= quantity
                pos.tick_update(exit_price)
                self._append_history(symbol, "PARTIAL_CLOSE", -quantity, pos.quantity, exit_price,
                                     pos.unrealized_pnl, pos.realized_pnl)
                logger.info("PositionValuationEngine: partial close %s remaining=%.4f realized=%.2f",
                            symbol, pos.quantity, realized)
                return pos, realized

    def get_all_positions(self) -> List[ValuatedPosition]:
        with self._lock:
            return list(self._positions.values())

    def get_position(self, symbol: str) -> Optional[ValuatedPosition]:
        with self._lock:
            return self._positions.get(symbol)

    def get_history(self, symbol: str = None) -> List[PositionHistoryEntry]:
        """Return position history, optionally filtered by symbol."""
        with self._lock:
            if symbol:
                return [e for e in self._history if e.symbol == symbol]
            return list(self._history)

    # ── Internals ────────────────────────────────────────────────────────────

    def _append_history(
        self,
        symbol: str,
        event_type: str,
        qty_delta: float,
        qty_remaining: float,
        price: float,
        unrealized_pnl: float,
        realized_pnl: float,
    ) -> None:
        entry = PositionHistoryEntry(
            entry_id=f"ph-{uuid.uuid4().hex[:8]}",
            symbol=symbol,
            event_type=event_type,  # type: ignore[arg-type]
            quantity_delta=qty_delta,
            quantity_remaining=qty_remaining,
            price=price,
            unrealized_pnl=unrealized_pnl,
            realized_pnl=realized_pnl,
        )
        self._history.append(entry)
        # Keep last 10,000 entries to bound memory
        if len(self._history) > 10_000:
            self._history = self._history[-10_000:]
