"""R51 Central Configuration Manager.
"""

from __future__ import annotations

import logging
import threading
import uuid
from typing import Any, Dict, Optional

from research_platform.config.interfaces import IConfigManager
from research_platform.config.models import CentralConfig
from research_platform.config.config_loader import ConfigLoader
from research_platform.config.config_validator import ConfigValidator
from research_platform.config.repository import ConfigRepository
from research_platform.config.hot_reload import ConfigHotReloader

logger = logging.getLogger(__name__)


class ConfigManager(IConfigManager):
    """Central entry coordinator for active configurations, hot-reloads, and Postgres persists."""

    def __init__(self, yaml_path: Optional[str] = None, default_profile: str = "PAPER") -> None:
        self.yaml_path = yaml_path
        self.loader = ConfigLoader(default_profile)
        self.repository = ConfigRepository()
        self._lock = threading.Lock()
        
        # Load configuration on initialization
        raw_dict = self.loader.load_configuration(yaml_path=self.yaml_path)
        self._active_config = CentralConfig.model_validate(raw_dict)
        
        # Persist initial config to DB
        self.repository.save_central_config(self._active_config)

        # Hot reloader
        self.reloader: Optional[ConfigHotReloader] = None
        if yaml_path:
            self.reloader = ConfigHotReloader(file_path=yaml_path, callback=self.reload)
            self.reloader.start()

    def get_config(self) -> CentralConfig:
        with self._lock:
            return self._active_config

    def apply_overrides(self, overrides: Dict[str, Any]) -> None:
        """Merges new overrides, validates, saves to DB, and updates in-memory config."""
        logger.info("Applying runtime overrides: %s", overrides)
        with self._lock:
            current_dict = self._active_config.model_dump()
            merged_dict = self.loader.merge_dicts(current_dict, overrides)
            
            # Validate
            errors = ConfigValidator.validate(merged_dict)
            if errors:
                raise ValueError(f"Override validation failed: {errors}")
                
            self._active_config = CentralConfig.model_validate(merged_dict)
            self.repository.save_central_config(self._active_config)

        # Publish override event
        try:
            # Resolve EventBus to dispatch event
            from research_platform.platform.service_registry import ServiceRegistry
            registry = ServiceRegistry()
            eb = registry.get_service("EventBus")
            if eb:
                from research_platform.config.events import ConfigOverridden
                event = ConfigOverridden(
                    event_id=str(uuid.uuid4()),
                    overridden_keys=list(overrides.keys())
                )
                eb.publish("ConfigOverridden", event.model_dump())
        except Exception:
            pass

    def reload(self) -> None:
        """Reads configuration file and merges overrides, updating configuration in place."""
        logger.info("Hot-reloading TOJI V1 configurations...")
        with self._lock:
            raw_dict = self.loader.load_configuration(yaml_path=self.yaml_path)
            self._active_config = CentralConfig.model_validate(raw_dict)
            self.repository.save_central_config(self._active_config)

        # Publish reload event
        try:
            from research_platform.platform.service_registry import ServiceRegistry
            registry = ServiceRegistry()
            eb = registry.get_service("EventBus")
            if eb:
                from research_platform.config.events import ConfigHotReloaded
                from datetime import datetime, timezone
                event = ConfigHotReloaded(
                    event_id=str(uuid.uuid4()),
                    updated_at=datetime.now(timezone.utc)
                )
                eb.publish("ConfigHotReloaded", event.model_dump())
        except Exception:
            pass

    def shutdown(self) -> None:
        """Stop background hot-reload monitor thread."""
        if self.reloader:
            self.reloader.stop()
