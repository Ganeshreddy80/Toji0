"""R51 Configuration database repository delegation.
"""

from __future__ import annotations

import logging
import threading
from typing import Dict, Any, Optional
from research_platform.platform.service_registry import ServiceRegistry
from research_platform.persistence.repositories.configuration_repository import PostgresConfigurationRepository
from research_platform.config.models import CentralConfig

logger = logging.getLogger(__name__)


class ConfigRepository:
    """Coordinates persistence updates of active configurations in PostgreSQL."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cache: Dict[str, Any] = {}

    def _get_pg_repo(self) -> Optional[PostgresConfigurationRepository]:
        registry = ServiceRegistry()
        db = registry.get_service("Database")
        if db:
            from research_platform.persistence.postgres.session import DatabaseSessionManager
            session_manager = DatabaseSessionManager(db)
            return PostgresConfigurationRepository(session_manager)
        return None

    def save_central_config(self, config: CentralConfig) -> None:
        config_data = config.model_dump()
        with self._lock:
            self._cache["central_config"] = config_data

        pg_repo = self._get_pg_repo()
        if pg_repo:
            try:
                pg_repo.save_parameter("central_config", config_data)
            except Exception as e:
                logger.error("Failed to persist configuration to PostgreSQL: %s", e)

    def load_central_config(self) -> Optional[CentralConfig]:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            try:
                val = pg_repo.get_parameter("central_config")
                if val:
                    return CentralConfig.model_validate(val)
            except Exception as e:
                logger.error("Failed to load configuration from PostgreSQL: %s", e)

        with self._lock:
            data = self._cache.get("central_config")
            return CentralConfig.model_validate(data) if data else None
