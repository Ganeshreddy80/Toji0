"""Execution Engine plugin registration.
"""

from __future__ import annotations

from research_platform.execution_engine.orchestrator import ExecutionEngineOrchestrator
from research_platform.execution_engine.repository import ExecutionRepository


class ExecutionEnginePlugin:
    """Hooks the execution engine components into the DI container during boot."""

    def __init__(self, container) -> None:
        self.container = container

    def initialize(self) -> None:
        """Register repositories and orchestrator mappings."""
        repo = ExecutionRepository()
        self.container.register(ExecutionRepository, instance=repo)

        # Register Orchestrator
        event_bus = self.container.resolve("IEventBus")
        orchestrator = ExecutionEngineOrchestrator(event_bus)
        self.container.register(ExecutionEngineOrchestrator, instance=orchestrator)
        self.container.register("ExecutionEngineOrchestrator", instance=orchestrator)
