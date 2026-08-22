"""Workspace manager loading workspace states.
"""

from __future__ import annotations

from typing import List
from research_platform.toji_os.models import WorkspaceState


class WorkspaceManager:
    """Manages files and strategy files indices inside active workspaces."""

    def load_workspace(
        self,
        root_path: str,
        corpus_name: str,
        strategies: List[str]
    ) -> WorkspaceState:
        return WorkspaceState(
            workspace_root=root_path,
            corpus_name=corpus_name,
            active_strategies=strategies
        )
