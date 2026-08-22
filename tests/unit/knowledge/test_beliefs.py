"""Unit tests for the BeliefEngine belief node lifecycles."""

from __future__ import annotations

import pytest

from knowledge.beliefs.engine import BeliefEngine
from knowledge.models import Belief


def test_create_belief():
    """Verify belief claim node creation and default attributes."""
    engine = BeliefEngine()
    belief = engine.create_belief(
        claim="BTC exhibitions indicate long momentum trend",
        evidence_ids=["ev-1", "ev-2"],
        confidence=0.75,
    )
    
    assert isinstance(belief, Belief)
    assert belief.claim == "BTC exhibitions indicate long momentum trend"
    assert belief.confidence == 0.75
    assert belief.evidence_ids == ["ev-1", "ev-2"]
    assert belief.is_retired is False
    
    # Verify retrieval
    retrieved = engine.get_belief(belief.belief_id)
    assert retrieved == belief


def test_update_belief_history():
    """Verify belief updates append old states to version history."""
    engine = BeliefEngine()
    belief = engine.create_belief("ETH trend following", ["ev-1"], confidence=0.5)
    
    # Update belief
    updated = engine.update_belief(belief.belief_id, new_confidence=0.8, new_evidence_ids=["ev-1", "ev-2"])
    
    assert updated.confidence == 0.8
    assert updated.evidence_ids == ["ev-1", "ev-2"]
    
    # Retrieve history
    history = engine.get_belief_history(belief.belief_id)
    assert len(history) == 1
    assert history[0].confidence == 0.5
    assert history[0].evidence_ids == ["ev-1"]


def test_retire_belief():
    """Verify retirement sets confidence to zero and flags state."""
    engine = BeliefEngine()
    belief = engine.create_belief("Solana scaling", [], 0.6)
    
    retired = engine.retire_belief(belief.belief_id)
    assert retired.is_retired is True
    assert retired.confidence == 0.0
    
    # List active beliefs should not include retired ones
    active = engine.list_beliefs(include_retired=False)
    assert len(active) == 0
    
    # All beliefs list should include retired
    all_beliefs = engine.list_beliefs(include_retired=True)
    assert len(all_beliefs) == 1


def test_declare_conflict():
    """Verify declaring conflicts links both belief nodes together."""
    engine = BeliefEngine()
    b1 = engine.create_belief("BTC is bullish", [], 0.6)
    b2 = engine.create_belief("BTC is bearish", [], 0.7)
    
    b1_c, b2_c = engine.declare_conflict(b1.belief_id, b2.belief_id)
    
    assert b2.belief_id in b1_c.conflicting_belief_ids
    assert b1.belief_id in b2_c.conflicting_belief_ids
    
    # Verify in backing store
    assert b2.belief_id in engine.get_belief(b1.belief_id).conflicting_belief_ids
