"""Mermaid visualization generator for workflow instances.
"""

from __future__ import annotations

from research_platform.workflow_orchestration.models import WorkflowInstance, WorkflowStatus

class WorkflowVisualizer:
    """Generates Mermaid diagrams representing active workflow execution statuses."""

    def generate_mermaid_diagram(self, instance: WorkflowInstance) -> str:
        """Construct Mermaid graph string highlighting the active step."""
        lines = ["graph LR"]

        # Loop through steps to write transitions
        for i in range(len(instance.steps) - 1):
            s1 = instance.steps[i]
            s2 = instance.steps[i + 1]
            lines.append(f"  {s1.name.value} --> {s2.name.value}")

        # Add node styles depending on status
        for s in instance.steps:
            if s.status == WorkflowStatus.COMPLETED:
                lines.append(f"  style {s.name.value} fill:#85e3b2,stroke:#333,stroke-width:1px")
            elif s.status == WorkflowStatus.PAUSED:
                lines.append(f"  style {s.name.value} fill:#ffcc80,stroke:#d35400,stroke-width:2px")
            elif s.status == WorkflowStatus.FAILED:
                lines.append(f"  style {s.name.value} fill:#ff8a80,stroke:#c0392b,stroke-width:2px")
            elif s.status == WorkflowStatus.RUNNING:
                lines.append(f"  style {s.name.value} fill:#80deea,stroke:#00838f,stroke-width:2px")
            else:
                lines.append(f"  style {s.name.value} fill:#eeeeee,stroke:#999,stroke-width:1px")

        # Highlight current active index
        idx = instance.current_step_index
        if idx < len(instance.steps):
            active_step = instance.steps[idx]
            lines.append(f"  %% Active step: {active_step.name.value}")

        return "\n".join(lines)
