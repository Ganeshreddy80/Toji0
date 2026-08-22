"""Decision Report Generator for compiling performance and audit reviews."""

from __future__ import annotations

from typing import Any
from decision.models import DecisionState, InvestmentDecision
from decision.journal.manager import DecisionJournal


class DecisionReportGenerator:
    """Compiles statistics and audit summaries from investment decisions and journal entries."""

    def compile_decision_summary(self, decision: InvestmentDecision) -> dict[str, Any]:
        """Compile a summary dictionary for an individual InvestmentDecision.

        Args:
            decision: InvestmentDecision object.

        Returns:
            Dictionary summary.
        """
        # Map committee votes
        votes_summary = {
            v.committee_name: {
                "state": v.vote_state.value,
                "score": v.score,
                "confidence": v.confidence,
                "reason": v.reason,
            }
            for v in decision.votes
        }

        return {
            "decision_id": decision.decision_id,
            "symbol": decision.symbol,
            "recommendation": decision.final_recommendation.value,
            "overall_score": decision.overall_score,
            "confidence": decision.confidence,
            "risk_summary": decision.risk_summary,
            "timing_summary": decision.timing_summary,
            "votes": votes_summary,
            "rule_count": len(decision.rule_references),
            "research_count": len(decision.research_references),
        }

    def compile_journal_report(self, journal: DecisionJournal) -> dict[str, Any]:
        """Compile an aggregated performance report from the DecisionJournal.

        Args:
            journal: DecisionJournal instance.

        Returns:
            Dictionary report containing correctness counts, ratios, and state distributions.
        """
        # We access the internal dictionary to summarize entries
        entries = list(journal._entries.values())

        if not entries:
            return {
                "summary": "No decisions logged in journal",
                "total_decisions": 0,
                "correctness_ratio": 0.0,
            }

        total = len(entries)
        closed_entries = [e for e in entries if e.closed_at is not None]
        audited_entries = [e for e in closed_entries if e.is_correct is not None]

        correct_count = sum(1 for e in audited_entries if e.is_correct is True)
        incorrect_count = sum(1 for e in audited_entries if e.is_correct is False)
        ratio = correct_count / len(audited_entries) if audited_entries else 0.0

        # Distribution of recommendations
        state_counts: dict[str, int] = {}
        for entry in entries:
            state = entry.decision.final_recommendation.value
            state_counts[state] = state_counts.get(state, 0) + 1

        return {
            "summary": "Decision Journal Audit Performance Report",
            "total_decisions": total,
            "closed_decisions": len(closed_entries),
            "audited_decisions": len(audited_entries),
            "correct_decisions": correct_count,
            "incorrect_decisions": incorrect_count,
            "correctness_ratio": ratio,
            "recommendation_distribution": state_counts,
            "lessons_compiled": [
                lesson
                for e in entries
                for lesson in e.lessons
                if not lesson.startswith("Audited via")
            ][:15],  # top 15 lessons
        }
