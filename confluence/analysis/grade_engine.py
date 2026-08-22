"""Grade Engine for assigning institutional setup grades with risk-based demotion."""

from __future__ import annotations

from confluence.core.enums import SetupGrade, RiskFlagType
from confluence.core.models import RiskFlag


class GradeEngine:
    """Assigns a setup grade based on overall score and active risk flags.

    Thresholds:
        A+  >= 95
        A   >= 88
        B+  >= 80
        B   >= 70
        C   >= 55
        No Trade < 55

    Risk demotion: any active HIGH-severity flag (severity >= 0.8) demotes the grade by one step.
    """

    # Ordered from highest to lowest
    _GRADE_LADDER: list[tuple[float, SetupGrade]] = [
        (95.0, SetupGrade.A_PLUS),
        (88.0, SetupGrade.A),
        (80.0, SetupGrade.B_PLUS),
        (70.0, SetupGrade.B),
        (55.0, SetupGrade.C),
    ]

    _DEMOTION_ORDER: list[SetupGrade] = [
        SetupGrade.A_PLUS,
        SetupGrade.A,
        SetupGrade.B_PLUS,
        SetupGrade.B,
        SetupGrade.C,
        SetupGrade.NO_TRADE,
    ]

    def assign_grade(
        self,
        overall_score: float,
        risk_flags: list[RiskFlag] | None = None,
    ) -> SetupGrade:
        """Compute the setup grade from the overall score, then apply risk demotion."""
        # 1. Assign base grade from thresholds
        grade = SetupGrade.NO_TRADE
        for threshold, candidate_grade in self._GRADE_LADDER:
            if overall_score >= threshold:
                grade = candidate_grade
                break

        # 2. Apply risk demotion if any HIGH-severity flag is active
        if risk_flags:
            high_severity_count = sum(
                1 for f in risk_flags if f.active and f.severity >= 0.8
            )
            for _ in range(high_severity_count):
                grade = self._demote(grade)

        return grade

    def _demote(self, grade: SetupGrade) -> SetupGrade:
        """Demote a grade by one step in the ladder."""
        try:
            idx = self._DEMOTION_ORDER.index(grade)
            if idx + 1 < len(self._DEMOTION_ORDER):
                return self._DEMOTION_ORDER[idx + 1]
        except ValueError:
            pass
        return SetupGrade.NO_TRADE
