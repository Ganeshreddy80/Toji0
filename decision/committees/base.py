"""Abstract Base Committee interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from decision.models import CommitteeVote


class BaseCommittee(ABC):
    """Abstract interface and helper class representing a specialized evaluating committee."""

    @abstractmethod
    def vote(self, context: dict[str, Any]) -> CommitteeVote:
        """Evaluate the provided context and produce a structured CommitteeVote.

        Args:
            context: Dictionary containing analytical, risk, timing, research,
                     and market data metrics.

        Returns:
            CommitteeVote object.
        """
        pass
