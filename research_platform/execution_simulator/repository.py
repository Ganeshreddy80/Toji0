"""Thread-safe memory repository caching simulated executions.
"""

from __future__ import annotations

import threading
from typing import Dict, Optional
from research_platform.execution_simulator.interfaces import IExecutionSimulatorRepository
from research_platform.execution_simulator.models import SimulatedExecution


class ExecutionSimulatorRepository(IExecutionSimulatorRepository):
    """Memory-backed, thread-safe repository for simulated executions."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._executions: Dict[str, SimulatedExecution] = {}

    def save_execution(self, execution: SimulatedExecution) -> None:
        with self._lock:
            self._executions[execution.execution_id] = execution

    def get_execution(self, execution_id: str) -> Optional[SimulatedExecution]:
        with self._lock:
            return self._executions.get(execution_id)
