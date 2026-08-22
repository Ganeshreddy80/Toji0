"""R53 Certification — aggregates validation runs into a signed certification report."""

from __future__ import annotations

from datetime import datetime, timezone
from research_platform.validation.models import (
    ValidationRun, CertificationReport, CheckStatus, ValidationDuration
)


class CertificationEngine:
    """Produces a CertificationReport from a completed ValidationRun."""

    @staticmethod
    def certify(run: ValidationRun, duration: ValidationDuration = ValidationDuration.QUICK) -> CertificationReport:
        counts = run.summarize()
        passed = counts.get(CheckStatus.PASS.value, 0)
        failed = counts.get(CheckStatus.FAIL.value, 0)
        warned = counts.get(CheckStatus.WARN.value, 0)
        total = sum(counts.values())

        # Platform is certified only if zero FAIL results
        certified = (failed == 0)
        status_line = "CERTIFIED" if certified else "FAILED"

        summary = (
            f"Validation {status_line}: {passed}/{total} checks passed, "
            f"{failed} failed, {warned} warned. Duration={duration.value}"
        )

        run.certified = certified
        run.overall_status = CheckStatus.PASS if certified else CheckStatus.FAIL
        run.completed_at = datetime.now(timezone.utc)

        return CertificationReport(
            run_id=run.run_id,
            duration=duration,
            passed=passed,
            failed=failed,
            warned=warned,
            certified=certified,
            summary=summary,
            details=run.results,
        )
