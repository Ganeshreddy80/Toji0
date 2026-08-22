"""Sync Engine querying balances and positions from exchange adapters.
"""

from __future__ import annotations

from typing import List

from research_platform.execution_engine.interfaces import IExchangeAdapter
from research_platform.execution_engine.models import ExchangeBalance, ExchangePosition


class StateSynchronizer:
    """Retrieves exchange positions and balances to sync local registry states."""

    def __init__(self, adapter: IExchangeAdapter) -> None:
        self.adapter = adapter
        self._last_balances: List[ExchangeBalance] = []
        self._last_positions: List[ExchangePosition] = []

    def sync_state(self) -> None:
        """Fetch latest state updates from exchange adapter APIs."""
        self._last_balances = self.adapter.get_balances()
        self._last_positions = self.adapter.get_positions()

    @property
    def balances(self) -> List[ExchangeBalance]:
        return self._last_balances

    @property
    def positions(self) -> List[ExchangePosition]:
        return self._last_positions
