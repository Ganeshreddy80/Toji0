"""Orchestrator for the Feature Platform, coordinating calculations, stores, and validations.
"""

from __future__ import annotations

import logging
import math as _math
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
import pandas as pd

from toji_platform.core.event_bus import IEventBus
from toji_platform.core.errors import EventBusError

from research_platform.feature_platform.cache import FeatureCache
from research_platform.feature_platform.catalog import FeatureCatalog
from research_platform.feature_platform.dependency_graph import DependencyGraph
from research_platform.feature_platform.events import (
    FeatureCalculated,
    FeatureFreshnessUpdated,
    FeatureImportanceCalculated,
    FeaturePromoted,
    FeatureRegistered,
    FeatureRejected,
    FeatureValidated,
    FeatureVersionCreated
)
from research_platform.feature_platform.feature_pipeline import FeaturePipeline
from research_platform.feature_platform.feature_store import FeatureStore
from research_platform.feature_platform.freshness import FeatureFreshnessEngine
from research_platform.feature_platform.governance import PromotionGovernor
from research_platform.feature_platform.importance import ImportanceFramework
from research_platform.feature_platform.lifecycle import FeatureLifecycleManager
from research_platform.feature_platform.lineage import LineageTracer
from research_platform.feature_platform.models import (
    FeatureApprovalReport,
    FeatureImportanceMetrics,
    FeatureRecord,
    FeatureVersionInfo,
    FeatureFreshnessMetrics,
    OrthogonalizationReport,
    FeatureValidationResult,
    LineageNode
)
from research_platform.feature_platform.orthogonalization import Orthogonalizer
from research_platform.feature_platform.provenance import FeatureProvenanceGraph
from research_platform.feature_platform.registry import FeatureRegistry
from research_platform.feature_platform.repository import (
    FeatureApprovalRepository,
    FeatureFreshnessRepository,
    FeatureImportanceRepository,
    FeatureRepository,
    FeatureVersionRepository
)
from research_platform.feature_platform.validators import FeatureValidator
from research_platform.feature_platform.versioning import FeatureVersionManager

logger = logging.getLogger(__name__)


