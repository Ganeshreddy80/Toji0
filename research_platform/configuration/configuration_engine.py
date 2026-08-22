"""Configuration engine managing version increments and updates overrides.
"""

from __future__ import annotations

import uuid
from typing import Dict, Any
from research_platform.configuration.models import ConfigurationEntry
from research_platform.configuration.repository import ConfigurationRepository


class ConfigurationEngine:
    """Creates versioned configuration entries."""

    def __init__(self, repo: ConfigurationRepository) -> None:
        self._repo = repo

    def create_update(self, scope: str, params: Dict[str, Any]) -> ConfigurationEntry:
        if scope not in ["GLOBAL", "STRATEGY", "RISK", "EXCHANGE"]:
            raise ValueError("Invalid Configuration Scope: Scope must be GLOBAL, STRATEGY, RISK, or EXCHANGE.")

        # Determine version increment
        actives = [e for e in self._repo.list_entries(scope) if e.is_active]
        next_ver = 1
        if actives:
            next_ver = actives[0].version + 1

        return ConfigurationEntry(
            config_id=f"cfg-{uuid.uuid4().hex[:8]}",
            scope=scope,
            params=params,
            version=next_ver
        )
