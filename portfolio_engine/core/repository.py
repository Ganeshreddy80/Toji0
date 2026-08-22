from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from portfolio_engine.core.interfaces import IPortfolioRepository
from portfolio_engine.core.models import Position, ClosedPosition, PortfolioSnapshot

logger = logging.getLogger(__name__)


import threading

class PortfolioRepository(IPortfolioRepository):
    """Persists and retrieves Portfolio snapshots and position histories."""

    def __init__(self, storage_engine: Any | None = None) -> None:
        self._storage = storage_engine
        self._snapshots: List[PortfolioSnapshot] = []
        self._positions: Dict[str, Position] = {}
        self._closed_positions: List[ClosedPosition] = []
        self._lock = threading.RLock()

    def save_snapshot(self, snapshot: PortfolioSnapshot) -> None:
        """Persist a complete Portfolio snapshot."""
        with self._lock:
            self._snapshots.append(snapshot)
            if len(self._snapshots) > 1000:
                self._snapshots.pop(0)
        logger.debug("PortfolioRepository: Saved snapshot: %s", snapshot.snapshot_id)

    def get_latest_snapshot(self) -> Optional[PortfolioSnapshot]:
        """Retrieve latest consolidated portfolio snapshot."""
        with self._lock:
            if self._snapshots:
                return self._snapshots[-1]
        return None

    def save_position(self, position: Position) -> None:
        """Persist active position details."""
        with self._lock:
            self._positions[position.position_id] = position

    def get_position(self, position_id: str) -> Optional[Position]:
        """Load position details by identifier."""
        with self._lock:
            return self._positions.get(position_id)

    def save_closed_position(self, position: ClosedPosition) -> None:
        """Persist closed position details."""
        with self._lock:
            self._closed_positions.append(position)
            if len(self._closed_positions) > 1000:
                self._closed_positions.pop(0)

    def get_all_closed_positions(self) -> List[ClosedPosition]:
        """Load all closed position logs."""
        with self._lock:
            return list(self._closed_positions)

    def clear(self) -> None:
        """Reset repository store."""
        with self._lock:
            self._snapshots.clear()
            self._positions.clear()
            self._closed_positions.clear()
