"""Abstract contracts for the Feature Platform, enforcing Dependency Inversion.
"""

from __future__ import annotations

import abc
from datetime import datetime
from typing import Any, Dict, List, Optional
import pandas as pd

from research_platform.feature_platform.models import (
    FeatureRecord,
    FeatureMetadata,
    FeatureValidationResult,
    LineageNode,
    FeatureVersionInfo,
    FeatureFreshnessMetrics,
    FeatureQualityScore,
    FeatureImportanceMetrics,
    OrthogonalizationReport,
    FeatureMathematicalMetadata,
    FeatureApprovalReport
)


class IFeatureRegistry(abc.ABC):
    """Abstract contract for registering and listing quantitative features."""

    @abc.abstractmethod
    def register(self, record: FeatureRecord) -> None:
        """Register a feature in the metadata store."""

    @abc.abstractmethod
    def get(self, name: str) -> Optional[FeatureRecord]:
        """Fetch feature details by unique technical name."""

    @abc.abstractmethod
    def list_all(self) -> List[FeatureRecord]:
        """Return all registered features."""


class IFeatureStore(abc.ABC):
    """Abstract contract for offline/online versioned feature storage."""

    @abc.abstractmethod
    def save_features(self, name: str, version: str, symbol: str, df: pd.DataFrame) -> None:
        """Save computed feature values for a symbol."""

    @abc.abstractmethod
    def query_historical(
        self,
        names: List[str],
        symbols: List[str],
        start_time: datetime,
        end_time: datetime
    ) -> pd.DataFrame:
        """Perform time-travel Point-In-Time query over historical dates."""

    @abc.abstractmethod
    def query_latest(self, names: List[str], symbols: List[str]) -> pd.DataFrame:
        """Fetch latest computed feature states for stream/live executions."""


class IFeaturePipeline(abc.ABC):
    """Abstract contract for executing DAG-based feature computations."""

    @abc.abstractmethod
    def compute(self, names: List[str], input_df: pd.DataFrame) -> pd.DataFrame:
        """Compute the requested features in topological order, reusing cached intermediate nodes."""


class IFeatureValidator(abc.ABC):
    """Abstract contract for validating feature performance, leakage, and drift."""

    @abc.abstractmethod
    def validate(self, name: str, df: pd.DataFrame) -> FeatureValidationResult:
        """Analyze a computed feature dataframe for data quality and leakage checks."""


class IFeatureScheduler(abc.ABC):
    """Abstract contract for scheduling background calculations."""

    @abc.abstractmethod
    def schedule(self, trigger_type: str, interval_sec: int, names: List[str]) -> None:
        """Setup execution triggers for specific features."""


class IFeatureRepository(abc.ABC):
    """Abstract database repository contract for feature persistence."""

    @abc.abstractmethod
    def save_record(self, record: FeatureRecord) -> None:
        """Persist a feature definition record."""

    @abc.abstractmethod
    def load_record(self, name: str) -> Optional[FeatureRecord]:
        """Load a feature definition record."""

    @abc.abstractmethod
    def load_all(self) -> List[FeatureRecord]:
        """Load all registered feature definitions."""


class IFeatureCache(abc.ABC):
    """Abstract contract for memory/disk caching."""

    @abc.abstractmethod
    def get(self, cache_key: str) -> Optional[pd.DataFrame]:
        """Retrieve cached calculations."""

    @abc.abstractmethod
    def set(self, cache_key: str, df: pd.DataFrame) -> None:
        """Cache calculations."""


class IFeatureMetadataRepository(abc.ABC):
    """Abstract database repository contract for extended metadata properties."""

    @abc.abstractmethod
    def save_meta(self, meta: FeatureMetadata) -> None:
        """Persist feature metadata information."""

    @abc.abstractmethod
    def load_meta(self, name: str) -> Optional[FeatureMetadata]:
        """Load feature metadata information."""


class ILineageTracer(abc.ABC):
    """Abstract contract for tracing feature data flow lineage."""

    @abc.abstractmethod
    def register_node(self, node: LineageNode) -> None:
        """Register a node in the lineage trace map."""

    @abc.abstractmethod
    def get_lineage(self, node_id: str) -> List[LineageNode]:
        """Trace lineage path backward to root sources."""


class IFeatureVersionManager(abc.ABC):
    """Tracks version history, hashes, and promotion status."""

    @abc.abstractmethod
    def create_version(self, info: FeatureVersionInfo) -> None:
        """Save a new feature version info record."""

    @abc.abstractmethod
    def get_version(self, name: str, version: str) -> Optional[FeatureVersionInfo]:
        """Fetch version info."""


class IFeatureFreshnessEngine(abc.ABC):
    """Tracks decay models and expiration metrics."""

    @abc.abstractmethod
    def calculate_freshness(self, name: str, last_update: datetime) -> FeatureFreshnessMetrics:
        """Compute freshness and age based on exponential decay half-life."""


class IImportanceFramework(abc.ABC):
    """Analyzes prediction values against a target returns vector."""

    @abc.abstractmethod
    def compute_importance(self, feature_name: str, values: pd.Series, returns: pd.Series) -> FeatureImportanceMetrics:
        """Compute Mutual Information, Information Coefficient (IC), and Information Ratio (IR)."""


class IOrthogonalizer(abc.ABC):
    """Checks for collinearity and recommends grouping/removals."""

    @abc.abstractmethod
    def analyze_orthogonal(self, name: str, df: pd.DataFrame, threshold: float) -> OrthogonalizationReport:
        """Compare correlation with existing dataframe columns and recommend actions."""


class IFeatureCatalog(abc.ABC):
    """Searchable catalog index mapping categories and asset classes."""

    @abc.abstractmethod
    def search(self, category: Optional[str] = None, tags: Optional[List[str]] = None) -> List[FeatureRecord]:
        """Filter registered features by category or tag filters."""


class IPromotionGovernor(abc.ABC):
    """Promotion gateway validating definitions before approving candidate promotion."""

    @abc.abstractmethod
    def evaluate_promotion(self, name: str, df: pd.DataFrame) -> FeatureApprovalReport:
        """Analyze validation checks and output signed approval reports."""
