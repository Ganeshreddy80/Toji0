"""Node Engine constructing KnowledgeNode records with incremented versions.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from research_platform.knowledge_graph.models import KnowledgeNode, NodeMetadata


class NodeEngine:
    """Manages version updates for entity nodes in the graph."""

    @staticmethod
    def create_node(
        node_id: str,
        node_type: str,
        subsystem: str,
        event: str,
        author: str,
        properties: Dict[str, Any] = None
    ) -> KnowledgeNode:
        meta = NodeMetadata(
            subsystem=subsystem,
            originating_event=event,
            author=author
        )

        return KnowledgeNode(
            node_id=node_id,
            node_type=node_type.upper(),
            version=1,
            properties=properties or {},
            metadata=meta
        )

    @staticmethod
    def increment_version(node: KnowledgeNode, updated_properties: Dict[str, Any]) -> KnowledgeNode:
        """Create new version node with updated properties metadata."""
        return KnowledgeNode(
            node_id=node.node_id,
            node_type=node.node_type,
            version=node.version + 1,
            properties=updated_properties,
            metadata=node.metadata,
            created_at=datetime.now(timezone.utc)
        )
