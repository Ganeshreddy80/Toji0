"""Walk Forward Validation orchestrator coordinating optimization windows, sensitivities, and overfitting checks.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, List, Optional

from toji_platform.core.event_bus import IEventBus

from research_platform.walk_forward.models import (
    ValidationWindow,
    SensitivityScore,
    OverfittingCard,
)
from research_platform.walk_forward.repository import WalkForwardRepository
from research_platform.walk_forward.rolling_engine import RollingEngine
from research_platform.walk_forward.expanding_engine import ExpandingEngine
from research_platform.walk_forward.validation_engine import ValidationEngine
from research_platform.walk_forward.robustness_engine import RobustnessEngine
from research_platform.walk_forward.stability_engine import StabilityEngine
from research_platform.walk_forward.events import (
    ValidationWindowCompleted,
    SensitivityAnalyzed,
    OverfittingChecked,
)

logger = logging.getLogger(__name__)


class WalkForwardOrchestrator:
    """Central orchestrator managing rolling/expanding validation pipelines."""

    def __init__(self, event_bus: IEventBus, container: Optional[Any] = None) -> None:
        self._event_bus = event_bus
        self._container = container
        
        self._repo = WalkForwardRepository()
        self._rolling = RollingEngine()
        self._expanding = ExpandingEngine()
        self._validation = ValidationEngine()
        self._robustness = RobustnessEngine()
        self._stability = StabilityEngine()

    @property
    def repository(self) -> WalkForwardRepository:
        return self._repo

    @property
    def rolling_engine(self) -> RollingEngine:
        return self._rolling

    @property
    def expanding_engine(self) -> ExpandingEngine:
        return self._expanding

    # ── Downstream Subsystem Resolvers ───────────────────────────────

    def _resolve(self, key: str) -> Optional[Any]:
        if self._container and self._container.has(key):
            try:
                return self._container.resolve(key)
            except Exception as e:
                logger.error("WalkForward: Failed to resolve registry key %s: %s", key, e)
        return None

    def _get_memory_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator")

    def _get_kg_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator")

    def _get_ops_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.operations_center.operations_orchestrator.OperationsOrchestrator")

    # ── Actions ──────────────────────────────────────────────────────

    def generate_rolling_windows(
        self,
        start: datetime,
        end: datetime,
        train_len_days: float,
        test_len_days: float
    ) -> List[ValidationWindow]:
        wins = self._rolling.generate_rolling_windows(start, end, train_len_days, test_len_days)
        for w in wins:
            self._repo.save_window(w)
        return wins

    def generate_expanding_windows(
        self,
        start: datetime,
        end: datetime,
        initial_train_days: float,
        test_len_days: float
    ) -> List[ValidationWindow]:
        wins = self._expanding.generate_expanding_windows(start, end, initial_train_days, test_len_days)
        for w in wins:
            self._repo.save_window(w)
        return wins

    def validate_window(self, window_id: str, in_sample_sharpe: float, out_of_sample_sharpe: float) -> ValidationWindow:
        win = self._repo.get_window(window_id)
        if not win:
            raise ValueError(f"Window '{window_id}' not found.")

        updated = self._validation.validate_window(win, in_sample_sharpe, out_of_sample_sharpe)
        self._repo.save_window(updated)
        
        self._event_bus.publish(ValidationWindowCompleted(payload={"window_id": window_id}))
        self._log_downstream_registries(window_id, "VALIDATION_WINDOW", f"Window Validated: out_of_sample_sharpe={out_of_sample_sharpe}")
        return updated

    def analyze_sensitivity(self, parameter_name: str, values: List[float], outcomes: List[float]) -> SensitivityScore:
        score = self._robustness.analyze_sensitivity(parameter_name, values, outcomes)
        self._repo.save_sensitivity(score)
        
        self._event_bus.publish(SensitivityAnalyzed(payload={"parameter_name": parameter_name}))
        self._log_downstream_registries(parameter_name, "SENSITIVITY_SCORE", f"Sensitivity Checked: score={score.score}")
        return score

    def detect_overfitting(self, strategy_id: str, is_overfitted: bool, stability_score: float) -> OverfittingCard:
        card = self._stability.detect_overfitting(strategy_id, is_overfitted, stability_score)
        self._repo.save_overfitting(card)
        
        self._event_bus.publish(OverfittingChecked(payload={"strategy_id": strategy_id}))
        self._log_downstream_registries(strategy_id, "OVERFITTING_DIAGNOSTICS", f"Overfitting Checked: is_overfitted={is_overfitted}")
        return card

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
                logger.error("WalkForward Audit: Failed to write to memory: %s", e)

        # 2. Knowledge Graph (R17)
        kg = self._get_kg_orchestrator()
        if kg:
            try:
                kg.register_node(
                    node_id=ref_id,
                    node_type=element_type,
                    subsystem="walk_forward",
                    event="WalkForwardUpdated",
                    author="walk_forward",
                    properties={"message": message}
                )
            except Exception as e:
                logger.error("WalkForward Audit: Failed to write to graph: %s", e)

        # 3. Operations Center (R30.5)
        ops = self._get_ops_orchestrator()
        if ops:
            try:
                ops.compile_dashboard_snapshot()
            except Exception as e:
                logger.error("WalkForward: Failed to refresh operations center: %s", e)
