"""Orchestrator driving system state checkpoints and recoveries.
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional

from research_platform.recovery.models import Checkpoint, Snapshot, SnapshotType, RecoverySession
from research_platform.recovery.repository import RecoveryRepository
from research_platform.recovery.checkpoint_manager import CheckpointManager
from research_platform.recovery.snapshot_manager import SnapshotManager
from research_platform.recovery.recovery_engine import RecoveryEngine

logger = logging.getLogger(__name__)


class RecoveryOrchestrator:
    """Public boundary coordinator trigger procedures."""

    def __init__(self, container: Any) -> None:
        self.container = container
        try:
            self.repository = container.resolve("RecoveryRepository")
            if not self.repository:
                self.repository = RecoveryRepository()
        except Exception:
            self.repository = RecoveryRepository()
        self.checkpoint_manager = CheckpointManager(container, self.repository)
        self.snapshot_manager = SnapshotManager(container, self.repository)
        self.recovery_engine = RecoveryEngine(container)

    def boot(self) -> bool:
        """Run startup recovery procedures. Return True if recovery was successful."""
        logger.info("Orchestrator: Initiating system recovery boot sequence...")
        return self.recovery_engine.execute_recovery()

    def trigger_checkpoint(self) -> Checkpoint:
        """Manually trigger state snapshot checkmarks."""
        checkpoint = self.checkpoint_manager.create_checkpoint()
        self.checkpoint_manager.save_checkpoint(checkpoint)
        return checkpoint

    def trigger_snapshot(self, snapshot_type: SnapshotType, description: Optional[str] = None) -> Snapshot:
        """Manually trigger detailed snapshots backups."""
        return self.snapshot_manager.create_snapshot(snapshot_type, description)

    def restore_from_snapshot(self, snapshot_id: str) -> None:
        """Restore active platform states to the snapshot checkpoint."""
        self.snapshot_manager.restore_snapshot(snapshot_id)

    def get_history(self) -> List[RecoverySession]:
        return self.repository.get_recovery_history()
