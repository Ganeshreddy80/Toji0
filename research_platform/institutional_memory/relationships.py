"""Relationships mapper building lineage parents-children mappings.
"""

from __future__ import annotations

from research_platform.institutional_memory.models import Relationship


class RelationshipMapper:
    """Links memories models."""

    @staticmethod
    def map_link(parent_id: str, child_id: str, link_type: str = "lineage") -> Relationship:
        return Relationship(
            parent_id=parent_id,
            child_id=child_id,
            link_type=link_type
        )
