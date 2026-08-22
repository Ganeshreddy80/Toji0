"""Configuration Manager orchestrator coordinating validations, triggers, and audits.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from toji_platform.core.event_bus import IEventBus

from research_platform.configuration.interfaces import IConfigurationEngine
from research_platform.configuration.models import ConfigurationEntry, ConfigurationSnapshot
from research_platform.configuration.repository import ConfigurationRepository
from research_platform.configuration.configuration_engine import ConfigurationEngine as Engine
from research_platform.configuration.validator import Validator
from research_platform.configuration.hot_reload import HotReload
from research_platform.configuration.events import ConfigurationUpdated, ConfigurationReloaded

logger = logging.getLogger(__name__)


class ConfigurationOrchestrator(IConfigurationEngine):
    """Central orchestrator managing hot-reloading configurations variables."""

    def __init__(self, event_bus: IEventBus, container: Optional[Any] = None) -> None:
        self._event_bus = event_bus
        self._container = container
        
        self._repo = ConfigurationRepository()
        self._engine = Engine(self._repo)
        self._validator = Validator()
        self._reload = HotReload()

    @property
    def repository(self) -> ConfigurationRepository:
        return self._repo

    @property
    def validator(self) -> Validator:
        return self._validator

    @property
    def hot_reload(self) -> HotReload:
        return self._reload

    # ── Downstream Subsystem Resolvers ───────────────────────────────

    def _resolve(self, key: str) -> Optional[Any]:
        if self._container and self._container.has(key):
            try:
                return self._container.resolve(key)
            except Exception as e:
                logger.error("ConfigurationManager: Failed to resolve registry key %s: %s", key, e)
        return None

    def _get_memory_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator")

    def _get_kg_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator")

    def _get_ops_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.operations_center.operations_orchestrator.OperationsOrchestrator")

    # ── IConfigurationEngine Action ──────────────────────────────────

    def update_config(self, scope: str, params: Dict[str, Any]) -> ConfigurationEntry:
        """Update configurations parameters, validating parameters layouts."""
        self._validator.validate(scope, params)

        entry = self._engine.create_update(scope, params)
        self._repo.save_entry(entry)

        self._event_bus.publish(ConfigurationUpdated(payload={"config_id": entry.config_id}))
        self._log_downstream_registries(entry, "Configuration Updated")

        return entry

    def trigger_hot_reload(self) -> None:
        self._reload.reload_configurations()
        self._event_bus.publish(ConfigurationReloaded(payload={"timestamp": datetime.now(timezone.utc).isoformat()}))

    def get_active_config(self, scope: str) -> Optional[ConfigurationEntry]:
        actives = [e for e in self._repo.list_entries(scope) if e.is_active]
        return actives[0] if actives else None

    def create_snapshot(self) -> ConfigurationSnapshot:
        return ConfigurationSnapshot(
            timestamp=datetime.now(timezone.utc),
            entries=self._repo.list_entries()
        )

    def _log_downstream_registries(self, entry: ConfigurationEntry, message: str) -> None:
        # 1. Institutional Memory (R16)
        mem = self._get_memory_orchestrator()
        if mem:
            try:
                mem.publish_memory("configuration", {
                    "config_id": entry.config_id,
                    "scope": entry.scope,
                    "version": entry.version,
                    "message": message
                })
            except Exception as e:
                logger.error("ConfigurationManager Audit: Failed to write to memory: %s", e)

        # 2. Knowledge Graph (R17)
        kg = self._get_kg_orchestrator()
        if kg:
            try:
                kg.register_node(
                    node_id=entry.config_id,
                    node_type="CONFIGURATION",
                    subsystem="configuration",
                    event="ConfigurationUpdated",
                    author="configuration",
                    properties={"scope": entry.scope, "version": entry.version}
                )
            except Exception as e:
                logger.error("ConfigurationManager Audit: Failed to write to graph: %s", e)

        # 3. Operations Center (R30.5)
        ops = self._get_ops_orchestrator()
        if ops:
            try:
                ops.compile_dashboard_snapshot()
            except Exception as e:
                logger.error("ConfigurationManager: Failed to refresh operations center: %s", e)
