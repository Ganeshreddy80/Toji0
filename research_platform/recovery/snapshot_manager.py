"""Snapshot Manager coordinator.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional

from research_platform.recovery.interfaces import ISnapshotManager
from research_platform.recovery.models import Snapshot, SnapshotType
from research_platform.recovery.checkpoint_manager import CheckpointManager

logger = logging.getLogger(__name__)


class SnapshotManager(ISnapshotManager):
    """Orchestrates creation, cataloging, and restoration of snapshots."""

    def __init__(self, container: Any, repository: Any) -> None:
        self.container = container
        self.repository = repository
        self.checkpoint_manager = CheckpointManager(container, repository)

    def create_snapshot(self, snapshot_type: SnapshotType, description: Optional[str] = None) -> Snapshot:
        logger.info("Creating snapshot trigger type: %s", snapshot_type)
        
        # 1. Capture current checkpoint
        checkpoint = self.checkpoint_manager.create_checkpoint()
        self.checkpoint_manager.save_checkpoint(checkpoint)

        snapshot = Snapshot(
            snapshot_id=str(uuid.uuid4()),
            checkpoint_id=checkpoint.checkpoint_id,
            snapshot_type=snapshot_type,
            timestamp=datetime.now(timezone.utc),
            description=description,
            data=checkpoint.model_dump()
        )

        self.repository.save_snapshot(snapshot)
        return snapshot

    def restore_snapshot(self, snapshot_id: str) -> None:
        logger.info("Restoring snapshot: %s...", snapshot_id)
        snapshot = self.repository.get_snapshot(snapshot_id)
        if not snapshot:
            raise ValueError(f"Snapshot ID {snapshot_id} not found.")

        # Reconstruct checkpoint and load via recovery engines
        from research_platform.recovery.recovery_engine import RecoveryEngine
        engine = RecoveryEngine(self.container)
        
        # Override latest checkpoint temporarily to force recovery from snapshot data
        checkpoint_data = snapshot.data
        from research_platform.recovery.models import Checkpoint
        checkpoint = Checkpoint.model_validate(checkpoint_data)
        
        # Execute restoration stages
        engine.restore_checkpoint_state(checkpoint)

    def list_snapshots(self) -> List[Snapshot]:
        return self.repository.list_snapshots()
