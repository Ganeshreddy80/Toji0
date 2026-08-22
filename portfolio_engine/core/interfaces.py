from __future__ import annotations

from typing import List, Optional, Protocol
from portfolio_engine.core.models import Position, ClosedPosition, PortfolioSnapshot


class IPositionStore(Protocol):
    """Protocol defining active and closed position registry operations."""

    def get_position(self, symbol: str) -> Optional[Position]:
        """Fetch active position for a symbol."""
        ...

    def save_position(self, position: Position) -> None:
        """Insert or update active position details."""
        ...

    def remove_position(self, symbol: str) -> None:
        """Discard active position from register."""
        ...

    def get_all_positions(self) -> List[Position]:
        """Fetch copy of all active open positions."""
        ...

    def add_closed_position(self, position: ClosedPosition) -> None:
        """Register closed historical position."""
        ...

    def get_closed_positions(self) -> List[ClosedPosition]:
        """Fetch copy of all closed positions."""
        ...

    def clear(self) -> None:
        """Reset the registries."""
        ...


class IPortfolioRepository(Protocol):
    """Protocol defining storage persistence for portfolio snapshots and states."""

    def save_snapshot(self, snapshot: PortfolioSnapshot) -> None:
        """Persist a complete Portfolio snapshot."""
        ...

    def get_latest_snapshot(self) -> Optional[PortfolioSnapshot]:
        """Retrieve latest consolidated portfolio snapshot."""
        ...

    def save_position(self, position: Position) -> None:
        """Persist active position details."""
        ...

    def get_position(self, position_id: str) -> Optional[Position]:
        """Load position details by identifier."""
        ...
