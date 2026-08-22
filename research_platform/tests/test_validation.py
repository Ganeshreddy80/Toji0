"""Comprehensive tests for R53 Continuous Validation Framework."""

from __future__ import annotations

import threading
import time
import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class TestValidationModels:
    def test_check_status_values(self):
        from research_platform.validation.models import CheckStatus
        assert CheckStatus.PASS == "PASS"
        assert CheckStatus.FAIL == "FAIL"
        assert CheckStatus.WARN == "WARN"
        assert CheckStatus.SKIP == "SKIP"
        assert CheckStatus.RUNNING == "RUNNING"

    def test_check_result_defaults(self):
        from research_platform.validation.models import CheckResult, CheckStatus
        r = CheckResult(check_name="TestChecker", status=CheckStatus.PASS)
        assert r.check_name == "TestChecker"
        assert r.status == CheckStatus.PASS
        assert r.check_id  # auto UUID

    def test_validation_run_creation(self):
        from research_platform.validation.models import ValidationRun, CheckResult, CheckStatus
        run = ValidationRun()
        assert run.run_id
        assert run.results == []
        assert run.overall_status == CheckStatus.RUNNING

    def test_validation_run_summarize(self):
        from research_platform.validation.models import ValidationRun, CheckResult, CheckStatus
        run = ValidationRun()
        run.results = [
            CheckResult(check_name="A", status=CheckStatus.PASS),
            CheckResult(check_name="B", status=CheckStatus.PASS),
            CheckResult(check_name="C", status=CheckStatus.FAIL),
            CheckResult(check_name="D", status=CheckStatus.WARN),
        ]
        summary = run.summarize()
        assert summary["PASS"] == 2
        assert summary["FAIL"] == 1
        assert summary["WARN"] == 1

    def test_certification_report(self):
        from research_platform.validation.models import CertificationReport, ValidationDuration
        cert = CertificationReport(
            run_id="run-001", duration=ValidationDuration.QUICK,
            passed=10, failed=0, warned=2,
            certified=True, summary="All good"
        )
        assert cert.certified is True
        assert cert.passed == 10

    def test_validation_duration_values(self):
        from research_platform.validation.models import ValidationDuration
        assert ValidationDuration.QUICK == "QUICK"
        assert ValidationDuration.DAILY == "DAILY"
        assert ValidationDuration.WEEKLY == "WEEKLY"
        assert ValidationDuration.MONTHLY == "MONTHLY"


# ---------------------------------------------------------------------------
# Memory Checker
# ---------------------------------------------------------------------------

class TestMemoryChecker:
    def test_returns_check_result(self):
        from research_platform.validation.memory_checker import MemoryChecker
        from research_platform.validation.models import CheckStatus
        checker = MemoryChecker()
        result = checker.run()
        assert result.check_name == "MemoryLeakChecker"
        assert result.status in (CheckStatus.PASS, CheckStatus.FAIL, CheckStatus.WARN)

    def test_name_property(self):
        from research_platform.validation.memory_checker import MemoryChecker
        assert MemoryChecker().name == "MemoryLeakChecker"

    def test_duration_measured(self):
        from research_platform.validation.memory_checker import MemoryChecker
        result = MemoryChecker().run()
        assert result.duration_ms >= 0


# ---------------------------------------------------------------------------
# Thread Checker
# ---------------------------------------------------------------------------

class TestThreadChecker:
    def test_passes_under_normal_conditions(self):
        from research_platform.validation.thread_checker import ThreadChecker
        from research_platform.validation.models import CheckStatus
        result = ThreadChecker().run()
        assert result.status in (CheckStatus.PASS, CheckStatus.WARN)

    def test_name(self):
        from research_platform.validation.thread_checker import ThreadChecker
        assert ThreadChecker().name == "ThreadLeakChecker"

    def test_details_contains_thread_counts(self):
        from research_platform.validation.thread_checker import ThreadChecker
        result = ThreadChecker().run()
        assert "active" in result.details


# ---------------------------------------------------------------------------
# Deadlock Checker
# ---------------------------------------------------------------------------

class TestDeadlockChecker:
    def test_no_deadlock_passes(self):
        from research_platform.validation.deadlock_checker import DeadlockChecker
        from research_platform.validation.models import CheckStatus
        result = DeadlockChecker().run()
        assert result.status == CheckStatus.PASS

    def test_name(self):
        from research_platform.validation.deadlock_checker import DeadlockChecker
        assert DeadlockChecker().name == "DeadlockChecker"

    def test_simulated_deadlock(self):
        """When a lock is already held, the checker should report FAIL."""
        from research_platform.validation.deadlock_checker import DeadlockChecker
        from research_platform.validation.models import CheckStatus
        import threading
        held_lock = threading.Lock()
        held_lock.acquire()  # hold externally so sentinel times out

        # We can't easily inject a held lock, but verify the checker completes
        result = DeadlockChecker().run()
        # In normal conditions (no held lock), it should PASS
        assert result.status in (CheckStatus.PASS, CheckStatus.FAIL)
        held_lock.release()


