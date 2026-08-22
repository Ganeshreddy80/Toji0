"""State Recovery abstract interface contracts.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from research_platform.recovery.models import Checkpoint, Snapshot, SnapshotType


class ICheckpointManager(ABC):
    """Abstract interface managing periodic state checkpointing operations."""

    @abstractmethod
    def create_checkpoint(self) -> Checkpoint:
        """Capture and serialize complete subsystem status records."""
        pass

    @abstractmethod
    def save_checkpoint(self, checkpoint: Checkpoint) -> None:
        """Persist the checkpoint into storage."""
        pass

    @abstractmethod
    def get_latest_checkpoint(self) -> Optional[Checkpoint]:
        """Fetch the most recent persisted checkpoint."""
        pass


class ISnapshotManager(ABC):
    """Abstract interface managing custom triggered database snapshots."""

    @abstractmethod
    def create_snapshot(self, snapshot_type: SnapshotType, description: Optional[str] = None) -> Snapshot:
        """Generate and persist a target state snapshot."""
        pass

    @abstractmethod
    def restore_snapshot(self, snapshot_id: str) -> None:
        """Restore active platform states from a snapshot record."""
        pass

    @abstractmethod
    def list_snapshots(self) -> List[Snapshot]:
        """Retrieve all persisted snapshots."""
        pass


class IRecoveryEngine(ABC):
    """Abstract interface coordinating startup recovery tasks."""

    @abstractmethod
    def execute_recovery(self) -> bool:
        """Run the sequenced stages recovery boot path. Return True if successful."""
        pass
