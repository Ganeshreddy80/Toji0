"""Research Lab orchestrator coordinating feature extractions, factor evaluations, and hypotheses.
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional

from toji_platform.core.event_bus import IEventBus

from research_platform.research_lab.models import (
    FeatureData,
    AlphaFactor,
    Hypothesis,
    ResearchSession,
)
from research_platform.research_lab.repository import ResearchLabRepository
from research_platform.research_lab.feature_store import FeatureStore
from research_platform.research_lab.factor_engine import FactorEngine
from research_platform.research_lab.indicator_library import IndicatorLibrary
from research_platform.research_lab.hypothesis_engine import HypothesisEngine
from research_platform.research_lab.events import (
    ResearchSessionStarted,
    FeatureExtracted,
    FactorCalculated,
    HypothesisVerified,
)

logger = logging.getLogger(__name__)


class ResearchLabOrchestrator:
    """Central orchestrator managing feature stores and factor combinations."""

    def __init__(self, event_bus: IEventBus, container: Optional[Any] = None) -> None:
        self._event_bus = event_bus
        self._container = container
        
        self._repo = ResearchLabRepository()
        self._feature_store = FeatureStore()
        self._factor_engine = FactorEngine()
        self._indicator_library = IndicatorLibrary()
        self._hypothesis_engine = HypothesisEngine()

    @property
    def repository(self) -> ResearchLabRepository:
        return self._repo

    @property
    def indicator_library(self) -> IndicatorLibrary:
        return self._indicator_library

    # ── Downstream Subsystem Resolvers ───────────────────────────────

    def _resolve(self, key: str) -> Optional[Any]:
        if self._container and self._container.has(key):
            try:
                return self._container.resolve(key)
            except Exception as e:
                logger.error("ResearchLab: Failed to resolve registry key %s: %s", key, e)
        return None

    def _get_memory_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator")

    def _get_kg_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator")

    def _get_ops_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.operations_center.operations_orchestrator.OperationsOrchestrator")

    # ── Actions ──────────────────────────────────────────────────────

    def start_session(self, session_id: str, name: str) -> ResearchSession:
        session = ResearchSession(session_id=session_id, name=name)
        self._event_bus.publish(ResearchSessionStarted(payload={"session_id": session_id}))
        return session

    def extract_features(self, feature_id: str, data: List[float]) -> FeatureData:
        feat = self._feature_store.extract_features(feature_id, data)
        self._repo.save_feature(feat)
        
        self._event_bus.publish(FeatureExtracted(payload={"feature_id": feature_id}))
        self._log_downstream_registries(feature_id, "FEATURE", "Feature Extracted")
        return feat

    def calculate_factor(self, factor_id: str, formula: str, inputs: List[float]) -> AlphaFactor:
        fact = self._factor_engine.calculate_factor(factor_id, formula, inputs)
        self._repo.save_factor(fact)
        
        self._event_bus.publish(FactorCalculated(payload={"factor_id": factor_id}))
        self._log_downstream_registries(factor_id, "FACTOR", "Factor Calculated")
        return fact

    def verify_hypothesis(self, hypothesis_id: str, description: str, p_value: float) -> Hypothesis:
        hypo = self._hypothesis_engine.verify_hypothesis(hypothesis_id, description, p_value)
        self._repo.save_hypothesis(hypo)
        
        self._event_bus.publish(HypothesisVerified(payload={"hypothesis_id": hypothesis_id}))
        self._log_downstream_registries(hypothesis_id, "HYPOTHESIS", f"Hypothesis Verified: verified={hypo.verified}")
        return hypo

    def _log_downstream_registries(self, ref_id: str, element_type: str, message: str) -> None:
        # 1. Institutional Memory (R16)
        mem = self._get_memory_orchestrator()
        if mem:
            try:
                mem.publish_memory("research", {
                    "ref_id": ref_id,
                    "type": element_type,
                    "message": message
                })
            except Exception as e:
                logger.error("ResearchLab Audit: Failed to write to memory: %s", e)

        # 2. Knowledge Graph (R17)
        kg = self._get_kg_orchestrator()
        if kg:
            try:
                kg.register_node(
                    node_id=ref_id,
                    node_type=element_type,
                    subsystem="research_lab",
                    event="ResearchUpdated",
                    author="research_lab",
                    properties={"message": message}
                )
            except Exception as e:
                logger.error("ResearchLab Audit: Failed to write to graph: %s", e)

        # 3. Operations Center (R30.5)
        ops = self._get_ops_orchestrator()
        if ops:
            try:
                ops.compile_dashboard_snapshot()
            except Exception as e:
                logger.error("ResearchLab: Failed to refresh operations center: %s", e)