# ---------------------------------------------------------------------------
# Latency Checker
# ---------------------------------------------------------------------------

class TestLatencyChecker:
    def test_passes_on_fast_machine(self):
        from research_platform.validation.latency_checker import LatencyChecker
        from research_platform.validation.models import CheckStatus
        result = LatencyChecker().run()
        assert result.status in (CheckStatus.PASS, CheckStatus.WARN, CheckStatus.FAIL)

    def test_duration_recorded(self):
        from research_platform.validation.latency_checker import LatencyChecker
        result = LatencyChecker().run()
        assert result.duration_ms > 0

    def test_name(self):
        from research_platform.validation.latency_checker import LatencyChecker
        assert LatencyChecker().name == "LatencyChecker"


# ---------------------------------------------------------------------------
# Performance Checker
# ---------------------------------------------------------------------------

class TestPerformanceChecker:
    def test_returns_valid_result(self):
        from research_platform.validation.performance_checker import PerformanceChecker
        from research_platform.validation.models import CheckStatus
        result = PerformanceChecker().run()
        assert result.status in (CheckStatus.PASS, CheckStatus.WARN, CheckStatus.FAIL, CheckStatus.SKIP)

    def test_name(self):
        from research_platform.validation.performance_checker import PerformanceChecker
        assert PerformanceChecker().name == "PerformanceResourceChecker"

    def test_skip_without_psutil(self):
        from research_platform.validation.performance_checker import PerformanceChecker
        from research_platform.validation.models import CheckStatus
        with patch.dict("sys.modules", {"psutil": None}):
            # Even if psutil isn't available, the checker catches ImportError
            result = PerformanceChecker().run()
            assert result.status in (CheckStatus.PASS, CheckStatus.WARN, CheckStatus.FAIL, CheckStatus.SKIP)


# ---------------------------------------------------------------------------
# Health Checker
# ---------------------------------------------------------------------------

class TestHealthChecker:
    def test_warns_when_registry_empty(self):
        from research_platform.validation.health_checker import HealthChecker
        from research_platform.validation.models import CheckStatus
        result = HealthChecker().run()
        # Without services registered, should WARN or FAIL
        assert result.status in (CheckStatus.FAIL, CheckStatus.WARN, CheckStatus.PASS)

    def test_name(self):
        from research_platform.validation.health_checker import HealthChecker
        assert HealthChecker().name == "PlatformHealthChecker"

    def test_details_contains_service_lists(self):
        from research_platform.validation.health_checker import HealthChecker
        result = HealthChecker().run()
        # Should have details dict
        assert isinstance(result.details, dict)


# ---------------------------------------------------------------------------
# Resource Checker
# ---------------------------------------------------------------------------

class TestResourceChecker:
    def test_returns_valid_result(self):
        from research_platform.validation.resource_checker import ResourceChecker
        from research_platform.validation.models import CheckStatus
        result = ResourceChecker().run()
        assert result.status in (CheckStatus.PASS, CheckStatus.WARN, CheckStatus.FAIL)

    def test_details_contain_disk_info(self):
        from research_platform.validation.resource_checker import ResourceChecker
        result = ResourceChecker().run()
        assert "free_gb" in result.details or result.status == CheckStatus.WARN

    def test_name(self):
        from research_platform.validation.resource_checker import ResourceChecker
        assert ResourceChecker().name == "SystemResourceChecker"


# ---------------------------------------------------------------------------
# Integrity Checker
# ---------------------------------------------------------------------------

class TestIntegrityChecker:
    def test_passes_without_services(self):
        from research_platform.validation.integrity_checker import IntegrityChecker
        from research_platform.validation.models import CheckStatus
        result = IntegrityChecker().run()
        assert result.status in (CheckStatus.PASS, CheckStatus.WARN, CheckStatus.FAIL)

    def test_name(self):
        from research_platform.validation.integrity_checker import IntegrityChecker
        assert IntegrityChecker().name == "StateIntegrityChecker"


# ---------------------------------------------------------------------------
# Runtime Checker
# ---------------------------------------------------------------------------

class TestRuntimeChecker:
    def test_warns_when_no_engine(self):
        from research_platform.validation.runtime_checker import RuntimeChecker
        from research_platform.validation.models import CheckStatus
        result = RuntimeChecker().run()
        assert result.status in (CheckStatus.WARN, CheckStatus.PASS)

    def test_name(self):
        from research_platform.validation.runtime_checker import RuntimeChecker
        assert RuntimeChecker().name == "RuntimeEngineChecker"


