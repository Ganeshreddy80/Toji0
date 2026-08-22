"""Belief engine to create, update, retire, and trace historical belief snapshots."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from knowledge.models import Belief


class BeliefEngine:
    """Manages quantitative claims (beliefs), version histories, and conflict mappings."""

    def __init__(self) -> None:
        self._beliefs: dict[str, Belief] = {}
        # Tracks belief_id -> list of historical Belief snapshots (ordered old to new)
        self._history: dict[str, list[Belief]] = {}

    def create_belief(self, claim: str, evidence_ids: list[str], confidence: float = 0.5) -> Belief:
        """Create and register a new Belief claim node."""
        b_id = str(uuid.uuid4())
        belief = Belief(
            belief_id=b_id,
            claim=claim,
            confidence=confidence,
            evidence_ids=evidence_ids,
            is_retired=False,
            conflicting_belief_ids=[],
            created_at=datetime.now(timezone.utc)
        )
        self._beliefs[b_id] = belief
        self._history[b_id] = []
        return belief

    def update_belief(
        self,
        belief_id: str,
        new_confidence: float | None = None,
        new_evidence_ids: list[str] | None = None,
    ) -> Belief:
        """Update an existing belief's properties and archive the old state to version history."""
        if belief_id not in self._beliefs:
            raise KeyError(f"Belief '{belief_id}' does not exist.")
            
        old_belief = self._beliefs[belief_id]
        
        # Save snapshot to history
        self._history[belief_id].append(old_belief)
        
        # Create updated belief
        new_belief = Belief(
            belief_id=old_belief.belief_id,
            claim=old_belief.claim,
            confidence=new_confidence if new_confidence is not None else old_belief.confidence,
            evidence_ids=new_evidence_ids if new_evidence_ids is not None else old_belief.evidence_ids,
            is_retired=old_belief.is_retired,
            conflicting_belief_ids=old_belief.conflicting_belief_ids,
            created_at=datetime.now(timezone.utc)
        )
        self._beliefs[belief_id] = new_belief
        return new_belief

    def retire_belief(self, belief_id: str) -> Belief:
        """Mark a belief claim as retired/inactive."""
        if belief_id not in self._beliefs:
            raise KeyError(f"Belief '{belief_id}' does not exist.")
            
        old_belief = self._beliefs[belief_id]
        self._history[belief_id].append(old_belief)
        
        retired_belief = Belief(
            belief_id=old_belief.belief_id,
            claim=old_belief.claim,
            confidence=0.0,  # Zero confidence when retired
            evidence_ids=old_belief.evidence_ids,
            is_retired=True,
            conflicting_belief_ids=old_belief.conflicting_belief_ids,
            created_at=datetime.now(timezone.utc)
        )
        self._beliefs[belief_id] = retired_belief
        return retired_belief

    def declare_conflict(self, belief_id_a: str, belief_id_b: str) -> tuple[Belief, Belief]:
        """Declare that two beliefs conflict with each other, linking their IDs."""
        if belief_id_a not in self._beliefs or belief_id_b not in self._beliefs:
            raise KeyError("Both conflicting beliefs must exist.")
            
        b_a = self._beliefs[belief_id_a]
        b_b = self._beliefs[belief_id_b]
        
        # Save historical snapshots
        self._history[belief_id_a].append(b_a)
        self._history[belief_id_b].append(b_b)
        
        # Link A to B
        new_conflicts_a = list(set(b_a.conflicting_belief_ids + [belief_id_b]))
        b_a_new = Belief(
            belief_id=b_a.belief_id,
            claim=b_a.claim,
            confidence=b_a.confidence,
            evidence_ids=b_a.evidence_ids,
            is_retired=b_a.is_retired,
            conflicting_belief_ids=new_conflicts_a,
            created_at=datetime.now(timezone.utc)
        )
        self._beliefs[belief_id_a] = b_a_new
        
        # Link B to A
        new_conflicts_b = list(set(b_b.conflicting_belief_ids + [belief_id_a]))
        b_b_new = Belief(
            belief_id=b_b.belief_id,
            claim=b_b.claim,
            confidence=b_b.confidence,
            evidence_ids=b_b.evidence_ids,
            is_retired=b_b.is_retired,
            conflicting_belief_ids=new_conflicts_b,
            created_at=datetime.now(timezone.utc)
        )
        self._beliefs[belief_id_b] = b_b_new
        
        return b_a_new, b_b_new

    def get_belief(self, belief_id: str) -> Belief | None:
        """Retrieve a specific active belief."""
        return self._beliefs.get(belief_id)

    def list_beliefs(self, include_retired: bool = False) -> list[Belief]:
        """List all registered beliefs."""
        if include_retired:
            return list(self._beliefs.values())
        return [b for b in self._beliefs.values() if not b.is_retired]

    def get_belief_history(self, belief_id: str) -> list[Belief]:
        """Retrieve chronological snapshot list of a belief's history."""
        return self._history.get(belief_id, [])
