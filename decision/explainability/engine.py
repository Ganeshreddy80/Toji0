"""Explainability Engine for generating audit trails of investment decisions."""

from __future__ import annotations

from decision.models import InvestmentDecision


class ExplainabilityEngine:
    """Formats investment decisions into detailed, structured explanation summaries and audit logs."""

    def generate_explanation_report(self, decision: InvestmentDecision) -> str:
        """Generate a complete Markdown explanation audit report for an InvestmentDecision.

        Args:
            decision: InvestmentDecision object.

        Returns:
            Markdown formatted report string.
        """
        lines = [
            f"# Investment Recommendation Report: {decision.symbol}",
            "",
            "## 1. Decision Metadata",
            f"- **Decision ID**: `{decision.decision_id}`",
            f"- **Recommendation**: **{decision.final_recommendation.value}**",
            f"- **Overall Score**: `{decision.overall_score:.2f}`",
            f"- **Consensus Confidence**: `{decision.confidence:.2%}`",
            f"- **Created At (UTC)**: `{decision.created_at.strftime('%Y-%m-%d %H:%M:%S')}`",
            f"- **Review Time (UTC)**: `{decision.review_time.strftime('%Y-%m-%d %H:%M:%S')}`",
            f"- **Expiry Time (UTC)**: `{decision.expiry_time.strftime('%Y-%m-%d %H:%M:%S')}`",
            "",
            "## 2. Core Summaries",
            f"### Risk Committee Overview",
            f"> {decision.risk_summary}",
            "",
            f"### Timing Committee Overview",
            f"> {decision.timing_summary}",
            "",
            "## 3. Committee Votes Breakdown",
            "",
            "| Committee | Vote State | Score | Confidence | Rationale |",
            "| :--- | :---: | :---: | :---: | :--- |",
        ]

        for vote in decision.votes:
            lines.append(
                f"| {vote.committee_name} | {vote.vote_state.value} | {vote.score:.2f} | {vote.confidence:.2%} | {vote.reason} |"
            )

        lines.append("")
        lines.append("## 4. Lineage & References")

        # Supporting Evidence
        lines.append("### Supporting Evidence")
        if decision.supporting_evidence:
            for item in decision.supporting_evidence:
                lines.append(f"- {item}")
        else:
            lines.append("- No supporting evidence logged")

        # Contradicting Evidence
        lines.append("\n### Contradicting / Risk Factors")
        if decision.contradicting_evidence:
            for item in decision.contradicting_evidence:
                lines.append(f"- {item}")
        else:
            lines.append("- No conflicting factors logged")

        # Knowledge Rules
        lines.append("\n### Applied Rules (Knowledge Graph)")
        if decision.rule_references:
            for ref in decision.rule_references:
                lines.append(f"- Rule ID: `{ref}`")
        else:
            lines.append("- No graph rules references logged")

        # Research References
        lines.append("\n### Referenced Research Runs")
        if decision.research_references:
            for ref in decision.research_references:
                lines.append(f"- Run ID: `{ref}`")
        else:
            lines.append("- No research experiments referenced")

        return "\n".join(lines)
