"""Thread-safe memory repository caching registered strategy configurations.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional
from research_platform.strategy_registry.interfaces import IStrategyRegistryRepository
from research_platform.strategy_registry.models import RegisteredStrategy


class StrategyRegistryRepository(IStrategyRegistryRepository):
    """Memory-backed, thread-safe repository for strategy registry configurations."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._strategies: Dict[str, RegisteredStrategy] = {}

    def save_strategy(self, strategy: RegisteredStrategy) -> None:
        with self._lock:
            self._strategies[strategy.strategy_id] = strategy

    def get_strategy(self, strategy_id: str) -> Optional[RegisteredStrategy]:
        with self._lock:
            return self._strategies.get(strategy_id)

    def list_strategies(self) -> List[RegisteredStrategy]:
        with self._lock:
            return list(self._strategies.values())