DEFAULT_FEATURE_DEFINITIONS: List[FeatureRecord] = [
    # Raw OHLCV (Level 0)
    FeatureRecord(
        uuid="feat-open-v1", name="open", display_name="OPEN", description="Open price",
        formula="open", category="Price", subcategory="Raw", owner="quants", author="CTO",
        version="1.0.0", dependencies=[], update_frequency="1m", warmup_length=0, lookback_window=0, required_resolution="1m"
    ),
    FeatureRecord(
        uuid="feat-high-v1", name="high", display_name="HIGH", description="High price",
        formula="high", category="Price", subcategory="Raw", owner="quants", author="CTO",
        version="1.0.0", dependencies=[], update_frequency="1m", warmup_length=0, lookback_window=0, required_resolution="1m"
    ),
    FeatureRecord(
        uuid="feat-low-v1", name="low", display_name="LOW", description="Low price",
        formula="low", category="Price", subcategory="Raw", owner="quants", author="CTO",
        version="1.0.0", dependencies=[], update_frequency="1m", warmup_length=0, lookback_window=0, required_resolution="1m"
    ),
    FeatureRecord(
        uuid="feat-close-v1", name="close", display_name="CLOSE", description="Close price",
        formula="close", category="Price", subcategory="Raw", owner="quants", author="CTO",
        version="1.0.0", dependencies=[], update_frequency="1m", warmup_length=0, lookback_window=0, required_resolution="1m"
    ),
    FeatureRecord(
        uuid="feat-volume-v1", name="volume", display_name="VOLUME", description="Volume",
        formula="volume", category="Volume", subcategory="Raw", owner="quants", author="CTO",
        version="1.0.0", dependencies=[], update_frequency="1m", warmup_length=0, lookback_window=0, required_resolution="1m"
    ),

    # Level 1 Derived
    FeatureRecord(
        uuid="feat-log-return-v1", name="log_return", display_name="LOG_RETURN", description="Log returns of close price",
        formula="log(close/close_prev)", category="Indicator", subcategory="Derived", owner="quants", author="CTO",
        version="1.0.0", dependencies=["close"], update_frequency="1m", warmup_length=1, lookback_window=1, required_resolution="1m"
    ),
    FeatureRecord(
        uuid="feat-atr-v1", name="atr", display_name="ATR", description="Average True Range 14",
        formula="atr(high,low,close,14)", category="Indicator", subcategory="Vol", owner="quants", author="CTO",
        version="1.0.0", dependencies=["high", "low", "close"], update_frequency="1m", warmup_length=14, lookback_window=14, required_resolution="1m"
    ),
    FeatureRecord(
        uuid="feat-ema9-v1", name="ema9", display_name="EMA9", description="Exponential Moving Average 9",
        formula="ema(close,9)", category="Indicator", subcategory="Trend", owner="quants", author="CTO",
        version="1.0.0", dependencies=["close"], update_frequency="1m", warmup_length=9, lookback_window=9, required_resolution="1m"
    ),
    FeatureRecord(
        uuid="feat-ema21-v1", name="ema21", display_name="EMA21", description="Exponential Moving Average 21",
        formula="ema(close,21)", category="Indicator", subcategory="Trend", owner="quants", author="CTO",
        version="1.0.0", dependencies=["close"], update_frequency="1m", warmup_length=21, lookback_window=21, required_resolution="1m"
    ),
    FeatureRecord(
        uuid="feat-ema50-v1", name="ema50", display_name="EMA50", description="Exponential Moving Average 50",
        formula="ema(close,50)", category="Indicator", subcategory="Trend", owner="quants", author="CTO",
        version="1.0.0", dependencies=["close"], update_frequency="1m", warmup_length=50, lookback_window=50, required_resolution="1m"
    ),
    FeatureRecord(
        uuid="feat-rsi-v1", name="rsi", display_name="RSI", description="Relative Strength Index 14",
        formula="rsi(close,14)", category="Indicator", subcategory="Momentum", owner="quants", author="CTO",
        version="1.0.0", dependencies=["close"], update_frequency="1m", warmup_length=14, lookback_window=14, required_resolution="1m"
    ),
    FeatureRecord(
        uuid="feat-vol-change-v1", name="volume_change", display_name="VOLUME_CHANGE", description="Percentage volume change",
        formula="pct_change(volume)", category="Volume", subcategory="Derived", owner="quants", author="CTO",
        version="1.0.0", dependencies=["volume"], update_frequency="1m", warmup_length=1, lookback_window=1, required_resolution="1m"
    ),
    FeatureRecord(
        uuid="feat-support-v1", name="support", display_name="SUPPORT", description="Rolling support level (min low 20)",
        formula="min(low,20)", category="Level", subcategory="Support", owner="quants", author="CTO",
        version="1.0.0", dependencies=["low"], update_frequency="1m", warmup_length=20, lookback_window=20, required_resolution="1m"
    ),
    FeatureRecord(
        uuid="feat-resistance-v1", name="resistance", display_name="RESISTANCE", description="Rolling resistance level (max high 20)",
        formula="max(high,20)", category="Level", subcategory="Resistance", owner="quants", author="CTO",
        version="1.0.0", dependencies=["high"], update_frequency="1m", warmup_length=20, lookback_window=20, required_resolution="1m"
    ),

    # Level 2 Derived
    FeatureRecord(
        uuid="feat-rolling-std-v1", name="rolling_std", display_name="ROLLING_STD", description="Rolling standard deviation of log returns",
        formula="std(log_return,20)", category="Indicator", subcategory="Derived", owner="quants", author="CTO",
        version="1.0.0", dependencies=["log_return"], update_frequency="1m", warmup_length=20, lookback_window=20, required_resolution="1m"
    ),
    FeatureRecord(
        uuid="feat-natr-v1", name="normalized_atr", display_name="NORMALIZED_ATR", description="Normalized ATR (ATR / close)",
        formula="atr / close", category="Indicator", subcategory="Vol", owner="quants", author="CTO",
        version="1.0.0", dependencies=["atr", "close"], update_frequency="1m", warmup_length=14, lookback_window=14, required_resolution="1m"
    ),
    # FP-3D: Canonical annualized realized volatility — primary input for PositionSizingOrchestrator.
    # Formula: sample_std(log_return, 1440) * sqrt(525600)
    # Units: dimensionless annualized fraction (e.g. 0.725 = 72.5%/year for typical BTC).
    # periods_per_year = 525600 = 365 * 24 * 60 (crypto 24/7, 1-minute bars).
    # warmup_length = 1441 = 1 (log_return shift) + 1440 (rolling window).
    # NaN during warm-up — position sizer uses fallback_volatility=0.50 instead.
    FeatureRecord(
        uuid="feat-annualized-vol-v1", name="annualized_vol", display_name="ANNUALIZED_VOL",
        description="Canonical annualized realized volatility: sample_std(log_return,1440) * sqrt(525600)",
        formula="sample_std(log_return,1440) * sqrt(525600)",
        category="Indicator", subcategory="Vol", owner="quants", author="CTO",
        version="1.0.0", dependencies=["log_return"], update_frequency="1m",
        warmup_length=1441, lookback_window=1440, required_resolution="1m"
    ),
    FeatureRecord(
        uuid="feat-breakout-v1", name="breakout", display_name="BREAKOUT", description="Price breakout indicator",
        formula="breakout(close,resistance,support)", category="Signal", subcategory="Breakout", owner="quants", author="CTO",
        version="1.0.0", dependencies=["close", "resistance", "support"], update_frequency="1m", warmup_length=20, lookback_window=20, required_resolution="1m"
    ),
    FeatureRecord(
        uuid="feat-trend-v1", name="trend", display_name="TREND", description="Trend direction indicator (EMA9 vs EMA21)",
        formula="trend(ema9,ema21)", category="Signal", subcategory="Trend", owner="quants", author="CTO",
        version="1.0.0", dependencies=["ema9", "ema21"], update_frequency="1m", warmup_length=21, lookback_window=21, required_resolution="1m"
    ),

    # Level 3 Derived
    FeatureRecord(
        uuid="feat-risk-score-v1", name="risk_score", display_name="RISK_SCORE", description="Risk score from normalized ATR z-score",
        formula="zscore(normalized_atr,50)", category="Indicator", subcategory="Risk", owner="quants", author="CTO",
        version="1.0.0", dependencies=["normalized_atr"], update_frequency="1m", warmup_length=50, lookback_window=50, required_resolution="1m"
    ),

    # Level 4 Derived
    FeatureRecord(
        uuid="feat-signal-v1", name="signal", display_name="SIGNAL", description="Risk trigger signal",
        formula="signal(risk_score,2.0)", category="Indicator", subcategory="Signal", owner="quants", author="CTO",
        version="1.0.0", dependencies=["risk_score"], update_frequency="1m", warmup_length=50, lookback_window=50, required_resolution="1m"
    ),
]

