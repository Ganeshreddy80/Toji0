"""Abstract contracts for the Workflow Orchestration Engine.
"""

from __future__ import annotations

import abc
from typing import Any, List, Optional
from research_platform.workflow_orchestration.models import (
    WorkflowApproval,
    WorkflowInstance,
    WorkflowStepName,
)


class IWorkflowRepository(abc.ABC):
    """Abstract contract for persisting and retrieving active workflow state records."""

    @abc.abstractmethod
    def save_instance(self, instance: WorkflowInstance) -> None:
        """Persist a workflow instance."""

    @abc.abstractmethod
    def get_instance(self, instance_id: str) -> Optional[WorkflowInstance]:
        """Retrieve a workflow instance by ID."""

    @abc.abstractmethod
    def list_instances(self) -> List[WorkflowInstance]:
        """List all workflow instances."""


class IWorkflowEngine(abc.ABC):
    """Abstract contract for processing state machine transitions and retries."""

    @abc.abstractmethod
    def execute_next_step(self, instance: WorkflowInstance) -> WorkflowInstance:
        """Evaluate dependencies and execute the next sequential step."""

    @abc.abstractmethod
    def submit_approval(self, instance: WorkflowInstance, approval: WorkflowApproval) -> WorkflowInstance:
        """Register governance signature and resume progression if paused."""

    @abc.abstractmethod
    def rollback_to_step(self, instance: WorkflowInstance, target_step: WorkflowStepName) -> WorkflowInstance:
        """Revert the workflow state machine back to a previous completed step."""


class IWorkflowOrchestrator(abc.ABC):
    """Abstract contract for the workflow orchestrator."""
    pass
