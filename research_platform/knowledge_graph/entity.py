"""Entity mapper registering core domain elements.
"""

from __future__ import annotations

from typing import Any, Dict

from research_platform.knowledge_graph.models import Entity


class EntityMapper:
    """Wraps domain objects (trades, backtests, configurations) as Graph Entities."""

    @staticmethod
    def wrap_entity(entity_id: str, node_type: str, props: Dict[str, Any]) -> Entity:
        return Entity(
            entity_id=entity_id,
            node_type=node_type,
            properties=props
        )
