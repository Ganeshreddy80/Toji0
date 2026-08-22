"""Thread-safe, append-only repository for storing simulation runs and orders.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional
from research_platform.simulation.interfaces import ISimulationRepository
from research_platform.simulation.models import (
    ReplayConfiguration,
    SimOrder,
    SimulationResult,
)


class SimulationRepository(ISimulationRepository):
    """Memory-backed, thread-safe repository implementation."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._configs: Dict[str, ReplayConfiguration] = {}
        self._orders: Dict[str, List[SimOrder]] = {}
        self._results: Dict[str, SimulationResult] = {}

    def save_configuration(self, config: ReplayConfiguration) -> None:
        with self._lock:
            self._configs[config.session_id] = config

    def get_configuration(self, session_id: str) -> Optional[ReplayConfiguration]:
        with self._lock:
            return self._configs.get(session_id)

    def save_order(self, order: SimOrder) -> None:
        with self._lock:
            # We map orders using a default session key or mock indexing
            session_key = "default_session"
            if session_key not in self._orders:
                self._orders[session_key] = []
            self._orders[session_key].append(order)

    def list_orders(self, session_id: str) -> List[SimOrder]:
        with self._lock:
            return list(self._orders.get(session_id, []))

    def save_result(self, result: SimulationResult) -> None:
        with self._lock:
            self._results[result.session_id] = result

    def get_result(self, session_id: str) -> Optional[SimulationResult]:
        with self._lock:
            return self._results.get(session_id)
