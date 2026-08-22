"""Research Intelligence plugin registration.
"""

from __future__ import annotations

from typing import Any
from research_platform.research_intelligence.orchestrator import ResearchIntelligenceOrchestrator


class ResearchIntelligencePlugin:
    """Hooks the research intelligence components into the DI container during boot."""

    def __init__(self, container) -> None:
        self.container = container

    def initialize(self) -> None:
        """Register orchestrator and quantitative validation mappings."""
        from research_platform.research_intelligence.validation import WalkForwardValidator, MonteCarloSimulator
        from research_platform.research_intelligence.feature_ranking import FeatureAndModelRanker

        event_bus = self.container.resolve("IEventBus")
        
        orchestrator = ResearchIntelligenceOrchestrator(event_bus, container=self.container)
        wfo = WalkForwardValidator()
        mc = MonteCarloSimulator()
        ranker = FeatureAndModelRanker()

        # Type/string DI registrations
        self.container.register(ResearchIntelligenceOrchestrator, instance=orchestrator)
        self.container.register("ResearchIntelligenceOrchestrator", instance=orchestrator)
        self.container.register(WalkForwardValidator, instance=wfo)
        self.container.register("WalkForwardValidator", instance=wfo)
        self.container.register(MonteCarloSimulator, instance=mc)
        self.container.register("MonteCarloSimulator", instance=mc)
        self.container.register(FeatureAndModelRanker, instance=ranker)
        self.container.register("FeatureAndModelRanker", instance=ranker)

    def shutdown(self) -> None:
        """Cleanup resources."""
        pass

    def health_check(self) -> Any:
        """Assess operational health state."""
        from toji_platform.core.types import HealthStatus
        return HealthStatus.HEALTHY
