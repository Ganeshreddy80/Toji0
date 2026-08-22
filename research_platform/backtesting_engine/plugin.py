"""Backtesting Engine plugin registration.
"""

from __future__ import annotations

from research_platform.backtesting_engine.orchestrator import BacktestingEngineOrchestrator
from research_platform.backtesting_engine.repository import BacktestRepository


class BacktestingEnginePlugin:
    """Hooks the backtesting engine components into the DI container during boot."""

    def __init__(self, container) -> None:
        self.container = container

    def initialize(self) -> None:
        """Register backtest repository and orchestrator mappings."""
        repo = BacktestRepository()
        self.container.register(BacktestRepository, instance=repo)

        # Register Orchestrator
        event_bus = self.container.resolve("IEventBus")
        orchestrator = BacktestingEngineOrchestrator(event_bus)
        self.container.register(BacktestingEngineOrchestrator, instance=orchestrator)
