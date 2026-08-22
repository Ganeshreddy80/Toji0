from __future__ import annotations

import threading
from typing import Dict, List, Optional
from portfolio_engine.core.interfaces import IPositionStore
from portfolio_engine.core.models import Position, ClosedPosition


class PositionStore(IPositionStore):
    """Thread-safe in-memory position registry."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active_positions: Dict[str, Position] = {}
        self._closed_positions: List[ClosedPosition] = []

    def get_position(self, symbol: str) -> Optional[Position]:
        """Fetch active position for a symbol in a thread-safe manner."""
        with self._lock:
            return self._active_positions.get(symbol.upper())

    def save_position(self, position: Position) -> None:
        """Insert or update active position details."""
        with self._lock:
            self._active_positions[position.symbol.upper()] = position

    def remove_position(self, symbol: str) -> None:
        """Discard active position from register."""
        with self._lock:
            self._active_positions.pop(symbol.upper(), None)

    def get_all_positions(self) -> List[Position]:
        """Fetch copy of all active open positions."""
        with self._lock:
            return list(self._active_positions.values())

    def add_closed_position(self, position: ClosedPosition) -> None:
        """Register closed historical position."""
        with self._lock:
            self._closed_positions.append(position)

    def get_closed_positions(self) -> List[ClosedPosition]:
        """Fetch copy of all closed positions."""
        with self._lock:
            return list(self._closed_positions)

    def clear(self) -> None:
        """Reset the registries."""
        with self._lock:
            self._active_positions.clear()
            self._closed_positions.clear()
