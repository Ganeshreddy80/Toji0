"""Dynamic strategy loader supporting hot reloading and runtime versioning."""

from __future__ import annotations

import logging
import threading
from typing import Dict, Any, Optional, List
from research_platform.strategy_framework.models import ComposedStrategy

logger = logging.getLogger(__name__)


class StrategyLoader:
    """Thread-safe dynamic loader managing hot-reloading of strategies."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active_strategies: Dict[str, ComposedStrategy] = {}
        self._versions_history: Dict[str, List[ComposedStrategy]] = {}

    def load_strategy(self, strategy: ComposedStrategy) -> None:
        sid = strategy.metadata.strategy_id
        with self._lock:
            self._active_strategies[sid] = strategy
            self._versions_history.setdefault(sid, []).append(strategy)
        logger.info("Strategy %s version %s loaded successfully.", sid, strategy.metadata.version)

    def reload_strategy(self, strategy_id: str, new_version: ComposedStrategy) -> None:
        with self._lock:
            if strategy_id not in self._active_strategies:
                raise KeyError(f"Strategy {strategy_id} is not currently active.")
            self._active_strategies[strategy_id] = new_version
            self._versions_history.setdefault(strategy_id, []).append(new_version)
        logger.info("Strategy %s hot-reloaded to version %s.", strategy_id, new_version.metadata.version)

    def get_strategy(self, strategy_id: str) -> Optional[ComposedStrategy]:
        with self._lock:
            return self._active_strategies.get(strategy_id)

    def get_all_active(self) -> List[ComposedStrategy]:
        with self._lock:
            return list(self._active_strategies.values())

    def get_versions(self, strategy_id: str) -> List[ComposedStrategy]:
        with self._lock:
            return list(self._versions_history.get(strategy_id, []))
