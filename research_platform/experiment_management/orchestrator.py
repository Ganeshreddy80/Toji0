"""Experiment management orchestrator logging runs, generating comparative reports, and running replays.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from toji_platform.core.event_bus import IEventBus

from research_platform.experiment_management.interfaces import IExperimentManagementOrchestrator
from research_platform.experiment_management.models import (
    ExperimentComparison,
    ExperimentRecord,
    ReproducibilityCheck,
)
from research_platform.experiment_management.repository import ExperimentRepository
from research_platform.experiment_management.replay import ExperimentReplayer
from research_platform.experiment_management.comparison import ExperimentComparer
from research_platform.experiment_management.events import (
    ExperimentLogged,
    ExperimentReplayed,
    ExperimentsCompared,
    ReproducibilityChecked,
)

logger = logging.getLogger(__name__)


class ExperimentManagementOrchestrator(IExperimentManagementOrchestrator):
    """Central orchestrator managing experiment tracking runs and mathematical replays."""

    def __init__(self, event_bus: IEventBus, container: Optional[Any] = None) -> None:
        self._event_bus = event_bus
        self._container = container
        self._repo = ExperimentRepository()

        # Engines
        self._replayer = ExperimentReplayer()
        self._comparer = ExperimentComparer()

    @property
    def repository(self) -> ExperimentRepository:
        return self._repo

    # ── Downstream Integration Helpers ───────────────────────────────

    def _get_memory_orchestrator(self) -> Optional[Any]:
        if self._container and self._container.has("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator"):
            return self._container.resolve("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator")
        return None

    def _get_kg_orchestrator(self) -> Optional[Any]:
        if self._container and self._container.has("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator"):
            return self._container.resolve("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator")
        return None

    def _publish_memory_record(self, category: str, record: Any) -> None:
        mem_orch = self._get_memory_orchestrator()
        if not mem_orch:
            return
        try:
            mem_orch.publish_memory(category, record)
        except Exception as e:
            logger.error("Failed to publish to institutional memory: %s", e)

    def _update_knowledge_graph(self, record: ExperimentRecord, check: Optional[ReproducibilityCheck] = None) -> None:
        kg_orch = self._get_kg_orchestrator()
        if not kg_orch:
            return
        try:
            # Register Experiment Node
            kg_orch.register_node(
                node_id=record.experiment_id,
                node_type="EXPERIMENT",
                subsystem="experiment_management",
                event="ExperimentLogged",
                author="system",
                properties={"dataset_hash": record.dataset_hash, "code_hash": record.code_hash}
            )

            if check:
                check_node_id = f"check-{check.check_id}"
                kg_orch.register_node(
                    node_id=check_node_id,
                    node_type="REPRODUCIBILITY_CHECK",
                    subsystem="experiment_management",
                    event="ReproducibilityChecked",
                    author="system",
                    properties={"matched": check.matched}
                )
                kg_orch.link_nodes(
                    source_id=check_node_id,
                    target_id=record.experiment_id,
                    relationship_type="references",
                    subsystem="experiment_management"
                )
        except Exception as e:
            logger.error("Failed to update knowledge graph: %s", e)

    # ── Orchestrator Actions ──────────────────────────────────────────

    def log_experiment(
        self,
        experiment_id: str,
        description: str,
        dataset_hash: str,
        parameters: Dict[str, Any],
        feature_versions: Dict[str, str],
        metrics: Dict[str, float],
        artifacts: List[str],
        code_hash: str
    ) -> ExperimentRecord:
        """Register an experiment run record."""
        record = ExperimentRecord(
            experiment_id=experiment_id,
            description=description,
            dataset_hash=dataset_hash,
            parameters=parameters,
            feature_versions=feature_versions,
            metrics=metrics,
            artifacts=artifacts,
            code_hash=code_hash,
            status="LOGGED"
        )
        self._repo.save_experiment(record)
        self._event_bus.publish(ExperimentLogged(payload={"experiment_id": experiment_id}))

        # Downstream
        self._publish_memory_record("experiment_records", record)
        self._update_knowledge_graph(record)

        return record

    def verify_reproducibility(
        self,
        experiment_id: str,
        replayed_metrics: Dict[str, float],
        replayed_code_hash: str
    ) -> ReproducibilityCheck:
        """Execute a math simulation replay and verify output differences logs."""
        original = self._repo.get_experiment(experiment_id)
        if not original:
            raise ValueError(f"Original experiment '{experiment_id}' not found.")

        # Replay comparison
        check = self._replayer.replay_experiment(original, replayed_metrics, replayed_code_hash)
        self._repo.save_reproducibility_check(check)

        self._event_bus.publish(ReproducibilityChecked(payload={
            "experiment_id": experiment_id,
            "matched": check.matched
        }))
        self._event_bus.publish(ExperimentReplayed(payload={"experiment_id": experiment_id}))

        # Downstream
        self._publish_memory_record("reproducibility_checks", check)
        self._update_knowledge_graph(original, check)

        return check

    def compare_experiment_runs(self, experiment_ids: List[str]) -> ExperimentComparison:
        """Compile parameters diff and output comparative metrics table reports."""
        records = []
        for eid in experiment_ids:
            rec = self._repo.get_experiment(eid)
            if rec:
                records.append(rec)

        comp = self._comparer.compare_experiments(records)
        self._repo.save_comparison(comp)

        self._event_bus.publish(ExperimentsCompared(payload={"comparison_id": comp.comparison_id}))
        self._publish_memory_record("experiment_comparisons", comp)

        return comp
