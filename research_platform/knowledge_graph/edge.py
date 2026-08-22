"""Edge Engine constructing KnowledgeEdge connections.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from research_platform.knowledge_graph.models import EdgeMetadata, KnowledgeEdge


class EdgeEngine:
    """Manages directed edges creation and properties configurations."""

    @staticmethod
    def create_edge(
        source_id: str,
        target_id: str,
        relationship_type: str,
        subsystem: str,
        properties: Dict[str, Any] = None
    ) -> KnowledgeEdge:
        meta = EdgeMetadata(
            subsystem=subsystem
        )

        return KnowledgeEdge(
            edge_id=f"ed-{uuid.uuid4()}",
            source_id=source_id,
            target_id=target_id,
            relationship_type=relationship_type.lower(),
            version=1,
            properties=properties or {},
            metadata=meta
        )
