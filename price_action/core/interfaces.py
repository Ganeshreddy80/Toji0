"""Abstract interfaces for the Price Action Engine."""

from __future__ import annotations

import abc
from datetime import datetime
from typing import Any

from market_intelligence.core.models import MarketState
from price_action.core.enums import PatternStatus, PatternType
from price_action.core.models import (
    DetectorContext,
    FairValueGap,
    LiquidityPool,
    MarketRegimeState,
    MarketStructureState,
    MomentumMetrics,
    MultiTimeframePriceActionSnapshot,
    OrderBlock,
    PatternCandidate,
    PatternMatch,
    PatternSnapshot,
    PatternState,
    PriceActionBar,
    PriceActionConfig,
    PriceActionFeatures,
    PriceActionSwing,
    PremiumDiscountState,
    TimeframePriceActionSnapshot,
    TrendMetrics,
    VolatilityMetrics,
)


class IPatternStateStore(abc.ABC):
    """Contract for in-memory, thread-safe Price Action state tracking."""

    @abc.abstractmethod
    def get_snapshot(self, symbol: str) -> PatternSnapshot | None:
        """Retrieve the current state snapshot for a symbol.

        Args:
            symbol: Target ticker symbol.

        Returns:
            The current PatternSnapshot, or None if not initialized.
        """

    @abc.abstractmethod
    def update_snapshot(self, snapshot: PatternSnapshot) -> None:
        """Update the active state snapshot in a thread-safe manner.

        Args:
            snapshot: The new snapshot to set.
        """

    @abc.abstractmethod
    def get_history(self, symbol: str, limit: int = 100) -> list[PatternSnapshot]:
        """Retrieve in-memory history of snapshots for a symbol.

        Args:
            symbol: Target ticker symbol.
            limit: Maximum snapshots to return.

        Returns:
            List of snapshots sorted chronologically.
        """

    @abc.abstractmethod
    def update_timeframe_state(
        self, symbol: str, timeframe: str, state_update: PatternState
    ) -> PatternSnapshot:
        """Safely apply a timeframe update to the active snapshot.

        Args:
            symbol: Target ticker symbol.
            timeframe: Target timeframe string.
            state_update: Timeframe state details.

        Returns:
            The updated PatternSnapshot.
        """

    @abc.abstractmethod
    def query(
        self,
        symbol: str,
        pattern_type: PatternType | None = None,
        status: PatternStatus | None = None,
    ) -> list[PatternMatch]:
        """Query currently tracked patterns.

        Args:
            symbol: Target ticker symbol.
            pattern_type: Optional pattern filter.
            status: Optional status filter.

        Returns:
            List of matching PatternMatch records.
        """

    @abc.abstractmethod
    def clear(self) -> None:
        """Purge all tracked states from memory."""


class IPatternRepository(abc.ABC):
    """Contract for persisting and loading price action snapshots and pattern matches."""

    @abc.abstractmethod
    def save_snapshot(self, snapshot: PatternSnapshot) -> None:
        """Persist a pattern snapshot.

        Args:
            snapshot: The snapshot to persist.
        """

    @abc.abstractmethod
    def load_snapshot(self, snapshot_id: str) -> PatternSnapshot | None:
        """Load a specific pattern snapshot by its unique ID.

        Args:
            snapshot_id: Unique snapshot identifier.

        Returns:
            The loaded PatternSnapshot, or None if not found.
        """

    @abc.abstractmethod
    def load_latest_snapshot(self, symbol: str) -> PatternSnapshot | None:
        """Load the most recent snapshot for a given symbol.

        Args:
            symbol: Target ticker symbol.

        Returns:
            The latest PatternSnapshot, or None if none exists.
        """

    @abc.abstractmethod
    def get_historical_snapshots(
        self, symbol: str, start: datetime, end: datetime
    ) -> list[PatternSnapshot]:
        """Load historical snapshots for a symbol over a specific timeframe.

        Args:
            symbol: Target ticker symbol.
            start: Start boundary timestamp.
            end: End boundary timestamp.

        Returns:
            List of matching snapshots sorted by timestamp.
        """

    @abc.abstractmethod
    def load_patterns(
        self,
        symbol: str,
        timeframe: str | None = None,
        pattern_type: PatternType | None = None,
        status: PatternStatus | None = None,
    ) -> list[PatternMatch]:
        """Load pattern match history from the repository.

        Args:
            symbol: Target ticker symbol.
            timeframe: Optional timeframe filter.
            pattern_type: Optional pattern filter.
            status: Optional status filter.

        Returns:
            List of matching PatternMatch records.
        """


class IPatternDetector(abc.ABC):
    """Contract for pluggable chart pattern detection engines."""

    @property
    @abc.abstractmethod
    def detector_id(self) -> str:
        """Unique identifier of the pattern detector."""

    @abc.abstractmethod
    def detect(self, context: DetectorContext) -> tuple[list[PatternCandidate], list[PatternMatch]]:
        """Run pattern detection logic against market state context.

        Args:
            context: The detector context containing all required inputs.

        Returns:
            A tuple of (candidates, confirmed_matches).
        """


