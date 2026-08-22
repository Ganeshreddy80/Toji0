"""Orchestrator coordinating structured memory publication, lineage links, and replay triggers.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from toji_platform.core.event_bus import IEventBus

from research_platform.institutional_memory.events import (
    LessonLearned,
    MemoryPersisted,
    RelationshipLinked,
    ReplayCompleted,
    ReplayStarted
)
from research_platform.institutional_memory.interfaces import IInstitutionalMemoryOrchestrator
from research_platform.institutional_memory.lessons import LessonsEngine
from research_platform.institutional_memory.models import LessonLearnedRecord, Relationship, ReplaySnapshot
from research_platform.institutional_memory.relationships import RelationshipMapper
from research_platform.institutional_memory.replay import DeterministicReplayEngine
from research_platform.institutional_memory.repository import InstitutionalMemoryRepository
from research_platform.institutional_memory.search import MemorySearchEngine

logger = logging.getLogger(__name__)


class InstitutionalMemoryOrchestrator(IInstitutionalMemoryOrchestrator):
    """Coordinates search queries and context replay rebuilds."""

    def __init__(self, event_bus: IEventBus) -> None:
        self._event_bus = event_bus
        self._repo = InstitutionalMemoryRepository()
        
        # Engines
        self._replay_engine = DeterministicReplayEngine(self._repo)
        self._search_engine = MemorySearchEngine(self._repo)
        self._lessons_engine = LessonsEngine()

    @property
    def repository(self) -> InstitutionalMemoryRepository:
        return self._repo

    def publish_memory(self, category: str, record: Any) -> None:
        """Persist memory log under domain type and publish Event Bus notifications."""
        self._repo.save_memory(category, record)
        
        mem_id = getattr(getattr(record, "metadata", None), "memory_id", "unknown")
        self._event_bus.publish(
            MemoryPersisted(payload={"memory_id": mem_id, "category": category})
        )

    def link_memories(self, parent_id: str, child_id: str, link_type: str = "lineage") -> Relationship:
        """Create connection lineage link mapping parent to child."""
        rel = RelationshipMapper.map_link(parent_id, child_id, link_type)
        self._repo.save_relationship(rel)
        
        self._event_bus.publish(
            RelationshipLinked(payload={"parent_id": parent_id, "child_id": child_id})
        )
        return rel

    def reconstruct_historical_state(self, ts: datetime) -> ReplaySnapshot:
        """Run Replay Engine to compile system state context at historical timestamp."""
        self._event_bus.publish(ReplayStarted(payload={"target_timestamp": ts.isoformat()}))
        
        snap = self._replay_engine.reconstruct_state(ts)
        
        self._event_bus.publish(ReplayCompleted(payload={"target_timestamp": ts.isoformat()}))
        return snap

    def execute_search(self, query_str: str, filters: Dict[str, Any]) -> List[Any]:
        """Perform search queries against memory database tables."""
        return self._search_engine.search_memories(query_str, filters)

    def learn_from_trade(
        self,
        trade_id: str,
        observation: str,
        hypothesis: str,
        evidence: str,
        confidence: float,
        recommended_action: str
    ) -> LessonLearnedRecord:
        """Extract structured lesson and publish notification."""
        lesson = self._lessons_engine.extract_lesson(
            trade_id, observation, hypothesis, evidence, confidence, recommended_action
        )
        
        self._repo.save_memory("lessons", lesson)
        self._event_bus.publish(
            LessonLearned(payload={"lesson_id": lesson.lesson_id, "trade_id": trade_id})
        )
        return lesson
