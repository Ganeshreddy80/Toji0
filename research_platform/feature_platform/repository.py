"""Database repositories for feature definitions, metadata, and validation logs.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional

from research_platform.feature_platform.interfaces import (
    IFeatureMetadataRepository,
    IFeatureRepository
)
from research_platform.feature_platform.models import (
    FeatureMetadata,
    FeatureRecord,
    FeatureVersionInfo,
    FeatureFreshnessMetrics,
    FeatureImportanceMetrics,
    FeatureApprovalReport,
    FeatureQualityScore
)


class FeatureRepository(IFeatureRepository):
    """Memory repository for saving and loading registered feature definitions."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._db: Dict[str, FeatureRecord] = {}

    def save_record(self, record: FeatureRecord) -> None:
        """Persist a feature definition record."""
        with self._lock:
            self._db[record.name] = record

    def load_record(self, name: str) -> Optional[FeatureRecord]:
        """Load a feature definition record."""
        with self._lock:
            return self._db.get(name)

    def load_all(self) -> List[FeatureRecord]:
        """Load all registered feature definitions."""
        with self._lock:
            return list(self._db.values())


class FeatureMetadataRepository(IFeatureMetadataRepository):
    """Memory repository for saving and loading extended feature metadata properties."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._db: Dict[str, FeatureMetadata] = {}

    def save_meta(self, meta: FeatureMetadata) -> None:
        """Persist feature metadata information."""
        with self._lock:
            self._db[meta.feature_name] = meta

    def load_meta(self, name: str) -> Optional[FeatureMetadata]:
        """Load feature metadata information."""
        with self._lock:
            return self._db.get(name)


class FeatureVersionRepository:
    """Memory repository for saving and loading semantic version audits."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._db: Dict[tuple[str, str], FeatureVersionInfo] = {}

    def save_version(self, info: FeatureVersionInfo) -> None:
        with self._lock:
            self._db[(info.feature_name, info.semantic_version)] = info

    def get_version(self, name: str, version: str) -> Optional[FeatureVersionInfo]:
        with self._lock:
            return self._db.get((name, version))


class FeatureFreshnessRepository:
    """Memory repository for saving freshness metrics snapshots."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._db: Dict[str, FeatureFreshnessMetrics] = {}

    def save_freshness(self, metrics: FeatureFreshnessMetrics) -> None:
        with self._lock:
            self._db[metrics.feature_name] = metrics

    def get_freshness(self, name: str) -> Optional[FeatureFreshnessMetrics]:
        with self._lock:
            return self._db.get(name)


class FeatureImportanceRepository:
    """Memory repository for logging historical feature importance scores."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._db: Dict[str, List[FeatureImportanceMetrics]] = {}

    def save_importance(self, metrics: FeatureImportanceMetrics) -> None:
        with self._lock:
            if metrics.feature_name not in self._db:
                self._db[metrics.feature_name] = []
            self._db[metrics.feature_name].append(metrics)

    def get_importance_history(self, name: str) -> List[FeatureImportanceMetrics]:
        with self._lock:
            return list(self._db.get(name, []))


class FeatureApprovalRepository:
    """Memory repository for logging signed governance approval reports."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._db: Dict[str, FeatureApprovalReport] = {}

    def save_report(self, report: FeatureApprovalReport) -> None:
        with self._lock:
            self._db[report.feature_name] = report

    def get_report(self, name: str) -> Optional[FeatureApprovalReport]:
        with self._lock:
            return self._db.get(name)
