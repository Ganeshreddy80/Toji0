"""Universe state persistence repository.

Uses existing storage interfaces from data.storage for persistence.
Maintains a rolling history of scan snapshots for drift analysis.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from universe.core.interfaces import IUniverseRepository
from universe.core.models import UniverseConfig, UniverseSnapshot

logger = logging.getLogger(__name__)


import threading

class UniverseRepository(IUniverseRepository):
    """Persist and retrieve universe scan snapshots.

    Uses an in-memory store by default for dev/test.
    Can be backed by MockPostgresStorageEngine or any IStorageEngine
    for production persistence.
    """

    def __init__(
        self,
        config: UniverseConfig | None = None,
        storage_engine: Any | None = None,
    ) -> None:
        self._config = config or UniverseConfig()
        self._storage = storage_engine
        # In-memory snapshot history (most recent first)
        self._snapshots: list[UniverseSnapshot] = []
        self._lock = threading.RLock()

    def save_snapshot(self, snapshot: UniverseSnapshot) -> None:
        """Persist a universe scan snapshot.

        Maintains a rolling window of max_snapshot_history snapshots.
        If a storage engine is available, also persists to the backend.
        """
        with self._lock:
            self._snapshots.insert(0, snapshot)

            # Trim history
            max_history = self._config.max_snapshot_history
            if len(self._snapshots) > max_history:
                self._snapshots = self._snapshots[:max_history]

        # Persist to storage engine if available
        if self._storage:
            try:
                row = {
                    "scan_id": snapshot.scan_id,
                    "scanned_at": snapshot.scanned_at.isoformat(),
                    "total_discovered": snapshot.total_discovered,
                    "total_after_filter": snapshot.total_after_filter,
                    "tier_distribution": json.dumps(snapshot.tier_distribution),
                    "drift_count": snapshot.drift_count,
                    "data": snapshot.model_dump_json(),
                }
                self._storage.write_rows("universe_snapshots", [row])
            except Exception as e:
                logger.error("Repository: Failed to persist snapshot: %s", e)

        logger.info(
            "Repository: Saved snapshot '%s' (history=%d)",
            snapshot.scan_id,
            len(self._snapshots),
        )

    def load_latest_snapshot(self) -> UniverseSnapshot | None:
        """Load the most recent snapshot."""
        with self._lock:
            if self._snapshots:
                return self._snapshots[0]
        return None

    def load_snapshot_history(
        self, limit: int = 10
    ) -> list[UniverseSnapshot]:
        """Load the last N snapshots for drift analysis."""
        with self._lock:
            return self._snapshots[:limit]

    @property
    def snapshot_count(self) -> int:
        """Total snapshots currently stored."""
        with self._lock:
            return len(self._snapshots)
