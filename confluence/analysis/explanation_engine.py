"""Explanation Engine for producing deterministic trade recommendations.

All explanations are rules-based. No LLMs. No randomness.
"""

from __future__ import annotations

from confluence.core.enums import SetupGrade
from confluence.core.models import (
    ConfluenceScore,
    OpportunityScore,
    RiskFlag,
    TradeExplanation,
)


class ExplanationEngine:
    """Generates structured, deterministic explanations for every trade recommendation."""

    # Grade to recommendation mapping
    _GRADE_RECOMMENDATIONS: dict[SetupGrade, str] = {
        SetupGrade.A_PLUS: "STRONG_BUY",
        SetupGrade.A: "BUY",
        SetupGrade.B_PLUS: "BUY",
        SetupGrade.B: "HOLD",
        SetupGrade.C: "AVOID",
        SetupGrade.NO_TRADE: "NO_TRADE",
    }

    def explain(
        self,
        confluence_score: ConfluenceScore,
        opportunity: OpportunityScore,
        risk_flags: list[RiskFlag],
        grade: SetupGrade,
    ) -> TradeExplanation:
        """Generate a fully deterministic, rules-based explanation."""
        recommendation = self._GRADE_RECOMMENDATIONS.get(grade, "NO_TRADE")
        reasons = self._build_reasons(confluence_score, opportunity, grade)
        risk_summary = self._build_risk_summary(risk_flags)
        grade_rationale = self._build_grade_rationale(confluence_score, grade, risk_flags)
        key_factors = self._extract_key_factors(confluence_score)

        return TradeExplanation(
            recommendation=recommendation,
            reasons=reasons,
            risk_summary=risk_summary,
            grade_rationale=grade_rationale,
            key_factors=key_factors,
        )

    def _build_reasons(
        self,
        score: ConfluenceScore,
        opportunity: OpportunityScore,
        grade: SetupGrade,
    ) -> list[str]:
        """Build ordered list of supporting reasons."""
        reasons: list[str] = []

        if score.overall_score >= 80:
            reasons.append(f"Strong confluence alignment with score {score.overall_score:.1f}/100.")
        elif score.overall_score >= 60:
            reasons.append(f"Moderate confluence alignment with score {score.overall_score:.1f}/100.")
        else:
            reasons.append(f"Weak confluence alignment with score {score.overall_score:.1f}/100.")

        # Trend
        if score.trend_score >= 80:
            reasons.append(f"Strong trend alignment (score: {score.trend_score:.0f}).")
        elif score.trend_score < 40:
            reasons.append(f"Weak trend conditions (score: {score.trend_score:.0f}).")

        # Liquidity
        if score.liquidity_score >= 80:
            reasons.append(f"Excellent liquidity conditions (score: {score.liquidity_score:.0f}).")
        elif score.liquidity_score < 40:
            reasons.append(f"Poor liquidity — execution risk elevated (score: {score.liquidity_score:.0f}).")

        # Opportunity
        if opportunity.expected_rr >= 2.0:
            reasons.append(f"Favorable risk/reward ratio of {opportunity.expected_rr:.1f}:1.")
        elif opportunity.expected_rr < 1.0:
            reasons.append(f"Unfavorable risk/reward ratio of {opportunity.expected_rr:.1f}:1.")

        # Supporting factors
        if len(score.supporting_factors) >= 5:
            reasons.append(f"{len(score.supporting_factors)} supporting factors identified.")

        # Conflicting factors
        if score.conflicting_factors:
            reasons.append(f"{len(score.conflicting_factors)} conflicting factor(s) detected.")

        return reasons

    def _build_risk_summary(self, risk_flags: list[RiskFlag]) -> str:
        """Build a human-readable risk summary."""
        active_flags = [f for f in risk_flags if f.active]
        if not active_flags:
            return "No active risk flags. Conditions are favorable for trading."

        high_sev = [f for f in active_flags if f.severity >= 0.8]
        med_sev = [f for f in active_flags if 0.4 <= f.severity < 0.8]
        low_sev = [f for f in active_flags if f.severity < 0.4]

        parts = []
        if high_sev:
            names = ", ".join(f.flag_type.value for f in high_sev)
            parts.append(f"HIGH: {names}")
        if med_sev:
            names = ", ".join(f.flag_type.value for f in med_sev)
            parts.append(f"MEDIUM: {names}")
        if low_sev:
            names = ", ".join(f.flag_type.value for f in low_sev)
            parts.append(f"LOW: {names}")

        return f"{len(active_flags)} active risk flag(s). {'; '.join(parts)}."

    def _build_grade_rationale(
        self,
        score: ConfluenceScore,
        grade: SetupGrade,
        risk_flags: list[RiskFlag],
    ) -> str:
        """Explain why the specific grade was assigned."""
        base = f"Grade {grade.value} assigned based on overall score {score.overall_score:.1f}/100."

        high_risk = [f for f in risk_flags if f.active and f.severity >= 0.8]
        if high_risk:
            flag_names = ", ".join(f.flag_type.value for f in high_risk)
            base += f" Grade demoted due to high-severity risk flags: {flag_names}."

        if score.conflict_penalty > 0:
            base += f" Conflict penalty of {score.conflict_penalty:.2f} applied."

        return base

    def _extract_key_factors(self, score: ConfluenceScore) -> list[str]:
        """Extract the top contributing factors sorted by value."""
        if not score.supporting_factors:
            return ["No significant contributing factors identified."]

        sorted_factors = sorted(
            score.supporting_factors, key=lambda f: f.value, reverse=True
        )
        return [
            f"{f.name} ({f.category}): {f.value:.1f} — {f.description}"
            for f in sorted_factors[:5]
        ]
