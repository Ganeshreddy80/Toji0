"""Evidence engine for storing and querying quantitative proofs."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from knowledge.models import Evidence, SourceReference


class EvidenceEngine:
    """Manages empirical evidence backed by concrete research, metrics, and runs."""

    def __init__(self) -> None:
        self._evidence: dict[str, Evidence] = {}

    def register_evidence(
        self,
        source_type: str,
        source_id: str,
        description: str,
        metric_name: str,
        metric_value: float,
        sample_size: int = 0,
    ) -> Evidence:
        """Register and store a new evidence entry."""
        evidence_id = str(uuid.uuid4())
        ref = SourceReference(
            ref_type=source_type,
            ref_id=source_id,
            description=description
        )
        
        evidence = Evidence(
            evidence_id=evidence_id,
            source=ref,
            metric_name=metric_name,
            metric_value=metric_value,
            sample_size=sample_size,
            created_at=datetime.now(timezone.utc)
        )
        self._evidence[evidence_id] = evidence
        return evidence

    def get_evidence(self, evidence_id: str) -> Evidence | None:
        """Retrieve evidence by its ID."""
        return self._evidence.get(evidence_id)

    def list_evidence(self) -> list[Evidence]:
        """List all registered evidence."""
        return list(self._evidence.values())

    def get_evidence_by_source(self, source_id: str) -> list[Evidence]:
        """Query evidence by its source identifier."""
        return [e for e in self._evidence.values() if e.source.ref_id == source_id]
