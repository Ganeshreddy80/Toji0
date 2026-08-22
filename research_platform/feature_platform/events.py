"""Event contracts for the Feature Platform.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class FeatureRegistered(BaseEvent):
    """Fired when a new feature is registered in the platform."""
    pass


@dataclass(frozen=True)
class FeatureUpdated(BaseEvent):
    """Fired when a feature definition metadata is updated."""
    pass


@dataclass(frozen=True)
class FeatureDeleted(BaseEvent):
    """Fired when a feature is deleted or archived."""
    pass


@dataclass(frozen=True)
class FeatureCalculated(BaseEvent):
    """Fired when a feature's calculated values are committed to the store."""
    pass


@dataclass(frozen=True)
class FeatureValidated(BaseEvent):
    """Fired when a feature completes validation checks."""
    pass


@dataclass(frozen=True)
class FeatureCached(BaseEvent):
    """Fired when calculation results are committed to memory/disk cache."""
    pass


@dataclass(frozen=True)
class FeatureExpired(BaseEvent):
    """Fired when cached feature values decay past freshness window."""
    pass


@dataclass(frozen=True)
class FeaturePromotionRequested(BaseEvent):
    """Fired when a feature is requested for promotion to production-ready status."""
    pass


@dataclass(frozen=True)
class FeaturePromoted(BaseEvent):
    """Fired when a feature is approved and promoted."""
    pass


@dataclass(frozen=True)
class FeatureRejected(BaseEvent):
    """Fired when a feature fails validation or promotion reviews."""
    pass


@dataclass(frozen=True)
class FeatureLineageUpdated(BaseEvent):
    """Fired when dependencies or execution chains shift."""
    pass


@dataclass(frozen=True)
class FeatureVersionCreated(BaseEvent):
    """Fired when a new version info is logged for a feature."""
    pass


@dataclass(frozen=True)
class FeatureVersionValidated(BaseEvent):
    """Fired when a version completes audit validations."""
    pass


@dataclass(frozen=True)
class FeatureFreshnessUpdated(BaseEvent):
    """Fired when freshness index decays or refreshes."""
    pass


@dataclass(frozen=True)
class FeatureImportanceCalculated(BaseEvent):
    """Fired when mutual information or IC scores are finalized."""
    pass


@dataclass(frozen=True)
class FeatureHealthUpdated(BaseEvent):
    """Fired when quality or stationarity states change."""
    pass


@dataclass(frozen=True)
class FeatureCatalogUpdated(BaseEvent):
    """Fired when new tags or indices are rebuilt."""
    pass
