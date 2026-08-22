"""Workflow orchestrator coordinating sequential strategy promotion lifecycles and external subsystems.
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional

from toji_platform.core.event_bus import IEventBus

from research_platform.workflow_orchestration.interfaces import IWorkflowOrchestrator
from research_platform.workflow_orchestration.models import (
    WorkflowApproval,
    WorkflowInstance,
    WorkflowStatus,
    WorkflowStep,
    WorkflowStepName,
)
from research_platform.workflow_orchestration.repository import WorkflowRepository
from research_platform.workflow_orchestration.engine import WorkflowEngine
from research_platform.workflow_orchestration.visualization import WorkflowVisualizer
from research_platform.workflow_orchestration.events import (
    WorkflowApprovalLogged,
    WorkflowPaused,
    WorkflowResumed,
    WorkflowRolledBack,
    WorkflowStarted,
    WorkflowStepCompleted,
    WorkflowStepFailed,
    WorkflowStepTransitioned,
)

logger = logging.getLogger(__name__)


class WorkflowOrchestrator(IWorkflowOrchestrator):
    """Central coordinator for managing strategy promotion pipelines and audits."""

    def __init__(self, event_bus: IEventBus, container: Optional[Any] = None) -> None:
        self._event_bus = event_bus
        self._container = container
        self._repo = WorkflowRepository()

        # Engines
        self._engine = WorkflowEngine()
        self._visualizer = WorkflowVisualizer()

    @property
    def repository(self) -> WorkflowRepository:
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

    def _publish_memory_record(self, record: WorkflowInstance) -> None:
        mem_orch = self._get_memory_orchestrator()
        if not mem_orch:
            return
        try:
            mem_orch.publish_memory("workflow_instances", record)
        except Exception as e:
            logger.error("Failed to publish to institutional memory: %s", e)

    def _update_knowledge_graph(self, record: WorkflowInstance) -> None:
        kg_orch = self._get_kg_orchestrator()
        if not kg_orch:
            return
        try:
            # Register Workflow Node
            kg_orch.register_node(
                node_id=record.instance_id,
                node_type="WORKFLOW_INSTANCE",
                subsystem="workflow_orchestration",
                event="WorkflowStepTransitioned",
                author="system",
                properties={"status": record.status.value, "strategy_id": record.strategy_id}
            )

            # Link Strategy
            kg_orch.register_node(
                node_id=record.strategy_id,
                node_type="STRATEGY",
                subsystem="workflow_orchestration",
                event="WorkflowStepTransitioned",
                author="system",
                properties={"strategy_id": record.strategy_id}
            )
            kg_orch.link_nodes(
                source_id=record.instance_id,
                target_id=record.strategy_id,
                relationship_type="references",
                subsystem="workflow_orchestration"
            )
        except Exception as e:
            logger.error("Failed to update knowledge graph: %s", e)

    # ── Orchestrator Actions ──────────────────────────────────────────

    def create_workflow_instance(self, instance_id: str, strategy_id: str) -> WorkflowInstance:
        """Create and initialize a new sequential strategy promotion workflow."""
        steps = [
            WorkflowStep(name=WorkflowStepName.RESEARCH),
            WorkflowStep(name=WorkflowStepName.BACKTEST),
            WorkflowStep(name=WorkflowStepName.WALK_FORWARD),
            WorkflowStep(name=WorkflowStepName.PAPER_TRADING),
            WorkflowStep(name=WorkflowStepName.RISK_REVIEW),
            WorkflowStep(name=WorkflowStepName.AI_REVIEW),
            WorkflowStep(name=WorkflowStepName.HUMAN_APPROVAL),
            WorkflowStep(name=WorkflowStepName.DEPLOYMENT),
            WorkflowStep(name=WorkflowStepName.MONITORING),
            WorkflowStep(name=WorkflowStepName.RETIREMENT),
        ]
        
        instance = WorkflowInstance(
            instance_id=instance_id,
            strategy_id=strategy_id,
            steps=steps,
            status=WorkflowStatus.PENDING,
            transition_log=["Workflow initialized."]
        )
        self._repo.save_instance(instance)
        self._event_bus.publish(WorkflowStarted(payload={"instance_id": instance_id}))

        # Downstream
        self._publish_memory_record(instance)
        self._update_knowledge_graph(instance)

        return instance

    def advance_workflow(self, instance_id: str) -> WorkflowInstance:
        """Execute the next workflow step and publish state machine updates."""
        instance = self._repo.get_instance(instance_id)
        if not instance:
            raise ValueError(f"Workflow instance '{instance_id}' not found.")

        old_idx = instance.current_step_index
        old_status = instance.status

        # Progress through engine
        updated = self._engine.execute_next_step(instance)
        self._repo.save_instance(updated)

        # Publish state transition events
        if updated.current_step_index != old_idx:
            completed_step = instance.steps[old_idx]
            self._event_bus.publish(WorkflowStepCompleted(payload={
                "instance_id": instance_id,
                "step": completed_step.name.value
            }))
            self._event_bus.publish(WorkflowStepTransitioned(payload={
                "instance_id": instance_id,
                "old_step": completed_step.name.value,
                "new_step": updated.steps[updated.current_step_index].name.value if updated.current_step_index < len(updated.steps) else "NONE"
            }))
        elif updated.status == WorkflowStatus.PAUSED and old_status != WorkflowStatus.PAUSED:
            paused_step = updated.steps[updated.current_step_index]
            self._event_bus.publish(WorkflowPaused(payload={
                "instance_id": instance_id,
                "step": paused_step.name.value
            }))
        elif updated.status == WorkflowStatus.FAILED and old_status != WorkflowStatus.FAILED:
            failed_step = updated.steps[updated.current_step_index]
            self._event_bus.publish(WorkflowStepFailed(payload={
                "instance_id": instance_id,
                "step": failed_step.name.value
            }))

        # Downstream
        self._publish_memory_record(updated)
        self._update_knowledge_graph(updated)

        return updated

    def approve_step(self, instance_id: str, approver: str, signature: str, approved: bool) -> WorkflowInstance:
        """Submit a step approval and resume workflow execution."""
        instance = self._repo.get_instance(instance_id)
        if not instance:
            raise ValueError(f"Workflow instance '{instance_id}' not found.")

        idx = instance.current_step_index
        active_step = instance.steps[idx]

        approval = WorkflowApproval(
            step_name=active_step.name,
            approver=approver,
            signature=signature,
            approved=approved
        )

        # Submit to engine
        updated = self._engine.submit_approval(instance, approval)
        self._repo.save_instance(updated)

        # Publish approval logs
        self._event_bus.publish(WorkflowApprovalLogged(payload={
            "instance_id": instance_id,
            "step": active_step.name.value,
            "approved": approved
        }))

        if approved and updated.status != WorkflowStatus.PAUSED:
            self._event_bus.publish(WorkflowResumed(payload={"instance_id": instance_id}))

        # Downstream
        self._publish_memory_record(updated)
        self._update_knowledge_graph(updated)

        return updated

    def rollback_workflow(self, instance_id: str, target_step_name: WorkflowStepName) -> WorkflowInstance:
        """Roll back workflow instance to a previous completed step."""
        instance = self._repo.get_instance(instance_id)
        if not instance:
            raise ValueError(f"Workflow instance '{instance_id}' not found.")

        updated = self._engine.rollback_to_step(instance, target_step_name)
        self._repo.save_instance(updated)

        self._event_bus.publish(WorkflowRolledBack(payload={
            "instance_id": instance_id,
            "target_step": target_step_name.value
        }))

        # Downstream
        self._publish_memory_record(updated)
        self._update_knowledge_graph(updated)

        return updated

    def visualize_workflow(self, instance_id: str) -> str:
        """Generate Mermaid visualization diagram string."""
        instance = self._repo.get_instance(instance_id)
        if not instance:
            raise ValueError(f"Workflow instance '{instance_id}' not found.")
        return self._visualizer.generate_mermaid_diagram(instance)
