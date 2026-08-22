"""Domain events for the Multi-Agent Decision System.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class AgentSessionStarted(BaseEvent):
    """Fired when an agent collaborative session starts."""
    pass


@dataclass(frozen=True)
class AgentProposalSubmitted(BaseEvent):
    """Fired when an individual agent registers a proposal."""
    pass


@dataclass(frozen=True)
class AgentConsensusReached(BaseEvent):
    """Fired when the AI reviewer aggregates and logs the final consensus recommendations."""
    pass
