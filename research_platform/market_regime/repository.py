"""Thread-safe, append-only repository for storing historical market regimes and transitions.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional
from research_platform.market_regime.interfaces import IMarketRegimeRepository
from research_platform.market_regime.models import (
    HistoricalRegimeRecord,
    MarketRegime,
    MarketStructure,
    RegimeTransition,
)


class MarketRegimeRepository(IMarketRegimeRepository):
    """Memory-backed, thread-safe repository implementation."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._regimes: Dict[str, List[HistoricalRegimeRecord]] = {}
        self._transitions: Dict[str, List[RegimeTransition]] = {}
        self._structures: Dict[str, MarketStructure] = {}

    def save_regime(self, record: HistoricalRegimeRecord) -> None:
        with self._lock:
            if record.symbol not in self._regimes:
                self._regimes[record.symbol] = []
            self._regimes[record.symbol].append(record)

    def get_latest_regime(self, symbol: str) -> Optional[MarketRegime]:
        with self._lock:
            records = self._regimes.get(symbol)
            if not records:
                return None
            return records[-1].regime

    def list_regime_history(self, symbol: str) -> List[HistoricalRegimeRecord]:
        with self._lock:
            return list(self._regimes.get(symbol, []))

    def save_transition(self, transition: RegimeTransition) -> None:
        with self._lock:
            if transition.symbol not in self._transitions:
                self._transitions[transition.symbol] = []
            self._transitions[transition.symbol].append(transition)

    def list_transitions(self, symbol: str) -> List[RegimeTransition]:
        with self._lock:
            return list(self._transitions.get(symbol, []))

    def save_market_structure(self, structure: MarketStructure) -> None:
        with self._lock:
            self._structures[structure.symbol] = structure

    def get_latest_market_structure(self, symbol: str) -> Optional[MarketStructure]:
        with self._lock:
            return self._structures.get(symbol)
