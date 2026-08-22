"""Lessons Engine generating lessons learned records.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from research_platform.institutional_memory.models import LessonLearnedRecord


class LessonsEngine:
    """Transforms trade parameters into structured learning records."""

    @staticmethod
    def extract_lesson(
        trade_id: str,
        observation: str,
        hypothesis: str,
        evidence: str,
        confidence: float,
        recommended_action: str
    ) -> LessonLearnedRecord:
        """Construct a structured lesson."""
        return LessonLearnedRecord(
            lesson_id=f"les-{uuid.uuid4().hex[:8]}",
            trade_id=trade_id,
            observation=observation,
            hypothesis=hypothesis,
            evidence=evidence,
            confidence=confidence,
            recommended_action=recommended_action,
            validation_status="PENDING_RESEARCH"
        )
