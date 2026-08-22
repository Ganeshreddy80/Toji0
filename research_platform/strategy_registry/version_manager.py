"""Version manager tracking strategy git commit hashes and version progression.
"""

from __future__ import annotations

import logging
from typing import Dict, List
from research_platform.strategy_registry.interfaces import IVersionManager

logger = logging.getLogger(__name__)


class VersionManager(IVersionManager):
    """Logs git hash changes and maintains historical version updates maps."""

    def __init__(self) -> None:
        self._versions: Dict[str, List[tuple[str, str]]] = {}

    def log_version_update(self, strategy_id: str, version: str, git_hash: str) -> None:
        if strategy_id not in self._versions:
            self._versions[strategy_id] = []
        self._versions[strategy_id].append((version, git_hash))
        logger.info("VersionManager: Logged version %s (hash: %s) for strategy %s", version, git_hash, strategy_id)

    def get_version_history(self, strategy_id: str) -> List[tuple[str, str]]:
        return list(self._versions.get(strategy_id, []))
class IVersionRepresentation:
    pass
