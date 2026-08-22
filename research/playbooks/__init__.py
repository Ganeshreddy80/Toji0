"""Quantitative research workflows and playbooks engine."""

from research.playbooks.implementations import (
    BreakoutResearchPlaybook,
    FactorResearchPlaybook,
    MacroResearchPlaybook,
    MeanReversionResearchPlaybook,
    MomentumResearchPlaybook,
)
from research.playbooks.interfaces import IPlaybook

__all__ = [
    "IPlaybook",
    "MomentumResearchPlaybook",
    "MeanReversionResearchPlaybook",
    "BreakoutResearchPlaybook",
    "MacroResearchPlaybook",
    "FactorResearchPlaybook",
]
