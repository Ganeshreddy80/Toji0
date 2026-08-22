"""Reasoning engine to evaluate rule actions, query proof paths, and trace lineage relationships."""

from __future__ import annotations

from typing import Any
from knowledge.rules.engine import RuleEngine
from knowledge.beliefs.engine import BeliefEngine
from knowledge.evidence.engine import EvidenceEngine
from knowledge.graph.manager import KnowledgeGraph
from knowledge.models import Rule, Belief


class ReasoningEngine:
    """Traverses the ontology graph and evidence links to generate explainable proofs."""

    @staticmethod
    def explain_rule(
        rule_id: str,
        rule_engine: RuleEngine,
        evidence_engine: EvidenceEngine,
    ) -> str:
        """Trace a rule back to its supporting evidence and compile a proof explanation."""
        rule = rule_engine.get_rule(rule_id)
        if rule is None:
            return f"Rule ID '{rule_id}' not found."
            
        explanation = [
            f"Rule Definition: '{rule.name}' (ID: {rule.rule_id})",
            f"  - Category: {rule.rule_type}",
            f"  - Expression: IF {rule.expression}",
            f"  - Confidence weight: {rule.confidence_weight:.2f}",
            "  - Supporting Evidence Lineage:"
        ]
        
        for e_id in rule.evidence_ids:
            ev = evidence_engine.get_evidence(e_id)
            if ev:
                explanation.append(
                    f"    * Evidence {ev.evidence_id}: {ev.metric_name} = {ev.metric_value} "
                    f"(sample size={ev.sample_size}) derived from {ev.source.ref_type} '{ev.source.ref_id}' "
                    f"({ev.source.description})."
                )
            else:
                explanation.append(f"    * Evidence ID '{e_id}' not registered in Evidence Engine.")
                
        return "\n".join(explanation)

    @staticmethod
    def explain_belief(
        belief_id: str,
        belief_engine: BeliefEngine,
        evidence_engine: EvidenceEngine,
    ) -> str:
        """Trace a belief claim back to its supporting evidence and compile an explanation."""
        belief = belief_engine.get_belief(belief_id)
        if belief is None:
            return f"Belief ID '{belief_id}' not found."
            
        status = "Retired" if belief.is_retired else "Active"
        explanation = [
            f"Belief Thesis: '{belief.claim}' (ID: {belief.belief_id})",
            f"  - Status: {status}",
            f"  - Current Confidence: {belief.confidence:.2f}",
            "  - Supporting Evidence Lineage:"
        ]
        
        for e_id in belief.evidence_ids:
            ev = evidence_engine.get_evidence(e_id)
            if ev:
                explanation.append(
                    f"    * Evidence {ev.evidence_id}: {ev.metric_name} = {ev.metric_value} "
                    f"derived from {ev.source.ref_type} '{ev.source.ref_id}'."
                )
            else:
                explanation.append(f"    * Evidence ID '{e_id}' not registered.")
                
        if belief.conflicting_belief_ids:
            explanation.append(f"  - Flagged Conflicts: {', '.join(belief.conflicting_belief_ids)}")
            
        return "\n".join(explanation)

    @staticmethod
    def find_lineage_path(
        start_id: str,
        end_id: str,
        graph: KnowledgeGraph,
    ) -> list[str] | None:
        """Trace paths across the KnowledgeGraph connecting ontology nodes (e.g. Asset -> Strategy -> Rule)."""
        return graph.find_path(start_id, end_id)

    @staticmethod
    def get_active_rules_for_facts(
        rule_engine: RuleEngine,
        facts: dict[str, Any],
    ) -> list[Rule]:
        """Query and return all registered rules that currently evaluate to True given fact parameters."""
        results = rule_engine.evaluate_rules(facts)
        active_rules = []
        for r_id, passed in results.items():
            if passed:
                rule = rule_engine.get_rule(r_id)
                if rule:
                    active_rules.append(rule)
        return active_rules
