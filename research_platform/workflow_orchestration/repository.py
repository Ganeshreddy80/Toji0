"""Thread-safe, append-only repository for storing workflow instances.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional
from research_platform.workflow_orchestration.interfaces import IWorkflowRepository
from research_platform.workflow_orchestration.models import WorkflowInstance


class WorkflowRepository(IWorkflowRepository):
    """Memory-backed, thread-safe repository implementation."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._instances: Dict[str, WorkflowInstance] = {}

    def save_instance(self, instance: WorkflowInstance) -> None:
        with self._lock:
            self._instances[instance.instance_id] = instance

    def get_instance(self, instance_id: str) -> Optional[WorkflowInstance]:
        with self._lock:
            return self._instances.get(instance_id)

    def list_instances(self) -> List[WorkflowInstance]:
        with self._lock:
            return list(self._instances.values())
