"""Event contracts for the Knowledge Graph Engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class NodeRegistered(BaseEvent):
    """Fired when a KnowledgeNode is persisted."""
    pass


@dataclass(frozen=True)
class EdgeRegistered(BaseEvent):
    """Fired when a KnowledgeEdge is persisted."""
    pass


@dataclass(frozen=True)
class GraphSnapshotCreated(BaseEvent):
    """Fired when a snapshot is serialized."""
    pass


@dataclass(frozen=True)
class TraversalExecuted(BaseEvent):
    """Fired when multi-hop queries execute."""
    pass


@dataclass(frozen=True)
class LessonEvaluated(BaseEvent):
    """Fired when trade lessons validate."""
    pass


@dataclass(frozen=True)
class RelationshipValidated(BaseEvent):
    """Fired when parent-child links verify."""
    pass
