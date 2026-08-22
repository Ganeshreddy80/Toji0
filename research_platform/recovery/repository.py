"""State Recovery repository interface wrapping database configurations table delegation.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Dict, Any, Optional, List
from research_platform.platform.service_registry import ServiceRegistry
from research_platform.persistence.repositories.configuration_repository import PostgresConfigurationRepository
from research_platform.recovery.models import Checkpoint, Snapshot, RecoverySession

logger = logging.getLogger(__name__)


class RecoveryRepository:
    """Thread-safe persistence coordinator saving checkpoints, snapshots, and recovery histories."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._checkpoints: Dict[str, Any] = {}
        self._snapshots: Dict[str, Any] = {}
        self._history: List[RecoverySession] = []

    def _get_pg_repo(self) -> Optional[PostgresConfigurationRepository]:
        registry = ServiceRegistry()
        db = registry.get_service("Database")
        if db:
            from research_platform.persistence.postgres.session import DatabaseSessionManager
            session_manager = DatabaseSessionManager(db)
            return PostgresConfigurationRepository(session_manager)
        return None

    def save_checkpoint(self, checkpoint: Checkpoint) -> None:
        checkpoint_data = checkpoint.model_dump(mode="json")

        with self._lock:
            self._checkpoints[checkpoint.checkpoint_id] = checkpoint_data
            self._checkpoints["latest"] = checkpoint_data

        pg_repo = self._get_pg_repo()
        if pg_repo:
            try:
                pg_repo.save_parameter("checkpoint_latest", checkpoint_data)
                pg_repo.save_parameter(f"checkpoint_{checkpoint.checkpoint_id}", checkpoint_data)
            except Exception as e:
                logger.error("Failed to save checkpoint to postgres: %s", e)

    def get_latest_checkpoint(self) -> Optional[Checkpoint]:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            try:
                val = pg_repo.get_parameter("checkpoint_latest")
                if val:
                    return Checkpoint.model_validate(val)
            except Exception as e:
                logger.error("Failed to load latest checkpoint from postgres: %s", e)

        with self._lock:
            data = self._checkpoints.get("latest")
            return Checkpoint.model_validate(data) if data else None

    def save_snapshot(self, snapshot: Snapshot) -> None:
        snapshot_data = snapshot.model_dump(mode="json")
        with self._lock:
            self._snapshots[snapshot.snapshot_id] = snapshot_data

        pg_repo = self._get_pg_repo()
        if pg_repo:
            try:
                pg_repo.save_parameter(f"snapshot_{snapshot.snapshot_id}", snapshot_data)
            except Exception as e:
                logger.error("Failed to save snapshot to postgres: %s", e)

    def get_snapshot(self, snapshot_id: str) -> Optional[Snapshot]:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            try:
                val = pg_repo.get_parameter(f"snapshot_{snapshot_id}")
                if val:
                    return Snapshot.model_validate(val)
            except Exception:
                pass

        with self._lock:
            data = self._snapshots.get(snapshot_id)
            return Snapshot.model_validate(data) if data else None

    def list_snapshots(self) -> List[Snapshot]:
        with self._lock:
            return [Snapshot.model_validate(x) for x in self._snapshots.values()]

    def log_recovery_session(self, session: RecoverySession) -> None:
        with self._lock:
            self._history.append(session)
            
        pg_repo = self._get_pg_repo()
        if pg_repo:
            try:
                history_data = [s.model_dump(mode="json") for s in self._history]
                pg_repo.save_parameter("recovery_history", history_data)
            except Exception:
                pass

    def get_recovery_history(self) -> List[RecoverySession]:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            try:
                val = pg_repo.get_parameter("recovery_history")
                if val:
                    return [RecoverySession.model_validate(s) for s in val]
            except Exception:
                pass

        with self._lock:
            return list(self._history)
