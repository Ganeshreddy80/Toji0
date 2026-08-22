"""Configuration repository with PostgreSQL delegation and memory fallbacks.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional
from research_platform.configuration.interfaces import IConfigurationRepository
from research_platform.configuration.models import ConfigurationEntry
from research_platform.platform.service_registry import ServiceRegistry
from research_platform.persistence.repositories.configuration_repository import PostgresConfigurationRepository


class ConfigurationRepository(IConfigurationRepository):
    """Memory-backed repository with PostgreSQL delegation capabilities."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: Dict[str, ConfigurationEntry] = {}

    def _get_pg_repo(self) -> Optional[PostgresConfigurationRepository]:
        registry = ServiceRegistry()
        db = registry.get_service("Database")
        if db:
            from research_platform.persistence.postgres.session import DatabaseSessionManager
            session_manager = DatabaseSessionManager(db)
            return PostgresConfigurationRepository(session_manager)
        return None

    def save_entry(self, entry: ConfigurationEntry) -> None:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            pg_repo.save_parameter(entry.config_id, entry.model_dump())
            
        with self._lock:
            # Set other entries of the same scope to inactive in-memory
            for e in self._entries.values():
                if e.scope == entry.scope and e.config_id != entry.config_id:
                    self._entries[e.config_id] = e.model_copy(update={"is_active": False})
            self._entries[entry.config_id] = entry

    def get_entry(self, config_id: str) -> Optional[ConfigurationEntry]:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            data = pg_repo.get_parameter(config_id)
            if data:
                return ConfigurationEntry(**data)
            return None
            
        with self._lock:
            return self._entries.get(config_id)

    def list_entries(self, scope: Optional[str] = None) -> List[ConfigurationEntry]:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            # In database fallback mode, we retrieve all parameters and filter
            models = pg_repo.list_all()
            entries = []
            for m in models:
                if isinstance(m.value, dict):
                    entries.append(ConfigurationEntry(**m.value))
            if scope:
                return [e for e in entries if e.scope == scope]
            return entries
            
        with self._lock:
            vals = list(self._entries.values())
            if scope:
                return [e for e in vals if e.scope == scope]
            return vals
