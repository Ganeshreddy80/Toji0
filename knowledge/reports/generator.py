"""Reports generator for summarizing rules, beliefs, evidence links, and contradiction tasks."""

from __future__ import annotations

from typing import Any
from knowledge.models import Rule, Belief, Evidence
from knowledge.contradictions.detector import InvestigationTask


class KnowledgeReportGenerator:
    """Generates structured diagnostic summaries of rules, beliefs, contradictions, and evidence logs."""

    @staticmethod
    def generate_knowledge_report(
        rules: list[Rule],
        beliefs: list[Belief],
        insights: list[Any],
    ) -> dict[str, Any]:
        """Aggregate high-level knowledge metrics into a Knowledge Report."""
        return {
            "report_type": "Knowledge Report",
            "summary": {
                "active_rules_count": len([r for r in rules if r.status.value == "active"]),
                "active_beliefs_count": len([b for b in beliefs if not b.is_retired]),
                "total_insights_count": len(insights),
            }
        }

    @staticmethod
    def generate_belief_report(beliefs: list[Belief]) -> dict[str, Any]:
        """Aggregate active/retired proportions and confidence distributions into a Belief Report."""
        active = [b for b in beliefs if not b.is_retired]
        retired = [b for b in beliefs if b.is_retired]
        
        confidences = [b.confidence for b in active]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        return {
            "report_type": "Belief Report",
            "metrics": {
                "total_beliefs": len(beliefs),
                "active_beliefs": len(active),
                "retired_beliefs": len(retired),
                "average_confidence": avg_confidence,
            },
            "beliefs": [b.model_dump() for b in beliefs]
        }

    @staticmethod
    def generate_rule_report(rules: list[Rule]) -> dict[str, Any]:
        """Aggregate rule categories and weights into a Rule Report."""
        by_type: dict[str, int] = {}
        for r in rules:
            by_type[r.rule_type] = by_type.get(r.rule_type, 0) + 1
            
        weights = [r.confidence_weight for r in rules]
        avg_weight = sum(weights) / len(weights) if weights else 0.0
        
        return {
            "report_type": "Rule Report",
            "metrics": {
                "total_rules": len(rules),
                "average_confidence_weight": avg_weight,
                "rules_by_category": by_type,
            },
            "rules": [r.model_dump() for r in rules]
        }

    @staticmethod
    def generate_evidence_report(evidence_list: list[Evidence]) -> dict[str, Any]:
        """Aggregate evidence types and samples counts into an Evidence Report."""
        by_source_type: dict[str, int] = {}
        for e in evidence_list:
            by_source_type[e.source.ref_type] = by_source_type.get(e.source.ref_type, 0) + 1
            
        return {
            "report_type": "Evidence Report",
            "metrics": {
                "total_evidence_entries": len(evidence_list),
                "evidence_by_source_type": by_source_type,
            },
            "evidence": [e.model_dump() for e in evidence_list]
        }

    @staticmethod
    def generate_contradiction_report(tasks: list[InvestigationTask]) -> dict[str, Any]:
        """Aggregate active contradictions and pending tasks into a Contradiction Report."""
        by_type: dict[str, int] = {}
        for t in tasks:
            by_type[t.contradiction_type] = by_type.get(t.contradiction_type, 0) + 1
            
        return {
            "report_type": "Contradiction Report",
            "metrics": {
                "total_active_contradictions": len(tasks),
                "contradictions_by_type": by_type,
            },
            "investigation_tasks": [t.model_dump() for t in tasks]
        }
