"""Database repository saving active session profiles and snapshots.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional

from research_platform.live_trading.models import LiveTradingSession, RecoveryCheckpoint, TradingSnapshot


class LiveTradingRepository:
    """Memory database repository for sessions and states snapshots."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: Dict[str, LiveTradingSession] = {}
        self._checkpoints: Dict[str, RecoveryCheckpoint] = {}
        self._snapshots: Dict[str, List[TradingSnapshot]] = {}

    def save_session(self, session: LiveTradingSession) -> None:
        with self._lock:
            self._sessions[session.session_id] = session

    def get_session(self, session_id: str) -> Optional[LiveTradingSession]:
        with self._lock:
            return self._sessions.get(session_id)

    def save_checkpoint(self, checkpoint: RecoveryCheckpoint) -> None:
        with self._lock:
            self._checkpoints[checkpoint.session_id] = checkpoint

    def get_checkpoint(self, session_id: str) -> Optional[RecoveryCheckpoint]:
        with self._lock:
            return self._checkpoints.get(session_id)

    def save_snapshot(self, session_id: str, snapshot: TradingSnapshot) -> None:
        with self._lock:
            if session_id not in self._snapshots:
                self._snapshots[session_id] = []
            self._snapshots[session_id].append(snapshot)

    def list_snapshots(self, session_id: str) -> List[TradingSnapshot]:
        with self._lock:
            return list(self._snapshots.get(session_id, []))
