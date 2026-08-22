"""Relationship Validator enforcing type constraints on links.
"""

from __future__ import annotations

from typing import List

from research_platform.knowledge_graph.models import KnowledgeNode

VALID_RELATIONSHIPS = [
    "created_by", "generated", "derived_from", "uses", "depends_on",
    "validated_by", "reviewed_by", "approved_by", "executed_by",
    "caused", "triggered", "belongs_to", "learned_from", "improved",
    "failed_due_to", "version_of", "references", "related_to",
    "replaced_by", "supersedes"
]


class RelationshipValidator:
    """Enforces constraint rules before saving connection edges."""

    @staticmethod
    def validate_link(
        source_node: KnowledgeNode,
        target_node: KnowledgeNode,
        relationship: str
    ) -> bool:
        """Validate if the connection is allowed."""
        if relationship not in VALID_RELATIONSHIPS:
            return False

        # Constraint check: STRATEGY uses/depends_on INDICATOR, etc.
        s_type = source_node.node_type
        t_type = target_node.node_type

        # Human approvals shouldn't be executed_by trades
        if s_type == "HUMAN_APPROVAL" and relationship == "executed_by":
            return False

        return True
