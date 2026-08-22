"""Thread-safe, append-only repository for storing agent sessions and proposals.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional
from research_platform.multi_agent.interfaces import IAgentRepository
from research_platform.multi_agent.models import (
    AgentConsensus,
    AgentProposal,
    AgentRequest,
)


class AgentRepository(IAgentRepository):
    """Memory-backed, thread-safe repository implementation."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: Dict[str, AgentRequest] = {}
        self._proposals: Dict[str, List[AgentProposal]] = {}
        self._consensus: Dict[str, AgentConsensus] = {}

    def save_session(self, request: AgentRequest) -> None:
        with self._lock:
            self._sessions[request.session_id] = request

    def get_session(self, session_id: str) -> Optional[AgentRequest]:
        with self._lock:
            return self._sessions.get(session_id)

    def save_proposal(self, session_id: str, proposal: AgentProposal) -> None:
        with self._lock:
            if session_id not in self._proposals:
                self._proposals[session_id] = []
            self._proposals[session_id].append(proposal)

    def list_proposals(self, session_id: str) -> List[AgentProposal]:
        with self._lock:
            return list(self._proposals.get(session_id, []))

    def save_consensus(self, consensus: AgentConsensus) -> None:
        with self._lock:
            self._consensus[consensus.session_id] = consensus

    def get_consensus(self, session_id: str) -> Optional[AgentConsensus]:
        with self._lock:
            return self._consensus.get(session_id)
