"""Strategy Registry index.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional

from research_platform.strategy_lab.models import StrategyDefinition


class StrategyRegistry:
    """Thread-safe catalog indexing strategy compositions, tags, and versions."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: Dict[str, StrategyDefinition] = {}

    def register(self, strategy: StrategyDefinition) -> None:
        with self._lock:
            self._entries[strategy.strategy_id] = strategy

    def get(self, strategy_id: str) -> Optional[StrategyDefinition]:
        with self._lock:
            return self._entries.get(strategy_id)

    def list_all(self) -> List[StrategyDefinition]:
        with self._lock:
            return list(self._entries.values())
