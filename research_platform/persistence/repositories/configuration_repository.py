"""PostgreSQL configuration parameters repository.
"""

from __future__ import annotations

from typing import Dict, Any, Optional

from research_platform.persistence.postgres.base_repository import BaseRepository
from research_platform.persistence.postgres.migrations import ConfigurationModel


class PostgresConfigurationRepository(BaseRepository):
    """PostgreSQL-backed Configuration parameters repository."""

    def __init__(self, session_manager) -> None:
        super().__init__(session_manager, ConfigurationModel)

    def save_parameter(self, key: str, value: Any) -> None:
        model = self.get(key)
        if model:
            self.update(key, {"value": value})
        else:
            new_model = ConfigurationModel(key=key, value=value)
            self.create(new_model)

    def get_parameter(self, key: str) -> Optional[Any]:
        model = self.get(key)
        if model:
            return model.value
        return None
