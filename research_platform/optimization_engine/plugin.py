"""Optimization Engine plugin registration.
"""

from __future__ import annotations

from research_platform.backtesting_engine.orchestrator import BacktestingEngineOrchestrator
from research_platform.optimization_engine.orchestrator import OptimizationEngineOrchestrator
from research_platform.optimization_engine.repository import OptimizationRepository


class OptimizationEnginePlugin:
    """Hooks the optimization engine components into the DI container during boot."""

    def __init__(self, container) -> None:
        self.container = container

    def initialize(self) -> None:
        """Register repositories and orchestrator mappings."""
        repo = OptimizationRepository()
        self.container.register(OptimizationRepository, instance=repo)

        # Register Orchestrator
        event_bus = self.container.resolve("IEventBus")
        backtester = self.container.resolve(BacktestingEngineOrchestrator)
        orchestrator = OptimizationEngineOrchestrator(event_bus, backtester)
        self.container.register(OptimizationEngineOrchestrator, instance=orchestrator)
