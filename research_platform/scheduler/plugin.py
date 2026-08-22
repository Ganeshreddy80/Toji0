"""Scheduler plugin registration.
"""

from __future__ import annotations

import logging
from typing import Any
from research_platform.scheduler.orchestrator import StrategySchedulerOrchestrator

logger = logging.getLogger(__name__)


class StrategySchedulerPlugin:
    """Hooks the strategy scheduler components into the DI container during boot."""

    def __init__(self, container) -> None:
        self.container = container
        self._orchestrator: StrategySchedulerOrchestrator | None = None

    def initialize(self) -> None:
        """Register orchestrator mappings."""
        event_bus = self.container.resolve("IEventBus")
        
        orchestrator = StrategySchedulerOrchestrator(event_bus, container=self.container)
        self.container.register("StrategySchedulerOrchestrator", instance=orchestrator)
        self.container.register(StrategySchedulerOrchestrator, instance=orchestrator)
        self.container.register("Scheduler", instance=orchestrator)

        from research_platform.platform.service_registry import ServiceRegistry
        ServiceRegistry().register_service("StrategySchedulerOrchestrator", orchestrator)
        ServiceRegistry().register_service("Scheduler", orchestrator)

        # Register default maintenance task callbacks
        self._register_maintenance_tasks(orchestrator)

        self._orchestrator = orchestrator
        self._orchestrator.start()

    def _register_maintenance_tasks(self, orchestrator: StrategySchedulerOrchestrator) -> None:
        # 1. Log Pruning Task
        def prune_logs():
            try:
                from research_platform.logging.retention import RetentionPolicy
                # Prune logs older than 90 days in the default logs directory
                policy = RetentionPolicy(log_dir="./logs", max_age_days=90)
                deleted = policy.prune()
                logger.info("Maintenance scheduled run: pruned %d old log files.", deleted)
            except Exception as e:
                logger.error("Failed to run log pruning maintenance task: %s", e)

        # 2. Continuous Platform Validation Task
        def validate_platform():
            try:
                val_orch = self.container.resolve("ValidationOrchestrator")
                if val_orch:
                    from research_platform.validation.models import ValidationDuration
                    run = val_orch.run_all(duration=ValidationDuration.DAILY)
                    logger.info("Maintenance scheduled run: validated platform. Run ID=%s, Status=%s", run.run_id, run.overall_status.value)
            except Exception as e:
                logger.error("Failed to run validation maintenance task: %s", e)

        # Register callbacks in the orchestrator
        orchestrator.register_callback("MAINTENANCE", prune_logs)
        orchestrator.register_callback("LogPruning", prune_logs)
        orchestrator.register_callback("PlatformValidation", validate_platform)

    def shutdown(self) -> None:
        """Cleanup resources."""
        if self._orchestrator:
            self._orchestrator.stop()

    def health_check(self) -> Any:
        """Assess operational health state."""
        from toji_platform.core.types import HealthStatus
        return HealthStatus.HEALTHY
