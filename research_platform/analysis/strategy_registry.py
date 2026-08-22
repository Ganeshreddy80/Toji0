"""Strategy registry for the Research Platform (Sprint 6)."""

from __future__ import annotations

import logging
import threading
from typing import Dict, List, Optional

from research_platform.core.exceptions import StrategyRegistryError
from research_platform.core.interfaces import IStrategyRegistry
from research_platform.core.models import StrategyVersion

logger = logging.getLogger(__name__)


class StrategyRegistry(IStrategyRegistry):
    """Thread-safe registry for managing research strategy versions."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        # key: (strategy_id, version) -> StrategyVersion
        self._strategies: Dict[tuple[str, str], StrategyVersion] = {}
        # latest mapping: strategy_id -> StrategyVersion
        self._latest: Dict[str, StrategyVersion] = {}

    def register_strategy(self, strategy: StrategyVersion) -> None:
        """Register a strategy version."""
        if not strategy or not strategy.strategy_id or not strategy.version:
            raise StrategyRegistryError("StrategyVersion must contain valid strategy_id and version.")

        with self._lock:
            key = (strategy.strategy_id, strategy.version)
            self._strategies[key] = strategy
            self._latest[strategy.strategy_id] = strategy
            logger.info("StrategyRegistry: Registered strategy '%s' version '%s'", strategy.strategy_id, strategy.version)

    def get_strategy(self, strategy_id: str, version: Optional[str] = None) -> Optional[StrategyVersion]:
        """Retrieve a registered strategy version."""
        with self._lock:
            if version:
                return self._strategies.get((strategy_id, version))
            return self._latest.get(strategy_id)

    def list_strategies(self) -> List[StrategyVersion]:
        """List all registered strategies."""
        with self._lock:
            return list(self._strategies.values())
