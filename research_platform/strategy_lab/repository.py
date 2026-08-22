"""Strategy Lab database repository.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional

from research_platform.strategy_lab.interfaces import IStrategyRepository
from research_platform.strategy_lab.models import StrategyDefinition


class StrategyRepository(IStrategyRepository):
    """Memory repository saving strategy definitions."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._db: Dict[str, StrategyDefinition] = {}

    def save(self, strategy: StrategyDefinition) -> None:
        """Persist a StrategyDefinition."""
        with self._lock:
            self._db[strategy.strategy_id] = strategy

    def get(self, strategy_id: str) -> Optional[StrategyDefinition]:
        """Fetch StrategyDefinition by ID."""
        with self._lock:
            return self._db.get(strategy_id)

    def list_all(self) -> List[StrategyDefinition]:
        """List all strategies."""
        with self._lock:
            return list(self._db.values())
