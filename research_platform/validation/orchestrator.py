"""R53 Validation Orchestrator — schedules and executes all checkers in a ValidationRun."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import List, Optional

from research_platform.validation.interfaces import IChecker, IValidationOrchestrator
from research_platform.validation.models import (
    CheckResult, CheckStatus, ValidationRun, ValidationDuration, CertificationReport
)
from research_platform.validation.certification import CertificationEngine
from research_platform.validation.repository import ValidationRepository
from research_platform.validation.events import ValidationRunStarted, ValidationRunCompleted, CheckFailed

# All checkers
from research_platform.validation.memory_checker import MemoryChecker
from research_platform.validation.thread_checker import ThreadChecker
from research_platform.validation.deadlock_checker import DeadlockChecker
from research_platform.validation.runtime_checker import RuntimeChecker
from research_platform.validation.database_checker import DatabaseChecker
from research_platform.validation.scheduler_checker import SchedulerChecker
from research_platform.validation.recovery_checker import RecoveryChecker
from research_platform.validation.latency_checker import LatencyChecker
from research_platform.validation.performance_checker import PerformanceChecker
from research_platform.validation.health_checker import HealthChecker
from research_platform.validation.resource_checker import ResourceChecker
from research_platform.validation.integrity_checker import IntegrityChecker
from research_platform.validation.stress_validator import StressValidator
from research_platform.validation.soak_test import SoakTest

logger = logging.getLogger(__name__)


def _build_default_checkers() -> List[IChecker]:
    return [
        MemoryChecker(),
        ThreadChecker(),
        DeadlockChecker(),
        LatencyChecker(),
        PerformanceChecker(),
        HealthChecker(),
        ResourceChecker(),
        IntegrityChecker(),
        RuntimeChecker(),
        DatabaseChecker(),
        SchedulerChecker(),
        RecoveryChecker(),
        StressValidator(),
        SoakTest(duration_sec=0.5, label="QUICK"),
    ]


class ValidationOrchestrator(IValidationOrchestrator):
    """Coordinates all validation checkers and produces certified reports."""

    def __init__(
        self,
        checkers: Optional[List[IChecker]] = None,
        repository: Optional[ValidationRepository] = None,
    ) -> None:
        self._checkers = checkers or _build_default_checkers()
        self._repository = repository or ValidationRepository()
        self._lock = threading.Lock()
        self._running = False

    def run_all(self, duration: ValidationDuration = ValidationDuration.QUICK) -> ValidationRun:
        """Execute all checkers sequentially and return the aggregated ValidationRun."""
        run = ValidationRun(run_id=str(uuid.uuid4()), duration=duration)

        self._publish_event("ValidationRunStarted", ValidationRunStarted(
            run_id=run.run_id, checker_count=len(self._checkers)
        ))

        for checker in self._checkers:
            try:
                result = checker.run()
                run.results.append(result)
                if result.status == CheckStatus.FAIL:
                    self._publish_event("CheckFailed", CheckFailed(
                        check_name=result.check_name, message=result.message
                    ))
                logger.debug("Checker %s → %s (%.1f ms)", checker.name, result.status.value, result.duration_ms)
            except Exception as e:
                logger.error("Checker %s raised exception: %s", checker.name, e)
                run.results.append(CheckResult(
                    check_name=checker.name, status=CheckStatus.FAIL,
                    message=f"Exception: {e}"
                ))

        cert = CertificationEngine.certify(run, duration)
        self._repository.save_run(run)
        self._repository.save_certification(cert)

        self._publish_event("ValidationRunCompleted", ValidationRunCompleted(
            run_id=run.run_id,
            passed=cert.passed,
            failed=cert.failed,
            warned=cert.warned,
            certified=cert.certified,
        ))

        # Print detailed validation stats for each checker
        for result in run.results:
            status_str = result.status.value
            msg_str = f"Reason: {result.message}" if result.status == CheckStatus.FAIL else result.message
            duration_val = f"{result.duration_ms / 1000.0:.4f}s" if result.duration_ms else "0.00s"
            
            print(f"{result.check_name}:", flush=True)
            print(status_str, flush=True)
            print(msg_str, flush=True)
            print(f"Duration: {duration_val}\n", flush=True)
            
            logger.info("Checker: %s", result.check_name)
            logger.info("Status: %s", status_str)
            logger.info("Message: %s", msg_str)
            logger.info("Duration: %s", duration_val)

        logger.info(
            "Validation complete: %s — %s/%s PASS, %s FAIL, %s WARN",
            "CERTIFIED" if cert.certified else "FAILED",
            cert.passed, cert.passed + cert.failed + cert.warned,
            cert.failed, cert.warned,
        )
        return run

    def get_latest_certification(self) -> Optional[CertificationReport]:
        return self._repository.get_latest_certification()

    def _publish_event(self, topic: str, event: object) -> None:
        try:
            from research_platform.platform.service_registry import ServiceRegistry
            eb = ServiceRegistry().get_service("EventBus")
            if eb:
                eb.publish(topic, event.model_dump())
        except Exception:
            pass
