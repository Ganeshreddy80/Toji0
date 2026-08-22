"""Alpha Factory orchestrator coordinating signals generation, combos combinations, and ensembling.
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional

from toji_platform.core.event_bus import IEventBus

from research_platform.alpha_factory.models import (
    AlphaSignal,
    AlphaCombo,
    EnsembleModel,
)
from research_platform.alpha_factory.repository import AlphaFactoryRepository
from research_platform.alpha_factory.signal_engine import SignalEngine
from research_platform.alpha_factory.alpha_engine import AlphaEngine
from research_platform.alpha_factory.ensemble_engine import EnsembleEngine
from research_platform.alpha_factory.ranking_engine import RankingEngine
from research_platform.alpha_factory.confidence_engine import ConfidenceEngine
from research_platform.alpha_factory.events import (
    SignalGenerated,
    ComboCreated,
    EnsembleModelUpdated,
)

logger = logging.getLogger(__name__)


class AlphaFactoryOrchestrator:
    """Central orchestrator combining factors into ensembled signals."""

    def __init__(self, event_bus: IEventBus, container: Optional[Any] = None) -> None:
        self._event_bus = event_bus
        self._container = container
        
        self._repo = AlphaFactoryRepository()
        self._signal_engine = SignalEngine()
        self._alpha_engine = AlphaEngine()
        self._ensemble_engine = EnsembleEngine()
        self._ranking_engine = RankingEngine()
        self._confidence_engine = ConfidenceEngine()

    @property
    def repository(self) -> AlphaFactoryRepository:
        return self._repo

    @property
    def ranking_engine(self) -> RankingEngine:
        return self._ranking

    @property
    def confidence_engine(self) -> ConfidenceEngine:
        return self._confidence_engine

    # ── Downstream Subsystem Resolvers ───────────────────────────────

    def _resolve(self, key: str) -> Optional[Any]:
        if self._container and self._container.has(key):
            try:
                return self._container.resolve(key)
            except Exception as e:
                logger.error("AlphaFactory: Failed to resolve registry key %s: %s", key, e)
        return None

    def _get_memory_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator")

    def _get_kg_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator")

    def _get_ops_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.operations_center.operations_orchestrator.OperationsOrchestrator")

    # ── Actions ──────────────────────────────────────────────────────

    def generate_signal(self, signal_id: str, factor_id: str, values: List[float]) -> AlphaSignal:
        sig = self._signal_engine.generate_signal(signal_id, factor_id, values)
        self._repo.save_signal(sig)
        
        self._event_bus.publish(SignalGenerated(payload={"signal_id": signal_id}))
        self._log_downstream_registries(signal_id, "ALPHA_SIGNAL", "Signal Generated")
        return sig

    def combine_signals(self, combo_id: str, signals: List[AlphaSignal], weights: List[float]) -> AlphaCombo:
        combo = self._alpha_engine.combine_signals(combo_id, signals, weights)
        self._repo.save_combo(combo)
        
        self._event_bus.publish(ComboCreated(payload={"combo_id": combo_id}))
        self._log_downstream_registries(combo_id, "ALPHA_COMBO", "Signal Combination Created")
        return combo

    def create_ensemble(self, ensemble_id: str, combos: List[AlphaCombo]) -> EnsembleModel:
        model = self._ensemble_engine.create_ensemble(ensemble_id, combos)
        self._repo.save_ensemble(model)
        
        self._event_bus.publish(EnsembleModelUpdated(payload={"ensemble_id": ensemble_id}))
        self._log_downstream_registries(ensemble_id, "ENSEMBLE_MODEL", "Ensemble Model Compiled")
        return model

    def rank_signals(self, signals: List[AlphaSignal]) -> List[AlphaSignal]:
        return self._ranking_engine.rank_signals(signals)

    def evaluate_confidence(self, signal: AlphaSignal) -> float:
        return self._confidence_engine.evaluate_confidence(signal)

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
                logger.error("AlphaFactory Audit: Failed to write to memory: %s", e)

        # 2. Knowledge Graph (R17)
        kg = self._get_kg_orchestrator()
        if kg:
            try:
                kg.register_node(
                    node_id=ref_id,
                    node_type=element_type,
                    subsystem="alpha_factory",
                    event="AlphaUpdated",
                    author="alpha_factory",
                    properties={"message": message}
                )
            except Exception as e:
                logger.error("AlphaFactory Audit: Failed to write to graph: %s", e)

        # 3. Operations Center (R30.5)
        ops = self._get_ops_orchestrator()
        if ops:
            try:
                ops.compile_dashboard_snapshot()
            except Exception as e:
                logger.error("AlphaFactory: Failed to refresh operations center: %s", e)
