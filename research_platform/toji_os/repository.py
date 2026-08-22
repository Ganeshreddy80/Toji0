"""Thread-safe memory repository caching OS sessions and workspace states.
"""

from __future__ import annotations

import threading
from typing import Dict, Optional
from research_platform.toji_os.interfaces import ITOJIOSRepository
from research_platform.toji_os.models import OSSession, WorkspaceState


class TOJIOSRepository(ITOJIOSRepository):
    """Memory-backed, thread-safe repository for OS configurations."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: Dict[str, OSSession] = {}
        self._workspaces: Dict[str, WorkspaceState] = {}

    def save_session(self, session: OSSession) -> None:
        with self._lock:
            self._sessions[session.session_id] = session

    def get_session(self, session_id: str) -> Optional[OSSession]:
        with self._lock:
            return self._sessions.get(session_id)

    def save_workspace(self, state: WorkspaceState) -> None:
        with self._lock:
            self._workspaces[state.workspace_root] = state

    def get_workspace(self, root_path: str) -> Optional[WorkspaceState]:
        with self._lock:
            return self._workspaces.get(root_path)
