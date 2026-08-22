"""Thread-safe memory repository caching deployment records and lock states.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional
from research_platform.deployment.interfaces import IDeploymentRepository
from research_platform.deployment.models import StrategyDeployment, DeploymentLock


class DeploymentRepository(IDeploymentRepository):
    """Memory-backed, thread-safe repository for deployments records."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._deployments: Dict[str, StrategyDeployment] = {}
        self._lock_state = DeploymentLock(is_locked=False)

    def save_deployment(self, deployment: StrategyDeployment) -> None:
        with self._lock:
            self._deployments[deployment.deployment_id] = deployment

    def get_deployment(self, deployment_id: str) -> Optional[StrategyDeployment]:
        with self._lock:
            return self._deployments.get(deployment_id)

    def list_deployments(self) -> List[StrategyDeployment]:
        with self._lock:
            return list(self._deployments.values())

    def save_lock(self, lock: DeploymentLock) -> None:
        with self._lock:
            self._lock_state = lock

    def get_lock(self) -> DeploymentLock:
        with self._lock:
            return self._lock_state
