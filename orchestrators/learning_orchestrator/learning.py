"""Learning Orchestrator for paper trade audits, journal updates, and confidence calibration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from knowledge.confidence.calculator import ConfidenceCalculator
from toji_platform.core.event_bus.events import LearningCompleted

if TYPE_CHECKING:
    from decision.journal.manager import DecisionJournal
    from knowledge.beliefs.engine import BeliefEngine
    from knowledge.evidence.engine import EvidenceEngine
    from knowledge.rules.engine import RuleEngine
    from toji_platform.core.event_bus.interfaces import IEvent
    from toji_platform.core.event_bus.interfaces import IEventBus


class LearningOrchestrator:
    """Manages trade reviews, audits journal correctness, and evolves knowledge confidence."""

    def __init__(
        self,
        event_bus: IEventBus,
        decision_journal: DecisionJournal,
        evidence_engine: EvidenceEngine,
        rule_engine: RuleEngine,
        belief_engine: BeliefEngine,
    ) -> None:
        """Initialize the LearningOrchestrator.

        Args:
            event_bus: Kernel Event Bus.
            decision_journal: Decision journal manager.
            evidence_engine: Knowledge Engine evidence registry.
            rule_engine: Knowledge Engine rule engine.
            belief_engine: Knowledge Engine belief engine.
        """
        self.event_bus = event_bus
        self.decision_journal = decision_journal
        self.evidence_engine = evidence_engine
        self.rule_engine = rule_engine
        self.belief_engine = belief_engine

    def audit_decision_performance(self, decision_id: str, prices: list[float]) -> bool | None:
        """Audit decision correctness against prices, record performance, and calibrate confidence.

        Args:
            decision_id: Target decision ID to audit.
            prices: Historical price series from the decision's active window.

        Returns:
            Correctness outcome boolean, or None if insufficient prices.
        """
        # 1. Run correctness check
        is_correct = self.decision_journal.audit_correctness(decision_id, prices)
        if is_correct is None:
            return None

        entry = self.decision_journal.get_entry(decision_id)
        if not entry:
            return is_correct

        decision = entry.decision

        # 2. Register new audit evidence
        audit_ev = self.evidence_engine.register_evidence(
            source_type="audit",
            source_id=decision_id,
            description=f"Performance audit for decision {decision_id}. Correct: {is_correct}",
            metric_name="audit_success",
            metric_value=1.0 if is_correct else 0.0,
            sample_size=1,
        )

        # 3. Calibrate Confidence for associated Rules
        for rule_id in decision.rule_references:
            rule = self.rule_engine.get_rule(rule_id)
            if not rule:
                continue

            # Associate new audit evidence with the rule
            updated_evs = list(rule.evidence_ids) + [audit_ev.evidence_id]
            ev_nodes = []
            for ev_id in updated_evs:
                ev_node = self.evidence_engine.get_evidence(ev_id)
                if ev_node:
                    ev_nodes.append(ev_node)

            # Re-calculate confidence
            new_confidence = ConfidenceCalculator.calculate_confidence(
                evidence_list=ev_nodes,
                has_conflict=False,  # default placeholder
            )

            # Update the rule parameters (we can register it again or modify internal registry)
            # For simplicity, we just update the internal database record
            rule = rule.model_copy(update={"evidence_ids": updated_evs, "confidence_weight": new_confidence})
            self.rule_engine._rules[rule_id] = rule

        # 4. Calibrate Confidence for associated Beliefs
        for belief_id in decision.research_references:
            belief = self.belief_engine.get_belief(belief_id)
            if not belief:
                continue

            updated_evs = list(belief.evidence_ids) + [audit_ev.evidence_id]
            ev_nodes = []
            for ev_id in updated_evs:
                ev_node = self.evidence_engine.get_evidence(ev_id)
                if ev_node:
                    ev_nodes.append(ev_node)

            new_confidence = ConfidenceCalculator.calculate_confidence(
                evidence_list=ev_nodes,
                has_conflict=False,
            )

            self.belief_engine.update_belief(
                belief_id=belief_id,
                new_confidence=new_confidence,
                new_evidence_ids=updated_evs,
            )

        # 5. Publish LearningCompleted event
        event_payload = {
            "decision_id": decision_id,
            "symbol": decision.symbol,
            "is_correct": is_correct,
            "audit_evidence_id": audit_ev.evidence_id,
        }
        event = LearningCompleted(
            source="LearningOrchestrator", payload=event_payload
        )
        self.event_bus.publish(event)

        return is_correct
