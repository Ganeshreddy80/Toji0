"""Thread-safe registry adapter for strategy framework."""

from __future__ import annotations

import logging
import threading
from typing import Dict, Any, List, Optional
from research_platform.strategy_framework.models import ComposedStrategy
from research_platform.platform.service_registry import ServiceRegistry

logger = logging.getLogger(__name__)


class StrategyFrameworkRegistry:
    """Thread-safe framework registry mapping ComposedStrategies to the base StrategyRegistry."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._strategies: Dict[str, ComposedStrategy] = {}

    def register_strategy(self, strategy: ComposedStrategy) -> None:
        sid = strategy.metadata.strategy_id
        with self._lock:
            self._strategies[sid] = strategy

        # Attempt to integrate with Toji core StrategyRegistry
        try:
            registry = ServiceRegistry()
            core_registry_orch = registry.get_service("StrategyRegistryOrchestrator")
            if core_registry_orch:
                core_registry_orch.register_strategy(
                    strategy_id=sid,
                    name=strategy.metadata.name,
                    description=f"Composed strategy of type {strategy.metadata.strategy_type}",
                    version=strategy.metadata.version,
                    git_hash="0000000",
                    dependencies=[],
                    tags=[strategy.metadata.strategy_type],
                    categories=["COMPOSED"],
                    author="SystemComposer",
                    asset_class="CRYPTO_FX",
                    risk_profile="MEDIUM",
                    capabilities=["BACKTEST", "PAPER"]
                )
        except Exception as e:
            logger.warning("StrategyFrameworkRegistry failed to cascade register to core registry: %s", e)

    def get_strategy(self, strategy_id: str) -> Optional[ComposedStrategy]:
        with self._lock:
            return self._strategies.get(strategy_id)

    def list_strategies(self) -> List[ComposedStrategy]:
        with self._lock:
            return list(self._strategies.values())
