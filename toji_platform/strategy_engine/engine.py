"""Strategy Engine orchestrator."""

from __future__ import annotations
import time
import logging
from typing import Any

from toji_platform.strategy_engine.registry import StrategyRegistry
from toji_platform.strategy_engine.base import IStrategy
from toji_platform.strategy_engine.context import StrategyContext
from toji_platform.strategy_engine.models import StrategyResult, TradeIdea
from toji_platform.market_scanner.models import MarketScan

logger = logging.getLogger(__name__)

class StrategyEngine:
    """Orchestrates strategy lifecycle and execution, isolating failures to preserve kernel uptime."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}
        self.registry = StrategyRegistry()

    def register_strategy(self, strategy: IStrategy) -> None:
        """Register a strategy plugin and initialize it with context sandbox."""
        self.registry.register(strategy)
        context = StrategyContext(
            strategy.metadata().name,
            self.config.get("strategies", {}).get(strategy.metadata().name, {})
        )
        strategy.initialize(context)

    def unregister_strategy(self, name: str) -> None:
        """Unregister a strategy plugin and shut it down cleanly."""
        strategy = self.registry.unregister(name)
        if strategy:
            try:
                strategy.shutdown()
            except Exception as e:
                logger.error("Error shutting down strategy '%s': %s", name, e)

    def execute_all(self, scans: list[MarketScan]) -> list[StrategyResult]:
        """Runs all registered strategies under try-catch blocks to isolate crashes."""
        results = []
        for strategy in self.registry.list_strategies():
            name = strategy.metadata().name
            start_time = time.perf_counter()
            ideas = []
            success = True
            err_msg = None
            
            try:
                for scan in scans:
                    res_ideas = strategy.analyze(scan)
                    if res_ideas:
                        ideas.extend(res_ideas)
            except Exception as e:
                logger.error("Fault isolation: Strategy '%s' crashed during analysis: %s", name, e)
                success = False
                err_msg = str(e)
                
            elapsed = (time.perf_counter() - start_time) * 1000.0
            results.append(StrategyResult(
                strategy_name=name,
                trade_ideas=ideas if success else [],
                execution_duration_ms=elapsed,
                success=success,
                error_message=err_msg
            ))
        return results
