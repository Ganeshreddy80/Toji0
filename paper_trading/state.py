"""Canonical thread-safe state container for Paper Trading subsystem (Sprint 9A)."""

from __future__ import annotations

import collections
import threading
from typing import Dict, List, Optional

from paper_trading.models.paper_models import (
    PaperAccount,
    PaperOrder,
    PaperPosition,
    PaperSession,
    PaperTrade,
)


class PaperState:
    """Thread-safe state container maintaining paper account, positions, orders, trades, and session state."""

    def __init__(self, initial_account: Optional[PaperAccount] = None, max_cache_size: int = 10000) -> None:
        self._lock = threading.RLock()
        self._max_cache_size = max_cache_size

        self._account: Optional[PaperAccount] = initial_account
        self._positions: Dict[str, PaperPosition] = {}
        self._orders: Dict[str, PaperOrder] = {}
        self._order_queue: collections.deque[str] = collections.deque()
        self._trades: Dict[str, PaperTrade] = {}
        self._trade_queue: collections.deque[str] = collections.deque()
        self._session: Optional[PaperSession] = None

    @property
    def lock(self) -> threading.RLock:
        """Return reentrant thread lock."""
        return self._lock

    def get_account(self) -> Optional[PaperAccount]:
        """Get current account snapshot."""
        with self._lock:
            return self._account

    def set_account(self, account: PaperAccount) -> None:
        """Set updated account snapshot."""
        with self._lock:
            self._account = account

    def get_position(self, symbol: str) -> Optional[PaperPosition]:
        """Get open position for a symbol."""
        with self._lock:
            return self._positions.get(symbol)

    def get_all_positions(self) -> Dict[str, PaperPosition]:
        """Get all open positions."""
        with self._lock:
            return dict(self._positions)

    def set_position(self, position: PaperPosition) -> None:
        """Add or update position."""
        with self._lock:
            if abs(position.quantity) < 1e-8:
                self._positions.pop(position.symbol, None)
            else:
                self._positions[position.symbol] = position

    def remove_position(self, symbol: str) -> Optional[PaperPosition]:
        """Remove position for a symbol."""
        with self._lock:
            return self._positions.pop(symbol, None)

    def get_order(self, order_id: str) -> Optional[PaperOrder]:
        """Get order by ID."""
        with self._lock:
            return self._orders.get(order_id)

    def get_all_orders(self) -> List[PaperOrder]:
        """Get all active and historical orders."""
        with self._lock:
            return list(self._orders.values())

    def save_order(self, order: PaperOrder) -> None:
        """Save order to state with bounded cache eviction."""
        with self._lock:
            oid = order.order_id
            if oid not in self._orders:
                if len(self._order_queue) >= self._max_cache_size:
                    oldest_id = self._order_queue.popleft()
                    self._orders.pop(oldest_id, None)
                self._order_queue.append(oid)
            self._orders[oid] = order

    def save_trade(self, trade: PaperTrade) -> None:
        """Record an executed trade with bounded cache eviction."""
        with self._lock:
            tid = trade.trade_id
            if tid not in self._trades:
                if len(self._trade_queue) >= self._max_cache_size:
                    oldest_id = self._trade_queue.popleft()
                    self._trades.pop(oldest_id, None)
                self._trade_queue.append(tid)
            self._trades[tid] = trade

    def get_trade(self, trade_id: str) -> Optional[PaperTrade]:
        """Get trade by ID."""
        with self._lock:
            return self._trades.get(trade_id)

    def get_all_trades(self) -> List[PaperTrade]:
        """Get all executed trades."""
        with self._lock:
            return list(self._trades.values())

    def get_session(self) -> Optional[PaperSession]:
        """Get current paper session."""
        with self._lock:
            return self._session

    def set_session(self, session: PaperSession) -> None:
        """Set current paper session."""
        with self._lock:
            self._session = session

    def clear(self) -> None:
        """Clear all stored state."""
        with self._lock:
            self._account = None
            self._positions.clear()
            self._orders.clear()
            self._order_queue.clear()
            self._trades.clear()
            self._trade_queue.clear()
            self._session = None
