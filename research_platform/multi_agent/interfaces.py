"""Abstract contracts for the Multi-Agent Decision System.
"""

from __future__ import annotations

import abc
from typing import Any, List, Optional
from research_platform.multi_agent.models import (
    AgentConsensus,
    AgentProposal,
    AgentRequest,
)


class IAgentRepository(abc.ABC):
    """Abstract contract for persisting agent sessions, proposals, and consensus decisions."""

    @abc.abstractmethod
    def save_session(self, request: AgentRequest) -> None:
        """Persist a new agent request session."""

    @abc.abstractmethod
    def get_session(self, session_id: str) -> Optional[AgentRequest]:
        """Retrieve a session by ID."""

    @abc.abstractmethod
    def save_proposal(self, session_id: str, proposal: AgentProposal) -> None:
        """Persist an agent's individual proposal."""

    @abc.abstractmethod
    def list_proposals(self, session_id: str) -> List[AgentProposal]:
        """List proposals registered in a session."""

    @abc.abstractmethod
    def save_consensus(self, consensus: AgentConsensus) -> None:
        """Persist the compiled consensus recommendation."""

    @abc.abstractmethod
    def get_consensus(self, session_id: str) -> Optional[AgentConsensus]:
        """Retrieve a consensus record by session ID."""


class IAgentDecisionEngine(abc.ABC):
    """Abstract contract for generating proposals from a specific agent role."""

    @abc.abstractmethod
    def evaluate_proposal(self, request: AgentRequest, proposals_so_far: List[AgentProposal]) -> AgentProposal:
        """Evaluate context and propose parameters adjustments."""


class IMultiAgentOrchestrator(abc.ABC):
    """Abstract contract for the multi-agent system orchestrator."""

    @abc.abstractmethod
    def execute_session(self, strategy_id: str, parameters: dict, context: dict) -> AgentConsensus:
        """Orchestrate specialized agent collaborations and compile a consensus recommendation."""
