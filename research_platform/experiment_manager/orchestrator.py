"""Experiment Manager orchestrator coordinating run triggers, audits, and rankings.
"""

from __future__ import annotations

import logging
from typing import Any, List, Dict, Optional

from toji_platform.core.event_bus import IEventBus

from research_platform.experiment_manager.interfaces import IExperimentManager
from research_platform.experiment_manager.models import (
    Experiment,
    ReproducibilitySnapshot,
    ExperimentComparison,
    Leaderboard,
)
from research_platform.experiment_manager.repository import ExperimentRepository
from research_platform.experiment_manager.experiment_engine import ExperimentEngine
from research_platform.experiment_manager.comparison_engine import ComparisonEngine
from research_platform.experiment_manager.ranking_engine import RankingEngine
from research_platform.experiment_manager.reproducibility_engine import ReproducibilityEngine
from research_platform.experiment_manager.events import (
    ExperimentCreated,
    ExperimentCompared,
    ExperimentLeaderboardRanked,
)

logger = logging.getLogger(__name__)


class ExperimentManagerOrchestrator(IExperimentManager):
    """Central orchestrator managing strategy backtesting comparison groups."""

    def __init__(self, event_bus: IEventBus, container: Optional[Any] = None) -> None:
        self._event_bus = event_bus
        self._container = container
        
        self._repo = ExperimentRepository()
        self._engine = ExperimentEngine()
        self._comparison = ComparisonEngine(self._repo)
        self._ranking = RankingEngine()
        self._reproducibility = ReproducibilityEngine()

    @property
    def repository(self) -> ExperimentRepository:
        return self._repo

    @property
    def comparison_engine(self) -> ComparisonEngine:
        return self._comparison

    @property
    def ranking_engine(self) -> RankingEngine:
        return self._ranking

    @property
    def reproducibility_engine(self) -> ReproducibilityEngine:
        return self._reproducibility

    # ── Downstream Subsystem Resolvers ───────────────────────────────

    def _resolve(self, key: str) -> Optional[Any]:
        if self._container and self._container.has(key):
            try:
                return self._container.resolve(key)
            except Exception as e:
                logger.error("ExperimentManager: Failed to resolve registry key %s: %s", key, e)
        return None

    def _get_memory_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator")

    def _get_kg_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator")

    def _get_ops_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.operations_center.operations_orchestrator.OperationsOrchestrator")

    # ── IExperimentManager Action ────────────────────────────────────

    def create_experiment(
        self,
        experiment_id: str,
        name: str,
        description: str,
        tags: List[str],
        group_id: str,
        reproducibility: ReproducibilitySnapshot
    ) -> Experiment:
        """Create new experiment, validating inputs."""
        exp = self._engine.initiate_experiment(
            experiment_id=experiment_id,
            name=name,
            description=description,
            tags=tags,
            group_id=group_id,
            reproducibility=reproducibility
        )
        self._repo.save_experiment(exp)

        self._event_bus.publish(ExperimentCreated(payload={"experiment_id": experiment_id}))
        self._log_downstream_registries(exp, "Experiment Created")

        return exp

    def archive_experiment(self, experiment_id: str) -> Experiment:
        exp = self._repo.get_experiment(experiment_id)
        if not exp:
            raise ValueError(f"Experiment '{experiment_id}' not found.")

        archived = exp.model_copy(update={"status": "ARCHIVED"})
        self._repo.save_experiment(archived)
        self._log_downstream_registries(archived, "Experiment Archived")
        return archived

    def clone_experiment(self, source_id: str, new_id: str) -> Experiment:
        source = self._repo.get_experiment(source_id)
        if not source:
            raise ValueError(f"Experiment '{source_id}' not found.")

        cloned = self._engine.clone_experiment(source, new_id)
        self._repo.save_experiment(cloned)
        self._event_bus.publish(ExperimentCreated(payload={"experiment_id": new_id}))
        self._log_downstream_registries(cloned, "Experiment Cloned")
        return cloned

    def update_experiment_results(self, experiment_id: str, results: Dict[str, Any]) -> Experiment:
        exp = self._repo.get_experiment(experiment_id)
        if not exp:
            raise ValueError(f"Experiment '{experiment_id}' not found.")

        updated = exp.model_copy(update={
            "results": results,
            "status": "COMPLETED"
        })
        self._repo.save_experiment(updated)
        self._log_downstream_registries(updated, "Experiment Results Saved")
        return updated

    def evaluate_comparison(self, experiment_ids: List[str]) -> ExperimentComparison:
        comp = self._comparison.compare_runs(experiment_ids)
        self._event_bus.publish(ExperimentCompared(payload={"experiment_ids": experiment_ids}))
        return comp

    def update_leaderboard(self, name: str, group_id: str) -> Leaderboard:
        exps = [e for e in self._repo.list_experiments() if e.group_id == group_id and e.status == "COMPLETED"]
        leaderboard = self._ranking.rank_strategies(name, exps)
        self._event_bus.publish(ExperimentLeaderboardRanked(payload={"leaderboard_name": name}))
        return leaderboard

    def verify_reproducibility(self, first_id: str, second_id: str) -> bool:
        f = self._repo.get_experiment(first_id)
        s = self._repo.get_experiment(second_id)
        if not f or not s:
            return False
        return self._reproducibility.verify_reproducibility(f.reproducibility, s.reproducibility)

    def _log_downstream_registries(self, exp: Experiment, message: str) -> None:
        # 1. Institutional Memory (R16)
        mem = self._get_memory_orchestrator()
        if mem:
            try:
                mem.publish_memory("research", {
                    "experiment_id": exp.experiment_id,
                    "status": exp.status,
                    "message": message
                })
            except Exception as e:
                logger.error("ExperimentManager Audit: Failed to write to memory: %s", e)

        # 2. Knowledge Graph (R17)
        kg = self._get_kg_orchestrator()
        if kg:
            try:
                kg.register_node(
                    node_id=exp.experiment_id,
                    node_type="EXPERIMENT",
                    subsystem="experiment_manager",
                    event="ExperimentCreated",
                    author="experiment_manager",
                    properties={"status": exp.status, "group_id": exp.group_id}
                )
            except Exception as e:
                logger.error("ExperimentManager Audit: Failed to write to graph: %s", e)

        # 3. Operations Center (R30.5)
        ops = self._get_ops_orchestrator()
        if ops:
            try:
                ops.compile_dashboard_snapshot()
            except Exception as e:
                logger.error("ExperimentManager: Failed to refresh operations center: %s", e)
