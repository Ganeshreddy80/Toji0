"""Events for the Research Platform (Sprint 6)."""

from __future__ import annotations

from dataclasses import dataclass

from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class ResearchPlatformInitialized(BaseEvent):
    """Fired when the Research Platform plugin initializes successfully."""


@dataclass(frozen=True)
class ResearchPlatformShutdown(BaseEvent):
    """Fired when the Research Platform plugin shuts down cleanly."""


@dataclass(frozen=True)
class ExperimentCreated(BaseEvent):
    """Fired when a new research experiment is created."""


@dataclass(frozen=True)
class ExperimentStarted(BaseEvent):
    """Fired when an experiment execution pipeline begins."""


@dataclass(frozen=True)
class ExperimentCompleted(BaseEvent):
    """Fired when an experiment execution pipeline completes successfully."""


@dataclass(frozen=True)
class ExperimentFailed(BaseEvent):
    """Fired when an experiment execution fails closed."""


@dataclass(frozen=True)
class WalkForwardCompleted(BaseEvent):
    """Fired when walk-forward framework analysis finishes."""


@dataclass(frozen=True)
class ParameterSweepCompleted(BaseEvent):
    """Fired when parameter sweep engine finishes."""


@dataclass(frozen=True)
class ReportGenerated(BaseEvent):
    """Fired when a research report document is generated."""
