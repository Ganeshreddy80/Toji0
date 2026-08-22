"""AI Intelligence plugin registration.
"""

from __future__ import annotations

from research_platform.ai_intelligence.orchestrator import AIIntelligenceOrchestrator
from research_platform.ai_intelligence.repository import AIIntelligenceRepository


class AIIntelligencePlugin:
    """Hooks the AI intelligence components into the DI container during boot."""

    def __init__(self, container) -> None:
        self.container = container

    def initialize(self) -> None:
        """Register repositories and orchestrator mappings."""
        repo = AIIntelligenceRepository()
        self.container.register(AIIntelligenceRepository, instance=repo)

        # Register Orchestrator
        event_bus = self.container.resolve("IEventBus")
        orchestrator = AIIntelligenceOrchestrator(event_bus)
        self.container.register(AIIntelligenceOrchestrator, instance=orchestrator)
