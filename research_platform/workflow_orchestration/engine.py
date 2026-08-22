"""Workflow engine running lifecycle state transitions, retries, pauses, and rollbacks.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List
from research_platform.workflow_orchestration.interfaces import IWorkflowEngine
from research_platform.workflow_orchestration.models import (
    WorkflowApproval,
    WorkflowInstance,
    WorkflowStatus,
    WorkflowStep,
    WorkflowStepName,
)

logger = logging.getLogger(__name__)


class WorkflowEngine(IWorkflowEngine):
    """Processes sequential workflow step transitions, retries, rollbacks, and pause/resumptions."""

    def execute_next_step(self, instance: WorkflowInstance) -> WorkflowInstance:
        """Evaluate dependencies and execute the next sequential step."""
        if instance.status in (WorkflowStatus.COMPLETED, WorkflowStatus.FAILED):
            return instance

        idx = instance.current_step_index
        if idx >= len(instance.steps):
            return instance.model_copy(update={"status": WorkflowStatus.COMPLETED})

        steps = list(instance.steps)
        step = steps[idx]

        # If already running or paused, block execution progress
        if step.status in (WorkflowStatus.RUNNING, WorkflowStatus.PAUSED):
            return instance

        # 1. Handle Governance Approval Steps (pauses execution)
        if step.name in (WorkflowStepName.RISK_REVIEW, WorkflowStepName.AI_REVIEW, WorkflowStepName.HUMAN_APPROVAL):
            updated_step = step.model_copy(update={"status": WorkflowStatus.PAUSED})
            steps[idx] = updated_step
            
            log = f"Paused at step '{step.name.value}' for governance review."
            return instance.model_copy(update={
                "steps": steps,
                "status": WorkflowStatus.PAUSED,
                "transition_log": instance.transition_log + [log]
            })

        # 2. Handle Automated Steps (simulate execution success or retry)
        updated_step = step.model_copy(update={"status": WorkflowStatus.RUNNING})
        steps[idx] = updated_step

        # Simulating execution outcome: check for a test parameter trigger in strategy ID
        # e.g., if strategy_id has 'fail_at_<step_name>', simulate execution failure
        fail_trigger = f"fail_at_{step.name.value.lower()}"
        is_failure = fail_trigger in instance.strategy_id.lower()

        if is_failure:
            retries = step.retries + 1
            if retries >= step.max_retries:
                # Failed permanently
                updated_step = step.model_copy(update={
                    "status": WorkflowStatus.FAILED,
                    "retries": retries
                })
                steps[idx] = updated_step
                log = f"Step '{step.name.value}' failed permanently after {retries} retries."
                return instance.model_copy(update={
                    "steps": steps,
                    "status": WorkflowStatus.FAILED,
                    "transition_log": instance.transition_log + [log]
                })
            else:
                # Retry-able failure
                updated_step = step.model_copy(update={
                    "status": WorkflowStatus.PENDING,
                    "retries": retries
                })
                steps[idx] = updated_step
                log = f"Step '{step.name.value}' failed. Triggering retry {retries}/{step.max_retries}."
                return instance.model_copy(update={
                    "steps": steps,
                    "transition_log": instance.transition_log + [log]
                })
        else:
            # Success
            updated_step = step.model_copy(update={
                "status": WorkflowStatus.COMPLETED,
                "completed_at": datetime.now(timezone.utc)
            })
            steps[idx] = updated_step
            next_idx = idx + 1
            next_status = WorkflowStatus.RUNNING if next_idx < len(steps) else WorkflowStatus.COMPLETED
            log = f"Completed step '{step.name.value}' successfully."

            return instance.model_copy(update={
                "steps": steps,
                "current_step_index": next_idx,
                "status": next_status,
                "transition_log": instance.transition_log + [log]
            })

    def submit_approval(self, instance: WorkflowInstance, approval: WorkflowApproval) -> WorkflowInstance:
        """Register governance signature and resume progression if paused."""
        idx = instance.current_step_index
        if idx >= len(instance.steps):
            return instance

        steps = list(instance.steps)
        step = steps[idx]

        if step.name != approval.step_name or step.status != WorkflowStatus.PAUSED:
            logger.warning("Submission rejected: instance is not paused at step '%s'.", approval.step_name.value)
            return instance

        approvals = list(instance.approvals)
        approvals.append(approval)

        if approval.approved:
            # Resumed
            updated_step = step.model_copy(update={
                "status": WorkflowStatus.COMPLETED,
                "completed_at": datetime.now(timezone.utc)
            })
            steps[idx] = updated_step
            next_idx = idx + 1
            next_status = WorkflowStatus.RUNNING if next_idx < len(steps) else WorkflowStatus.COMPLETED
            log = f"Governance review passed at step '{step.name.value}' by '{approval.approver}'."

            updated_instance = instance.model_copy(update={
                "steps": steps,
                "current_step_index": next_idx,
                "status": next_status,
                "approvals": approvals,
                "transition_log": instance.transition_log + [log]
            })

            # Auto-run next step
            return self.execute_next_step(updated_instance)
        else:
            # Rejected/Failed
            updated_step = step.model_copy(update={
                "status": WorkflowStatus.FAILED
            })
            steps[idx] = updated_step
            log = f"Governance review rejected at step '{step.name.value}' by '{approval.approver}'."

            return instance.model_copy(update={
                "steps": steps,
                "status": WorkflowStatus.FAILED,
                "approvals": approvals,
                "transition_log": instance.transition_log + [log]
            })

    def rollback_to_step(self, instance: WorkflowInstance, target_step: WorkflowStepName) -> WorkflowInstance:
        """Revert the workflow state machine back to a previous completed step."""
        steps = list(instance.steps)
        target_idx = -1
        for i, s in enumerate(steps):
            if s.name == target_step:
                target_idx = i
                break

        if target_idx == -1:
            raise ValueError(f"Target step '{target_step.value}' not found in workflow configuration.")

        # Reset all steps from target_idx onwards to PENDING
        for i in range(target_idx, len(steps)):
            steps[i] = steps[i].model_copy(update={
                "status": WorkflowStatus.PENDING,
                "retries": 0,
                "completed_at": None
            })

        log = f"Rolled back workflow status to step '{target_step.value}'."
        return instance.model_copy(update={
            "steps": steps,
            "current_step_index": target_idx,
            "status": WorkflowStatus.RUNNING,
            "transition_log": instance.transition_log + [log]
        })
class_name = "WorkflowEngine"
