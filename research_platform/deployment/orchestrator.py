"""Deployment Manager orchestrator coordinating canary rollouts, audits, and health checks.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, List, Optional

from toji_platform.core.event_bus import IEventBus

from research_platform.deployment.interfaces import IDeploymentEngine
from research_platform.deployment.models import StrategyDeployment, DeploymentLock, DeploymentHealthCard, DeploymentSnapshot
from research_platform.deployment.repository import DeploymentRepository
from research_platform.deployment.deployment_engine import DeploymentEngine as Engine
from research_platform.deployment.health_monitor import HealthMonitor
from research_platform.deployment.rollback_manager import RollbackManager
from research_platform.deployment.events import DeploymentTriggered, DeploymentCompleted, DeploymentFailed, DeploymentRolledBack

logger = logging.getLogger(__name__)


class DeploymentOrchestrator(IDeploymentEngine):
    """Central orchestrator managing canary and Blue/Green deployment env routing."""

    def __init__(self, event_bus: IEventBus, container: Optional[Any] = None) -> None:
        self._event_bus = event_bus
        self._container = container
        
        self._repo = DeploymentRepository()
        self._engine = Engine()
        self._health = HealthMonitor()
        self._rollback = RollbackManager(self._repo)

    @property
    def repository(self) -> DeploymentRepository:
        return self._repo

    @property
    def health_monitor(self) -> HealthMonitor:
        return self._health

    @property
    def rollback_manager(self) -> RollbackManager:
        return self._rollback

    # ── Downstream Subsystem Resolvers ───────────────────────────────

    def _resolve(self, key: str) -> Optional[Any]:
        if self._container and self._container.has(key):
            try:
                return self._container.resolve(key)
            except Exception as e:
                logger.error("DeploymentManager: Failed to resolve registry key %s: %s", key, e)
        return None

    def _get_memory_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator")

    def _get_kg_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator")

    def _get_ops_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.operations_center.operations_orchestrator.OperationsOrchestrator")

    # ── IDeploymentEngine Action ─────────────────────────────────────

    def deploy_strategy(
        self,
        strategy_id: str,
        environment: str,
        version_id: str,
        canary_weight: float = 100.0
    ) -> StrategyDeployment:
        """Deploy strategy to target environment using canary routes weights."""
        lock = self._repo.get_lock()
        if lock.is_locked:
            raise RuntimeError(f"Deployment Blocked: Concurrent rollout in progress by '{lock.locked_by}'.")

        # 1. Trigger rollout
        self._event_bus.publish(DeploymentTriggered(payload={"strategy_id": strategy_id, "version_id": version_id}))

        dep = self._engine.initiate_deployment(
            strategy_id=strategy_id,
            environment=environment,
            version_id=version_id,
            canary_weight=canary_weight
        )
        self._repo.save_deployment(dep)

        # 2. Complete rollout
        self._event_bus.publish(DeploymentCompleted(payload={"deployment_id": dep.deployment_id}))
        self._log_downstream_registries(dep, "Deployment Completed")

        return dep

    def lock_deployments(self, actor: str, reason: str) -> None:
        lock = DeploymentLock(is_locked=True, locked_by=actor, reason=reason)
        self._repo.save_lock(lock)

    def unlock_deployments(self) -> None:
        lock = DeploymentLock(is_locked=False)
        self._repo.save_lock(lock)

    def evaluate_deployment_health(self, deployment_id: str) -> DeploymentHealthCard:
        card = self._health.evaluate_health(deployment_id)
        if card.status == "CRITICAL":
            self._event_bus.publish(DeploymentFailed(payload={"deployment_id": deployment_id}))
            self.execute_rollback(deployment_id, "Critical health diagnostics warning.")
        return card

    def execute_rollback(self, deployment_id: str, reason: str) -> StrategyDeployment:
        rolled = self._rollback.rollback_deployment(deployment_id, reason)
        self._event_bus.publish(DeploymentRolledBack(payload={"deployment_id": deployment_id}))
        self._log_downstream_registries(rolled, f"Rolled Back: {reason}")
        return rolled

    def create_snapshot(self) -> DeploymentSnapshot:
        return DeploymentSnapshot(
            timestamp=datetime.now(timezone.utc),
            deployments=self._repo.list_deployments()
        )

    def _log_downstream_registries(self, dep: StrategyDeployment, message: str) -> None:
        # 1. Institutional Memory (R16)
        mem = self._get_memory_orchestrator()
        if mem:
            try:
                mem.publish_memory("deployment", {
                    "deployment_id": dep.deployment_id,
                    "strategy_id": dep.strategy_id,
                    "status": dep.status,
                    "message": message
                })
            except Exception as e:
                logger.error("DeploymentManager Audit: Failed to write to memory: %s", e)

        # 2. Knowledge Graph (R17)
        kg = self._get_kg_orchestrator()
        if kg:
            try:
                kg.register_node(
                    node_id=dep.deployment_id,
                    node_type="DEPLOYMENT",
                    subsystem="deployment",
                    event="DeploymentCompleted",
                    author="deployment",
                    properties={"status": dep.status, "environment": dep.environment}
                )
            except Exception as e:
                logger.error("DeploymentManager Audit: Failed to write to graph: %s", e)

        # 3. Operations Center (R30.5)
        ops = self._get_ops_orchestrator()
        if ops:
            try:
                ops.compile_dashboard_snapshot()
            except Exception as e:
                logger.error("DeploymentManager: Failed to refresh operations center: %s", e)
