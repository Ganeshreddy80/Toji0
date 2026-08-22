"""Thread-safe, bounded-cache repository for Paper Trading state persistence (Sprint 9A)."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from paper_trading.models.paper_models import (
    PaperAccount,
    PaperOrder,
    PaperPosition,
    PaperSession,
    PaperTrade,
)
from paper_trading.state import PaperState

logger = logging.getLogger(__name__)


class PaperRepository:
    """Thread-safe repository providing atomic persistence and bounded caching for Paper Trading."""

    def __init__(self, max_cache_size: int = 10000) -> None:
        self._state = PaperState(max_cache_size=max_cache_size)

    def save_account(self, account: PaperAccount) -> None:
        """Atomically persist account state."""
        self._state.set_account(account)

    def load_account(self) -> Optional[PaperAccount]:
        """Load persistent account state."""
        return self._state.get_account()

    def save_position(self, position: PaperPosition) -> None:
        """Atomically persist position."""
        self._state.set_position(position)

    def load_position(self, symbol: str) -> Optional[PaperPosition]:
        """Load position for symbol."""
        return self._state.get_position(symbol)

    def load_all_positions(self) -> Dict[str, PaperPosition]:
        """Load all open positions."""
        return self._state.get_all_positions()

    def save_order(self, order: PaperOrder) -> None:
        """Atomically persist paper order with bounded cache eviction."""
        self._state.save_order(order)

    def load_order(self, order_id: str) -> Optional[PaperOrder]:
        """Load paper order by ID."""
        return self._state.get_order(order_id)

    def list_orders(self) -> List[PaperOrder]:
        """List all cached paper orders."""
        return self._state.get_all_orders()

    def save_trade(self, trade: PaperTrade) -> None:
        """Atomically persist executed trade with bounded cache eviction."""
        self._state.save_trade(trade)

    def load_trade(self, trade_id: str) -> Optional[PaperTrade]:
        """Load executed trade by ID."""
        return self._state.get_trade(trade_id)

    def list_trades(self) -> List[PaperTrade]:
        """List all cached executed trades."""
        return self._state.get_all_trades()

    def save_session(self, session: PaperSession) -> None:
        """Atomically persist session state."""
        self._state.set_session(session)

    def load_session(self) -> Optional[PaperSession]:
        """Load current paper session state."""
        return self._state.get_session()

    def clear(self) -> None:
        """Clear all stored state."""
        self._state.clear()
