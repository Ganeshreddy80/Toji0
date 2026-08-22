"""Abstract contracts for TOJI Operating System.
"""

from __future__ import annotations

import abc
from typing import Optional
from research_platform.toji_os.models import OSSession, WorkspaceState


class ITOJIOSRepository(abc.ABC):
    """Abstract contract for persisting OS states."""

    @abc.abstractmethod
    def save_session(self, session: OSSession) -> None:
        """Persist OS control session details."""

    @abc.abstractmethod
    def get_session(self, session_id: str) -> Optional[OSSession]:
        """Retrieve OS control session details by ID."""

    @abc.abstractmethod
    def save_workspace(self, state: WorkspaceState) -> None:
        """Persist workspace state config."""

    @abc.abstractmethod
    def get_workspace(self, root_path: str) -> Optional[WorkspaceState]:
        """Retrieve workspace state by root path."""
