"""Compliance policy evaluation engine implementing IPolicyEvaluator.
"""

from __future__ import annotations

import logging
from typing import Dict, List
from research_platform.governance.interfaces import IPolicyEvaluator
from research_platform.governance.models import ComplianceRule, PolicyEvaluationResult

logger = logging.getLogger(__name__)


class PolicyEvaluator(IPolicyEvaluator):
    """Evaluates strategy metrics against active compliance rules (e.g. max drawdown caps)."""

    def evaluate_policies(self, rules: List[ComplianceRule], metrics: Dict[str, float]) -> List[PolicyEvaluationResult]:
        """Evaluate compliance rules against metrics dict."""
        results = []

        for rule in rules:
            key = rule.criterion_key
            if key not in metrics:
                results.append(PolicyEvaluationResult(
                    rule_id=rule.rule_id,
                    passed=False,
                    message=f"Missing metric key '{key}' required by compliance rule."
                ))
                continue

            val = metrics[key]
            passed = False
            op = rule.operator
            th = rule.threshold

            if op == ">":
                passed = val > th
            elif op == "<":
                passed = val < th
            elif op == "==":
                passed = abs(val - th) < 1e-9
            elif op == ">=":
                passed = val >= th
            elif op == "<=":
                passed = val <= th
            else:
                results.append(PolicyEvaluationResult(
                    rule_id=rule.rule_id,
                    passed=False,
                    message=f"Unsupported operator '{op}' in compliance rule."
                ))
                continue

            message = f"Rule passed. Metric {key}={val:.4f} satisfies {op} {th:.4f}."
            if not passed:
                message = f"Rule breached. Metric {key}={val:.4f} violates {op} {th:.4f}."

            results.append(PolicyEvaluationResult(
                rule_id=rule.rule_id,
                passed=passed,
                message=message
            ))

        return results