# =============================================================================
# Sprint 5 Detector & Engine Interfaces
# =============================================================================

class ISwingDetector(abc.ABC):
    """Protocol for swing pivot point detection."""

    @abc.abstractmethod
    def detect_swings(
        self, bars: list[PriceActionBar], config: PriceActionConfig | None = None
    ) -> list[PriceActionSwing]:
        """Identify pivot highs and pivot lows across candle history."""


class IMarketStructureDetector(abc.ABC):
    """Protocol for market structure shift and BOS/CHOCH detection."""

    @abc.abstractmethod
    def detect_market_structure(
        self, bars: list[PriceActionBar], swings: list[PriceActionSwing], config: PriceActionConfig | None = None
    ) -> MarketStructureState:
        """Analyze swing structure for BOS, CHOCH, and structural trend bias."""


class ITrendEngine(abc.ABC):
    """Protocol for trend analysis."""

    @abc.abstractmethod
    def analyze_trend(
        self, bars: list[PriceActionBar], config: PriceActionConfig | None = None
    ) -> TrendMetrics:
        """Evaluate moving average alignment and trend direction/strength."""


class IVolatilityEngine(abc.ABC):
    """Protocol for volatility metric evaluation."""

    @abc.abstractmethod
    def analyze_volatility(
        self, bars: list[PriceActionBar], config: PriceActionConfig | None = None
    ) -> VolatilityMetrics:
        """Calculate ATR, Bollinger Bands, bandwidth, and squeeze states."""


class IMomentumEngine(abc.ABC):
    """Protocol for momentum and divergence evaluation."""

    @abc.abstractmethod
    def analyze_momentum(
        self, bars: list[PriceActionBar], swings: list[PriceActionSwing], config: PriceActionConfig | None = None
    ) -> MomentumMetrics:
        """Calculate RSI, MACD, and momentum divergence against price swings."""


class ILiquidityEngine(abc.ABC):
    """Protocol for liquidity pool (BSL/SSL) detection."""

    @abc.abstractmethod
    def detect_liquidity(
        self, bars: list[PriceActionBar], swings: list[PriceActionSwing], config: PriceActionConfig | None = None
    ) -> list[LiquidityPool]:
        """Detect Buy-Side and Sell-Side liquidity pools and sweep events."""


class IFairValueGapDetector(abc.ABC):
    """Protocol for Fair Value Gap (FVG) detection."""

    @abc.abstractmethod
    def detect_fvgs(
        self, bars: list[PriceActionBar], config: PriceActionConfig | None = None
    ) -> list[FairValueGap]:
        """Identify 3-candle imbalance gaps and mitigation status."""


class IOrderBlockDetector(abc.ABC):
    """Protocol for institutional Order Block detection."""

    @abc.abstractmethod
    def detect_order_blocks(
        self, bars: list[PriceActionBar], swings: list[PriceActionSwing], config: PriceActionConfig | None = None
    ) -> list[OrderBlock]:
        """Identify bullish and bearish institutional Order Blocks."""


class IPremiumDiscountEngine(abc.ABC):
    """Protocol for Premium / Discount zone calculation."""

    @abc.abstractmethod
    def calculate_zones(
        self, current_price: float, swings: list[PriceActionSwing], config: PriceActionConfig | None = None
    ) -> PremiumDiscountState | None:
        """Calculate dealing range equilibrium, premium, and discount levels."""


class IMarketRegimeEngine(abc.ABC):
    """Protocol for macro market regime classification."""

    @abc.abstractmethod
    def classify_regime(
        self,
        trend: TrendMetrics,
        volatility: VolatilityMetrics,
        market_structure: MarketStructureState,
        config: PriceActionConfig | None = None,
    ) -> MarketRegimeState:
        """Synthesize trend, volatility, and structure into a market regime classification."""


class IMultiTimeframeAggregator(abc.ABC):
    """Protocol for multi-timeframe price action aggregation."""

    @abc.abstractmethod
    def aggregate_snapshots(
        self, symbol: str, timeframe_snapshots: dict[str, TimeframePriceActionSnapshot]
    ) -> MultiTimeframePriceActionSnapshot:
        """Aggregate single-timeframe price action snapshots into an MTF snapshot."""


class IPriceActionFeatureStore(abc.ABC):
    """Contract for in-memory, thread-safe storage of price action snapshots & features."""

    @abc.abstractmethod
    def store_snapshot(self, snapshot: MultiTimeframePriceActionSnapshot) -> None:
        """Store a multi-timeframe price action snapshot."""

    @abc.abstractmethod
    def get_latest_snapshot(self, symbol: str) -> MultiTimeframePriceActionSnapshot | None:
        """Fetch the latest snapshot for a symbol."""

    @abc.abstractmethod
    def get_features(self, symbol: str, timeframe: str = "1h") -> PriceActionFeatures | None:
        """Fetch derived price action features for a symbol and timeframe."""

    @abc.abstractmethod
    def clear(self) -> None:
        """Purge stored feature store data."""