# FP-7D-2: Canonical immutable compute-name constant derived from DEFAULT_FEATURE_DEFINITIONS.
# All production compute sites (paper trading, live trading) must use this constant
# instead of maintaining independent hard-coded feature name lists.
# Immutable tuple prevents accidental mutation by consumers.
DEFAULT_COMPUTE_NAMES: tuple[str, ...] = tuple(
    record.name for record in DEFAULT_FEATURE_DEFINITIONS
)


class FeaturePlatformOrchestrator:
    """Central manager coordinating registry registrations, DAG pipelines, validations, and PIT stores."""

    def __init__(self, event_bus: IEventBus) -> None:
        self._event_bus = event_bus
        self._registry = FeatureRegistry()
        self._repo = FeatureRepository()
        self._store = FeatureStore()
        self._dep_graph = DependencyGraph()
        self._pipeline = FeaturePipeline(self._dep_graph)
        self._validator = FeatureValidator()
        self._cache = FeatureCache()
        self._lineage = LineageTracer()

        # Sprint R3.5 infrastructure managers
        self._version_manager = FeatureVersionManager()
        self._provenance_graph = FeatureProvenanceGraph()
        self._lifecycle_manager = FeatureLifecycleManager(event_bus)
        self._freshness_engine = FeatureFreshnessEngine()
        self._importance_framework = ImportanceFramework()
        self._orthogonalizer = Orthogonalizer()
        self._catalog = FeatureCatalog()
        self._governance = PromotionGovernor(self._validator)

        # Repositories
        self._version_repo = FeatureVersionRepository()
        self._freshness_repo = FeatureFreshnessRepository()
        self._importance_repo = FeatureImportanceRepository()
        self._approval_repo = FeatureApprovalRepository()

    @property
    def registry(self) -> FeatureRegistry:
        return self._registry

    @property
    def store(self) -> FeatureStore:
        return self._store

    @property
    def pipeline(self) -> FeaturePipeline:
        return self._pipeline

    @property
    def dep_graph(self) -> DependencyGraph:
        return self._dep_graph

    @property
    def lineage(self) -> LineageTracer:
        return self._lineage

    @property
    def version_manager(self) -> FeatureVersionManager:
        return self._version_manager

    @property
    def provenance_graph(self) -> FeatureProvenanceGraph:
        return self._provenance_graph

    @property
    def lifecycle_manager(self) -> FeatureLifecycleManager:
        return self._lifecycle_manager

    @property
    def catalog(self) -> FeatureCatalog:
        return self._catalog

    def register_default_features(self) -> None:
        """Register all canonical production feature definitions in topological dependency order once."""
        for record in DEFAULT_FEATURE_DEFINITIONS:
            if self._registry.get(record.name) is None:
                self.register_feature(record)

    def register_feature(self, record: FeatureRecord) -> None:
        """Register a feature, update the dependency graph and lineage tracer, and store definitions."""
        self._registry.register(record)
        self._repo.save_record(record)
        self._dep_graph.add_node(record.name, record.dependencies)
        self._catalog.register_feature(record)

        # Register trace lineage node in core tracer and provenance graph
        node = LineageNode(
            node_id=record.name,
            name=record.display_name,
            type="feature",
            parents=record.dependencies,
            children=[]
        )
        self._lineage.register_node(node)
        self._provenance_graph.register_node(node)

        # Publish event
        self._event_bus.publish(FeatureRegistered(payload={"name": record.name, "version": record.version}))
        logger.info("Registered feature definition: %s v%s", record.name, record.version)

    def register_version(self, info: FeatureVersionInfo) -> None:
        """Save a new feature version info record."""
        self._version_manager.create_version(info)
        self._version_repo.save_version(info)
        self._event_bus.publish(
            FeatureVersionCreated(payload={"name": info.feature_name, "version": info.semantic_version})
        )

    def compute_and_store(
        self,
        names: List[str],
        symbol: str,
        input_df: pd.DataFrame,
        as_of_time: Optional[datetime] = None
    ) -> pd.DataFrame:
        """Compute targets in topological order, validate them, and persist results in PIT store."""
        # Compute through DAG pipeline
        output_df = self._pipeline.compute(names, input_df)

        as_of = as_of_time or datetime.now(timezone.utc)
        
        # Make sure Point-In-Time columns exist in calculated frame
        if "effective_time" not in output_df.columns:
            if "timestamp" in output_df.columns:
                output_df["effective_time"] = output_df["timestamp"]
            else:
                output_df["effective_time"] = as_of  # FP-5 ND-1b fix: use controlled as_of, not a second wall-clock call
        output_df["as_of"] = as_of

        # Validate and store each target
        for name in names:
            record = self._registry.get(name)
            if record is None:
                continue

            # Run validation checks
            validation_res = self._validator.validate(name, output_df)
            try:
                self._event_bus.publish(
                    FeatureValidated(
                        payload={
                            "name": name,
                            "approved": validation_res.is_approved,
                            "nan_ratio": validation_res.nan_ratio
                        }
                    )
                )
            except EventBusError as exc:  # FP-6 FP6-N-1: isolate subscriber failure
                logger.warning("FeatureValidated publish failed (subscriber error): %s", exc)

            if validation_res.is_approved:
                # Save to Offline PIT store
                self._store.save_features(name, record.version, symbol, output_df)
                try:
                    self._event_bus.publish(
                        FeatureCalculated(
                            payload={"name": name, "version": record.version, "symbol": symbol}
                        )
                    )
                except EventBusError as exc:  # FP-6 FP6-N-1: isolate subscriber failure
                    logger.warning("FeatureCalculated publish failed (subscriber error): %s", exc)
                logger.debug("Computed and stored approved feature: %s", name)
            else:
                self._event_bus.publish(FeatureRejected(payload={"name": name, "reason": "Failed validations."}))
                logger.warning("Feature %s failed validation rules. Promotion rejected.", name)

        return output_df

    def query_historical(
        self,
        names: List[str],
        symbols: List[str],
        start: datetime,
        end: datetime
    ) -> pd.DataFrame:
        """Perform historical PIT time-travel query.

        Canonical name — mirrors IFeatureStore.query_historical() and FeatureStore.query_historical().
        """
        return self._store.query_historical(names, symbols, start, end)

    def query_realtime(
        self,
        names: List[str],
        symbols: List[str],
        max_age_seconds: Optional[float] = None,
    ) -> pd.DataFrame:
        """Query latest computed online feature states.

        Args:
            names: Feature names to query.
            symbols: Symbols to query.
            max_age_seconds: Optional staleness TTL in seconds.
                - None (default): exact current behaviour — all stored values returned.
                - > 0: any feature value whose ``as_of`` timestamp is older than
                  ``max_age_seconds`` relative to a single consistent UTC reference
                  time is excluded from the result (value and *_as_of* set to NaN).
                  The symbol row itself is preserved.

        Returns:
            pd.DataFrame with one row per symbol.  When *max_age_seconds* is None
            the output is identical to the pre-FP-7C output.
        """
        df = self._store.query_latest(names, symbols)

        if max_age_seconds is None or df.empty:
            return df

        # Single reference time for the entire call (FP-7C: consistent UTC now)
        now_utc = datetime.now(timezone.utc)
        max_age_td = timedelta(seconds=max_age_seconds)

        for name in names:
            as_of_col = f"{name}_as_of"
            if name not in df.columns or as_of_col not in df.columns:
                continue  # feature not present — already absent, no action needed

            def _is_stale(as_of_val: object) -> bool:
                """Return True if the as_of value is stale or unparseable."""
                # Handle None, NaN float, or pd.NaT (datetime columns use NaT not float NaN)
                if as_of_val is None or pd.isna(as_of_val):
                    return True  # missing as_of treated as stale when TTL is active
                try:
                    ts = pd.Timestamp(as_of_val)
                    # Normalise timezone: naive → assume UTC (repository convention)
                    if ts.tzinfo is None:
                        ts = ts.tz_localize("UTC")
                    return (now_utc - ts) > max_age_td
                except Exception:
                    return True  # malformed as_of treated as stale

            stale_mask = df[as_of_col].apply(_is_stale)
            if stale_mask.any():
                df.loc[stale_mask, name] = float("nan")
                df.loc[stale_mask, as_of_col] = float("nan")

        return df

    def evaluate_freshness(self, name: str, last_update: datetime) -> FeatureFreshnessMetrics:
        """Calculate and store decay freshness score."""
        metrics = self._freshness_engine.calculate_freshness(name, last_update)
        self._freshness_repo.save_freshness(metrics)
        self._event_bus.publish(
            FeatureFreshnessUpdated(payload={"name": name, "freshness_score": metrics.freshness_score})
        )
        return metrics

    def calculate_importance(self, name: str, values: pd.Series, returns: pd.Series) -> FeatureImportanceMetrics:
        """Calculate Mutual Info, IC, and IR scores and store metrics."""
        metrics = self._importance_framework.compute_importance(name, values, returns)
        self._importance_repo.save_importance(metrics)
        self._event_bus.publish(
            FeatureImportanceCalculated(payload={"name": name, "ic": metrics.information_coefficient})
        )
        return metrics

    def check_collinearity(self, name: str, df: pd.DataFrame, threshold: float = 0.85) -> OrthogonalizationReport:
        """Determine collinearity overlays."""
        return self._orthogonalizer.analyze_orthogonal(name, df, threshold)

    def catalog_search(self, category: Optional[str] = None, tags: Optional[List[str]] = None) -> List[FeatureRecord]:
        """Search catalog."""
        return self._catalog.search(category, tags)

    def evaluate_promotion(self, name: str, df: pd.DataFrame) -> FeatureApprovalReport:
        """Evaluate promotion and generate signed report."""
        record = self._registry.get(name)
        report = self._governance.evaluate_promotion(name, df, record)
        self._approval_repo.save_report(report)
        
        # Update lifecycle state depending on promotion report approval status
        if report.validation_status == "APPROVED":
            self._lifecycle_manager.transition_state(name, "APPROVED")
        else:
            self._lifecycle_manager.transition_state(name, "REJECTED")

        return report
