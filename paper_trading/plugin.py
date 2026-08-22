"""Kernel Plugin integration for Paper Trading Subsystem (Sprint 9A)."""

from __future__ import annotations

import logging
from typing import List, Optional

from paper_trading.models.paper_models import PaperSessionStatus
from paper_trading.orchestrator import PaperOrchestrator
from toji_platform.core.plugin_manager.interfaces import IPlugin
from toji_platform.core.types import HealthStatus, ModuleState, PluginId

logger = logging.getLogger(__name__)


class PaperTradingPlugin(IPlugin):
    """Kernel Plugin wrapping Paper Trading Subsystem lifecycle."""

    def __init__(self, orchestrator: Optional[PaperOrchestrator] = None) -> None:
        self._orchestrator = orchestrator or PaperOrchestrator()
        self._state = ModuleState.UNINITIALIZED
        self._plugin_id = PluginId("paper_trading")

    @property
    def plugin_id(self) -> PluginId:
        return self._plugin_id

    @property
    def name(self) -> str:
        return "PaperTradingSubsystem"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def dependencies(self) -> List[PluginId]:
        return [PluginId("event_bus")]

    @property
    def state(self) -> ModuleState:
        return self._state

    def initialize(self) -> None:
        """Initialize plugin resources."""
        if self._state == ModuleState.READY:
            return
        self._state = ModuleState.INITIALIZING
        logger.info("Initializing Paper Trading Plugin...")
        self._state = ModuleState.READY
        logger.info("Paper Trading Plugin initialized and READY.")

    def shutdown(self) -> None:
        """Release plugin resources on shutdown."""
        if self._state == ModuleState.STOPPED:
            return
        logger.info("Shutting down Paper Trading Plugin...")
        session = self._orchestrator.get_session()
        if session and session.status in (PaperSessionStatus.RUNNING, PaperSessionStatus.STARTING):
            self._orchestrator.stop_session()
        self._state = ModuleState.STOPPED
        logger.info("Paper Trading Plugin STOPPED.")

    def health_check(self) -> HealthStatus:
        """Report paper trading plugin health status."""
        if self._state == ModuleState.READY:
            return HealthStatus.HEALTHY
        elif self._state == ModuleState.INITIALIZING:
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.UNHEALTHY
