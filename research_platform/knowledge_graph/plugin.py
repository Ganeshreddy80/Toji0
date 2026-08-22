"""Knowledge Graph plugin registration.
"""

from __future__ import annotations

from research_platform.knowledge_graph.orchestrator import KnowledgeGraphOrchestrator
from research_platform.knowledge_graph.repository import KnowledgeGraphRepository


class KnowledgeGraphPlugin:
    """Hooks the knowledge graph components into the DI container during boot."""

    def __init__(self, container) -> None:
        self.container = container

    def initialize(self) -> None:
        """Register repositories and orchestrator mappings."""
        repo = KnowledgeGraphRepository()
        self.container.register(KnowledgeGraphRepository, instance=repo)

        # Register Orchestrator
        event_bus = self.container.resolve("IEventBus")
        orchestrator = KnowledgeGraphOrchestrator(event_bus)
        self.container.register(KnowledgeGraphOrchestrator, instance=orchestrator)
