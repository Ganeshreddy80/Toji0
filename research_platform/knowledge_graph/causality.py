"""Causality Engine analyzing root cause of drawdown events.
"""

from __future__ import annotations

from typing import List

from research_platform.knowledge_graph.models import RootCauseResult


class CausalityEngine:
    """Traces failed_due_to relationship edges to diagnose system failures."""

    def __init__(self, repository) -> None:
        self.repository = repository

    def analyze_root_cause(self, target_node_id: str) -> RootCauseResult:
        """Find nodes triggering drawdown faults."""
        edges = self.repository.list_edges()
        
        # Look for failed_due_to or caused relations
        culprit = None
        for e in edges:
            if e.source_id == target_node_id and e.relationship_type in ["failed_due_to", "caused"]:
                culprit = e.target_id
                break

        if culprit:
            explanation = f"Drawdown target {target_node_id} was caused by failure in node {culprit}."
            confidence = 0.90
        else:
            culprit = "unknown"
            explanation = "No explicit root cause connection mapping detected."
            confidence = 0.0

        return RootCauseResult(
            target_node_id=target_node_id,
            culprit_node_id=culprit,
            explanation=explanation,
            confidence=confidence
        )