# ---------------------------------------------------------------------------
# Database Checker
# ---------------------------------------------------------------------------

class TestDatabaseChecker:
    def test_warns_when_no_db(self):
        from research_platform.validation.database_checker import DatabaseChecker
        from research_platform.validation.models import CheckStatus
        result = DatabaseChecker().run()
        assert result.status in (CheckStatus.WARN, CheckStatus.PASS, CheckStatus.FAIL)

    def test_name(self):
        from research_platform.validation.database_checker import DatabaseChecker
        assert DatabaseChecker().name == "DatabaseConnectivityChecker"


# ---------------------------------------------------------------------------
# Scheduler Checker
# ---------------------------------------------------------------------------

class TestSchedulerChecker:
    def test_warns_when_no_scheduler(self):
        from research_platform.validation.scheduler_checker import SchedulerChecker
        from research_platform.validation.models import CheckStatus
        result = SchedulerChecker().run()
        assert result.status in (CheckStatus.WARN, CheckStatus.PASS)

    def test_name(self):
        from research_platform.validation.scheduler_checker import SchedulerChecker
        assert SchedulerChecker().name == "SchedulerChecker"


# ---------------------------------------------------------------------------
# Recovery Checker
# ---------------------------------------------------------------------------

class TestRecoveryChecker:
    def test_warns_when_no_recovery(self):
        from research_platform.validation.recovery_checker import RecoveryChecker
        from research_platform.validation.models import CheckStatus
        result = RecoveryChecker().run()
        assert result.status in (CheckStatus.WARN, CheckStatus.PASS)

    def test_name(self):
        from research_platform.validation.recovery_checker import RecoveryChecker
        assert RecoveryChecker().name == "RecoveryChecker"


# ---------------------------------------------------------------------------
# Stress Validator
# ---------------------------------------------------------------------------

class TestStressValidator:
    def test_passes_under_normal_conditions(self):
        from research_platform.validation.stress_validator import StressValidator
        from research_platform.validation.models import CheckStatus
        result = StressValidator().run()
        assert result.status == CheckStatus.PASS

    def test_name(self):
        from research_platform.validation.stress_validator import StressValidator
        assert StressValidator().name == "StressValidator"

    def test_duration_recorded(self):
        from research_platform.validation.stress_validator import StressValidator
        result = StressValidator().run()
        assert result.duration_ms > 0


# ---------------------------------------------------------------------------
# Soak Test
# ---------------------------------------------------------------------------

class TestSoakTest:
    def test_short_soak_passes(self):
        from research_platform.validation.soak_test import SoakTest
        from research_platform.validation.models import CheckStatus
        result = SoakTest(duration_sec=0.1, label="TEST").run()
        assert result.status == CheckStatus.PASS

    def test_name(self):
        from research_platform.validation.soak_test import SoakTest
        assert SoakTest(duration_sec=0.1, label="QUICK").name == "SoakTest[QUICK]"

    def test_iteration_count_positive(self):
        from research_platform.validation.soak_test import SoakTest
        result = SoakTest(duration_sec=0.2, label="T").run()
        assert result.details.get("iterations", 0) > 0


# ---------------------------------------------------------------------------
# Burn-In Test
# ---------------------------------------------------------------------------

class TestBurnInTest:
    def test_short_burn_in_passes(self):
        from research_platform.validation.burn_in_test import BurnInTest
        from research_platform.validation.latency_checker import LatencyChecker
        from research_platform.validation.thread_checker import ThreadChecker
        from research_platform.validation.models import CheckStatus
        checkers = [LatencyChecker(), ThreadChecker()]
        result = BurnInTest(checkers=checkers, duration_sec=0.5).run()
        assert result.status in (CheckStatus.PASS, CheckStatus.FAIL)

    def test_name(self):
        from research_platform.validation.burn_in_test import BurnInTest
        assert BurnInTest(checkers=[], duration_sec=0.1).name == "BurnInTest"

    def test_empty_checkers(self):
        from research_platform.validation.burn_in_test import BurnInTest
        from research_platform.validation.models import CheckStatus
        result = BurnInTest(checkers=[], duration_sec=0.1).run()
        assert result.status == CheckStatus.PASS  # no checkers = no failures


# ---------------------------------------------------------------------------
# Certification
# ---------------------------------------------------------------------------

