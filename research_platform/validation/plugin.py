"""R53 Continuous Validation Framework Plugin — platform DI integration."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ValidationPlugin:
    """Registers R53 ValidationOrchestrator and runs a startup certification pass."""

    def __init__(self, container: Any) -> None:
        self.container = container
        self._orchestrator = None

    def initialize(self) -> None:
        logger.info("Initializing Continuous Validation Framework (R53)...")
        try:
            from research_platform.validation.orchestrator import ValidationOrchestrator
            from research_platform.validation.repository import ValidationRepository
            from research_platform.validation.certification import CertificationEngine

            repo = ValidationRepository()
            orchestrator = ValidationOrchestrator(repository=repo)

            self.container.register("ValidationOrchestrator", instance=orchestrator)
            self.container.register("ValidationRepository", instance=repo)
            self.container.register(ValidationOrchestrator, instance=orchestrator)
            self.container.register(ValidationRepository, instance=repo)

            self._orchestrator = orchestrator
            logger.info("R53 ValidationPlugin initialized with %d checkers.", len(orchestrator._checkers))

            # Run startup validation pass (deferred to end of boot sequence)
            # self._run_startup_validation()
        except Exception as e:
            logger.error("R53 ValidationPlugin initialization failed: %s", e)

    def _run_startup_validation(self) -> None:
        """Run a QUICK validation pass during platform boot."""
        try:
            from research_platform.validation.models import ValidationDuration
            run = self._orchestrator.run_all(duration=ValidationDuration.QUICK)
            cert = self._orchestrator.get_latest_certification()
            if cert:
                logger.info("Startup validation: %s", cert.summary)
        except Exception as e:
            logger.warning("Startup validation failed: %s", e)

    def shutdown(self) -> None:
        logger.info("R53 ValidationPlugin shutdown complete.")

    def health_check(self) -> str:
        try:
            cert = self._orchestrator.get_latest_certification() if self._orchestrator else None
            if cert and cert.certified:
                return "HEALTHY"
            return "DEGRADED"
        except Exception:
            return "UNKNOWN"
