"""R51 Configuration change event models.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Any
from pydantic import BaseModel, Field


class ConfigEvent(BaseModel):
    """Base event representation for config changes."""
    event_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ConfigLoaded(ConfigEvent):
    """Emitted when configuration is loaded on boot."""
    profile: str
    version: int


class ConfigOverridden(ConfigEvent):
    """Emitted when dynamic overrides are applied at runtime."""
    overridden_keys: list[str]


class ConfigHotReloaded(ConfigEvent):
    """Emitted when configuration file updates trigger reloads."""
    updated_at: datetime
