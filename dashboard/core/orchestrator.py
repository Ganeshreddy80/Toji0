"""Dashboard Orchestrator for managing snapshot storage and updates."""

from __future__ import annotations

import logging
from typing import Any

from dashboard.core.exceptions import OrchestratorError
from dashboard.core.interfaces import IDashboardRepository, IDashboardStateStore
from dashboard.core.models import DashboardSnapshot

logger = logging.getLogger(__name__)


class DashboardOrchestrator:
    """Coordinates compiling, updating, and persisting dashboard snapshots."""

    def __init__(self) -> None:
        self._state_store: IDashboardStateStore | None = None
        self._repository: IDashboardRepository | None = None

    def initialize(
        self,
        state_store: IDashboardStateStore,
        repository: IDashboardRepository,
    ) -> None:
        """Inject dependencies into the orchestrator."""
        self._state_store = state_store
        self._repository = repository

    def process_snapshot(self, snapshot: DashboardSnapshot) -> None:
        """Update state store and persist snapshot to repository."""
        if not self._state_store or not self._repository:
            raise OrchestratorError("DashboardOrchestrator is not initialized.")

        try:
            # 1. Update state store
            self._state_store.update_snapshot(snapshot)

            # 2. Save to repository
            self._repository.save_snapshot(snapshot)
        except Exception as e:
            logger.error("Orchestrator: Failed to process snapshot: %s", e)
            raise OrchestratorError(f"Failed to process snapshot: {e}") from e
