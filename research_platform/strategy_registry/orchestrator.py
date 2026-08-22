"""Strategy Registry orchestrator coordinating validations, audits, and registry logs.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, List, Optional

from toji_platform.core.event_bus import IEventBus

from research_platform.strategy_registry.interfaces import IStrategyRegistry
from research_platform.strategy_registry.models import RegisteredStrategy, StrategyRegistryStatistics, StrategyRegistrySnapshot
from research_platform.strategy_registry.repository import StrategyRegistryRepository
from research_platform.strategy_registry.registry_engine import RegistryEngine
from research_platform.strategy_registry.search_engine import SearchEngine
from research_platform.strategy_registry.version_manager import VersionManager
from research_platform.strategy_registry.events import StrategyRegistered, StrategyRegistrySnapshotCreated

logger = logging.getLogger(__name__)


class StrategyRegistryOrchestrator(IStrategyRegistry):
    """Central orchestrator managing registered strategies portfolios."""

    def __init__(self, event_bus: IEventBus, container: Optional[Any] = None) -> None:
        self._event_bus = event_bus
        self._container = container
        
        self._repo = StrategyRegistryRepository()
        self._engine = RegistryEngine()
        self._search = SearchEngine(self._repo)
        self._version = VersionManager()

    @property
    def repository(self) -> StrategyRegistryRepository:
        return self._repo

    @property
    def search_engine(self) -> SearchEngine:
        return self._search

    @property
    def version_manager(self) -> VersionManager:
        return self._version

    # ── Downstream Subsystem Resolvers ───────────────────────────────

    def _resolve(self, key: str) -> Optional[Any]:
        if self._container and self._container.has(key):
            try:
                return self._container.resolve(key)
            except Exception as e:
                logger.error("StrategyRegistry: Failed to resolve registry key %s: %s", key, e)
        return None

    def _get_memory_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator")

    def _get_kg_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator")

    def _get_ops_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.operations_center.operations_orchestrator.OperationsOrchestrator")

    # ── IStrategyRegistry Action ─────────────────────────────────────

    def register_strategy(
        self,
        strategy_id: str,
        name: str,
        description: str,
        version: str,
        git_hash: str,
        dependencies: List[str],
        tags: List[str],
        categories: List[str],
        author: str,
        asset_class: str,
        risk_profile: str,
        capabilities: List[str]
    ) -> RegisteredStrategy:
        """Register a strategy, validating inputs and persisting details."""
        strategy = self._engine.create_registration(
            strategy_id=strategy_id,
            name=name,
            description=description,
            version=version,
            git_hash=git_hash,
            dependencies=dependencies,
            tags=tags,
            categories=categories,
            author=author,
            asset_class=asset_class,
            risk_profile=risk_profile,
            capabilities=capabilities
        )
        self._repo.save_strategy(strategy)
        self._version.log_version_update(strategy_id, version, git_hash)
        
        self._event_bus.publish(StrategyRegistered(payload={"strategy_id": strategy_id}))
        self._log_downstream_registries(strategy, "Strategy Registered")

        return strategy

    def get_statistics(self) -> StrategyRegistryStatistics:
        strats = self._repo.list_strategies()
        active = len([s for s in strats if s.status == "ACTIVE"])
        retired = len([s for s in strats if s.status == "RETIRED"])
        return StrategyRegistryStatistics(
            total_registered=len(strats),
            active_count=active,
            retired_count=retired
        )

    def create_snapshot(self) -> StrategyRegistrySnapshot:
        snap = StrategyRegistrySnapshot(
            timestamp=datetime.now(timezone.utc),
            strategies=self._repo.list_strategies()
        )
        self._event_bus.publish(StrategyRegistrySnapshotCreated(payload={"timestamp": snap.timestamp.isoformat()}))
        return snap

    def _log_downstream_registries(self, strategy: RegisteredStrategy, message: str) -> None:
        # 1. Institutional Memory (R16)
        mem = self._get_memory_orchestrator()
        if mem:
            try:
                mem.publish_memory("strategy_registry", {
                    "strategy_id": strategy.strategy_id,
                    "name": strategy.name,
                    "git_hash": strategy.git_hash,
                    "message": message
                })
            except Exception as e:
                logger.error("StrategyRegistry Audit: Failed to write to memory: %s", e)

        # 2. Knowledge Graph (R17)
        kg = self._get_kg_orchestrator()
        if kg:
            try:
                kg.register_node(
                    node_id=strategy.strategy_id,
                    node_type="STRATEGY",
                    subsystem="strategy_registry",
                    event="StrategyRegistered",
                    author="strategy_registry",
                    properties={"name": strategy.name, "active_version": strategy.active_version}
                )
            except Exception as e:
                logger.error("StrategyRegistry Audit: Failed to write to graph: %s", e)

        # 3. Operations Center (R30.5)
        ops = self._get_ops_orchestrator()
        if ops:
            try:
                ops.compile_dashboard_snapshot()
            except Exception as e:
                logger.error("StrategyRegistry: Failed to refresh operations center: %s", e)
