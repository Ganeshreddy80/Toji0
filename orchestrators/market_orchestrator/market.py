"""Market Orchestrator for data ingestion, validation, and feature computation."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import pandas as pd

from data.quality.analyzer import DataQualityAnalyzer
from data.schemas.market_data import OHLCV
from toji_platform.core.event_bus.events import MarketDataUpdated

if TYPE_CHECKING:
    from data.feature_store.cache import FeatureCache
    from data.feature_store.registry import FeatureRegistry
    from data.providers.interfaces import IMarketDataProvider
    from toji_platform.core.event_bus.interfaces import IEventBus


class MarketOrchestrator:
    """Coordinates providers, validates ingestion, calculates features, and publishes updates."""

    def __init__(
        self,
        event_bus: IEventBus,
        provider: IMarketDataProvider,
        feature_cache: FeatureCache,
        feature_registry: FeatureRegistry,
        quality_analyzer: DataQualityAnalyzer | None = None,
    ) -> None:
        """Initialize the MarketOrchestrator.

        Args:
            event_bus: Kernel Event Bus.
            provider: Market data provider implementation.
            feature_cache: Active Feature Store Cache.
            feature_registry: Feature definition registry.
            quality_analyzer: Data validation analyzer.
        """
        self.event_bus = event_bus
        self.provider = provider
        self.feature_cache = feature_cache
        self.feature_registry = feature_registry
        self.quality_analyzer = quality_analyzer or DataQualityAnalyzer()

    def process_market_data(
        self,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: datetime,
    ) -> None:
        """Fetch market data, run quality validation, compute and cache features, then publish.

        Args:
            symbol: Target asset ticker.
            interval: Standard timeframe.
            start_time: Historical start time.
            end_time: Historical end time.
        """
        # 1. Ingestion
        ohlcv_list = self.provider.get_historical_ohlcv(
            symbol, interval, start_time, end_time
        )
        if not ohlcv_list:
            return

        # 2. Schema Validation
        records = [bar.model_dump() for bar in ohlcv_list]
        schema_result = self.quality_analyzer.validate_schema(records, OHLCV)
        if not schema_result.passed:
            raise ValueError(
                f"Ingestion schema violation for symbol {symbol}: {schema_result.errors}"
            )

        # 3. Create pandas DataFrame
        df = pd.DataFrame(records)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df.set_index("timestamp", inplace=True)
        df.sort_index(inplace=True)

        # 4. Quality Rules Verification
        dup_result = self.quality_analyzer.check_duplicates(df)
        order_result = self.quality_analyzer.check_ordering(df)
        integrity_result = self.quality_analyzer.check_integrity(df)

        if not (dup_result.passed and order_result.passed and integrity_result.passed):
            errors = dup_result.errors + order_result.errors + integrity_result.errors
            raise ValueError(
                f"Data quality checks failed for symbol {symbol}: {errors}"
            )

        # 5. Feature Store calculations
        definitions = self.feature_registry.list_all()
        features_payload = {}
        for dfn in definitions:
            feature_df = dfn.calculate(df)
            self.feature_cache.save_features(
                symbol, dfn.name, dfn.version, feature_df
            )
            # Extracted technical columns only
            feat_cols = [
                c for c in feature_df.columns if c not in df.columns
            ]
            if feat_cols:
                features_payload[dfn.name] = feature_df[feat_cols].to_dict(
                    orient="list"
                )

        # 6. Event Dispatches
        event_payload = {
            "symbol": symbol,
            "interval": interval,
            "prices": df["close"].tolist(),
            "volumes": df["volume"].tolist(),
            "features": features_payload,
        }
        event = MarketDataUpdated(
            source="MarketOrchestrator", payload=event_payload
        )
        self.event_bus.publish(event)