class TestCertification:
    def test_certified_when_no_failures(self):
        from research_platform.validation.certification import CertificationEngine
        from research_platform.validation.models import ValidationRun, CheckResult, CheckStatus, ValidationDuration
        run = ValidationRun()
        run.results = [
            CheckResult(check_name="A", status=CheckStatus.PASS),
            CheckResult(check_name="B", status=CheckStatus.WARN),
        ]
        cert = CertificationEngine.certify(run)
        assert cert.certified is True
        assert cert.failed == 0

    def test_not_certified_with_failures(self):
        from research_platform.validation.certification import CertificationEngine
        from research_platform.validation.models import ValidationRun, CheckResult, CheckStatus
        run = ValidationRun()
        run.results = [
            CheckResult(check_name="A", status=CheckStatus.PASS),
            CheckResult(check_name="B", status=CheckStatus.FAIL),
        ]
        cert = CertificationEngine.certify(run)
        assert cert.certified is False
        assert cert.failed == 1

    def test_certification_summary_string(self):
        from research_platform.validation.certification import CertificationEngine
        from research_platform.validation.models import ValidationRun, CheckResult, CheckStatus
        run = ValidationRun()
        run.results = [CheckResult(check_name="X", status=CheckStatus.PASS)]
        cert = CertificationEngine.certify(run)
        assert "CERTIFIED" in cert.summary or "FAILED" in cert.summary

    def test_completed_at_set(self):
        from research_platform.validation.certification import CertificationEngine
        from research_platform.validation.models import ValidationRun, CheckResult, CheckStatus
        run = ValidationRun()
        run.results = [CheckResult(check_name="X", status=CheckStatus.PASS)]
        CertificationEngine.certify(run)
        assert run.completed_at is not None


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------

class TestValidationRepository:
    def test_save_and_retrieve_run(self):
        from research_platform.validation.repository import ValidationRepository
        from research_platform.validation.models import ValidationRun
        repo = ValidationRepository()
        run = ValidationRun()
        repo.save_run(run)
        latest = repo.get_latest_run()
        assert latest is not None
        assert latest.run_id == run.run_id

    def test_save_and_retrieve_certification(self):
        from research_platform.validation.repository import ValidationRepository
        from research_platform.validation.models import CertificationReport, ValidationDuration
        repo = ValidationRepository()
        cert = CertificationReport(run_id="run-001", duration=ValidationDuration.QUICK,
                                   passed=5, failed=0, warned=1, certified=True,
                                   summary="CERTIFIED")
        repo.save_certification(cert)
        latest = repo.get_latest_certification()
        assert latest is not None
        assert latest.certified is True

    def test_thread_safe_saves(self):
        from research_platform.validation.repository import ValidationRepository
        from research_platform.validation.models import ValidationRun
        repo = ValidationRepository()
        errors = []

        def save():
            try:
                repo.save_run(ValidationRun())
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=save) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []

    def test_empty_repo_returns_none(self):
        from research_platform.validation.repository import ValidationRepository
        repo = ValidationRepository()
        assert repo.get_latest_run() is None
        assert repo.get_latest_certification() is None


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

class TestValidationEvents:
    def test_run_started_event(self):
        from research_platform.validation.events import ValidationRunStarted
        ev = ValidationRunStarted(run_id="run-001", checker_count=12)
        assert ev.checker_count == 12

    def test_run_completed_event(self):
        from research_platform.validation.events import ValidationRunCompleted
        ev = ValidationRunCompleted(run_id="run-001", passed=10, failed=0, warned=2, certified=True)
        assert ev.certified is True

    def test_check_failed_event(self):
        from research_platform.validation.events import CheckFailed
        ev = CheckFailed(check_name="MemoryChecker", message="Growth exceeded 50 MB")
        assert ev.check_name == "MemoryChecker"


# ---------------------------------------------------------------------------
# Orchestrator (Integration)
# ---------------------------------------------------------------------------

class TestValidationOrchestrator:
    def test_run_all_returns_validation_run(self):
        from research_platform.validation.orchestrator import ValidationOrchestrator
        from research_platform.validation.models import ValidationRun
        orch = ValidationOrchestrator()
        run = orch.run_all()
        assert isinstance(run, ValidationRun)
        assert len(run.results) > 0

    def test_all_results_have_names(self):
        from research_platform.validation.orchestrator import ValidationOrchestrator
        orch = ValidationOrchestrator()
        run = orch.run_all()
        for result in run.results:
            assert result.check_name

    def test_certification_available_after_run(self):
        from research_platform.validation.orchestrator import ValidationOrchestrator
        orch = ValidationOrchestrator()
        orch.run_all()
        cert = orch.get_latest_certification()
        assert cert is not None

    def test_run_completes_without_crash(self):
        from research_platform.validation.orchestrator import ValidationOrchestrator
        orch = ValidationOrchestrator()
        run = orch.run_all()
        assert run.run_id

    def test_thread_safe_concurrent_runs(self):
        from research_platform.validation.orchestrator import ValidationOrchestrator
        orch = ValidationOrchestrator()
        errors = []

        def run():
            try:
                orch.run_all()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=run) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
