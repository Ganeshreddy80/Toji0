"""Rule engine for registering, validating, and evaluating IF/THEN strategies rules."""

from __future__ import annotations

import uuid
from typing import Any
from knowledge.models import Rule, KnowledgeStatus
from knowledge.evidence.engine import EvidenceEngine


class RuleEngine:
    """Manages quantitative rules, validates evidence citations, and evaluates conditional logic."""

    def __init__(self, evidence_engine: EvidenceEngine | None = None) -> None:
        self.evidence_engine = evidence_engine
        self._rules: dict[str, Rule] = {}

    def register_rule(
        self,
        name: str,
        rule_type: str,
        expression: str,
        evidence_ids: list[str],
        confidence_weight: float = 1.0,
    ) -> Rule:
        """Register a new Rule backed by registered evidence IDs.
        
        Enforces: No unsupported rule may exist (must cite at least one valid evidence).
        """
        if not evidence_ids:
            raise ValueError("Unsupported rule: Rules must cite at least one evidence ID.")
            
        # Verify evidence existence if engine is connected
        if self.evidence_engine is not None:
            for e_id in evidence_ids:
                if self.evidence_engine.get_evidence(e_id) is None:
                    raise ValueError(f"Evidence ID '{e_id}' does not exist in the evidence engine.")
                    
        rule_id = str(uuid.uuid4())
        rule = Rule(
            rule_id=rule_id,
            name=name,
            rule_type=rule_type,
            expression=expression,
            confidence_weight=confidence_weight,
            evidence_ids=evidence_ids,
            status=KnowledgeStatus.ACTIVE
        )
        self._rules[rule_id] = rule
        return rule

    def evaluate_rules(self, facts: dict[str, Any]) -> dict[str, bool]:
        """Evaluate registered active rules expressions against a dictionary of facts."""
        eval_results = {}
        for r_id, rule in self._rules.items():
            if rule.status != KnowledgeStatus.ACTIVE:
                continue
                
            # Safely evaluate rule condition expression (e.g. "trend == 'bullish' and vol > 10")
            try:
                # Restrict builtins inside eval for safety
                res = bool(eval(rule.expression, {"__builtins__": None}, facts))
            except Exception:
                # Expression evaluation failed (e.g., key error in facts or syntax error)
                res = False
                
            eval_results[r_id] = res
            
        return eval_results

    def get_rule(self, rule_id: str) -> Rule | None:
        """Retrieve a registered rule by its ID."""
        return self._rules.get(rule_id)

    def list_rules(self) -> list[Rule]:
        """List all registered rules."""
        return list(self._rules.values())
