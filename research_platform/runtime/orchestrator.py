"""Runtime Orchestrator managing engine lifecycle triggers.
"""

from __future__ import annotations

import logging
from typing import Dict, Any

from research_platform.runtime.interfaces import IRuntimeOrchestrator
from research_platform.runtime.lifecycle import RuntimeLifecycleManager
from research_platform.runtime.runtime_engine import RuntimeEngine

logger = logging.getLogger(__name__)


class RuntimeOrchestrator(IRuntimeOrchestrator):
    """Central orchestrator controlling continuous trading loop executions."""

    def __init__(self, container: Any) -> None:
        self.container = container
        self.lifecycle_manager = RuntimeLifecycleManager()
        self.engine: RuntimeEngine | None = None
        self.registry = None

    def boot(self) -> None:
        """Start the continuous runtime process boot and threads."""
        logger.info("Orchestrator: Initializing platform boot sequence...")
        self.registry = self.lifecycle_manager.boot()
        
        # Instantiate and start RuntimeEngine
        if self.container.has("RuntimeEngine"):
            self.engine = self.container.resolve("RuntimeEngine")
        else:
            self.engine = RuntimeEngine(self.container)
            self.container.register("RuntimeEngine", instance=self.engine)
            from research_platform.platform.service_registry import ServiceRegistry
            ServiceRegistry().register_service("RuntimeEngine", self.engine)
        
        logger.info("Orchestrator: Starting runtime loop execution engine thread...")
        self.engine.start()

    def shutdown(self) -> None:
        """Stop runtime execution engine and teardown dependencies."""
        logger.info("Orchestrator: Initializing teardown sequence...")
        if self.engine:
            self.engine.stop()
            
        if self.registry:
            self.lifecycle_manager.shutdown(self.registry)
        
        logger.info("Orchestrator: Teardown complete.")
