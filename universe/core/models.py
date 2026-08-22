"""Strongly-typed domain models for the Universe Manager.

All models are Pydantic with frozen configs. No hardcoded assets.
Every threshold, weight, and tier boundary is configurable.
"""

from __future__ import annotations

import enum
from datetime import datetime
from pydantic import BaseModel, Field

from toji_platform.core.types import AssetClass


# ── Enums ──────────────────────────────────────────────────────────────────


class Tier(str, enum.Enum):
    """Asset quality tier classification."""

    S = "S"
    A = "A"
    B = "B"
    C = "C"
    UNRANKED = "UNRANKED"


class ContractType(str, enum.Enum):
    """Type of trading contract."""

    SPOT = "spot"
    PERPETUAL = "perpetual"
    FUTURES = "futures"
    MARGIN = "margin"
    UNKNOWN = "unknown"


class WatchlistType(str, enum.Enum):
    """Watchlist management mode."""

    AUTO = "auto"
    MANUAL = "manual"


class FilterOperator(str, enum.Enum):
    """Comparison operator for filter rules."""

    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    EQ = "eq"
    NEQ = "neq"
    IN = "in"
    NOT_IN = "not_in"


# ── Score Models ───────────────────────────────────────────────────────────


class AssetScore(BaseModel):
    """Multi-factor score breakdown for a single asset."""

    liquidity_score: float = Field(default=0.0, ge=0.0, le=100.0, description="Score based on 24h volume and depth")
    volatility_score: float = Field(default=0.0, ge=0.0, le=100.0, description="Score based on price volatility")
    momentum_score: float = Field(default=0.0, ge=0.0, le=100.0, description="Score based on recent price movement")
    correlation_score: float = Field(default=0.0, ge=0.0, le=100.0, description="Diversification value (inverse BTC corr)")
    exchange_coverage_score: float = Field(default=0.0, ge=0.0, le=100.0, description="Multi-exchange availability")
    composite_score: float = Field(default=0.0, ge=0.0, le=100.0, description="Weighted composite of all factors")

    model_config = {"frozen": True}


class ScoringWeights(BaseModel):
    """Configurable weights for composite score calculation."""

    liquidity: float = Field(default=0.30, ge=0.0, le=1.0)
    volatility: float = Field(default=0.20, ge=0.0, le=1.0)
    momentum: float = Field(default=0.20, ge=0.0, le=1.0)
    correlation: float = Field(default=0.15, ge=0.0, le=1.0)
    exchange_coverage: float = Field(default=0.15, ge=0.0, le=1.0)

    model_config = {"frozen": True}

    @property
    def total(self) -> float:
        """Sum of all weights (used as denominator)."""
        return (
            self.liquidity
            + self.volatility
            + self.momentum
            + self.correlation
            + self.exchange_coverage
        )


# ── Rank Models ────────────────────────────────────────────────────────────


class AssetRank(BaseModel):
    """Tier and position ranking for a single asset."""

    tier: Tier = Field(default=Tier.UNRANKED)
    position: int = Field(default=0, ge=0, description="Absolute rank position (1 = best)")
    previous_tier: Tier | None = Field(default=None, description="Tier from previous scan")
    previous_position: int | None = Field(default=None, description="Position from previous scan")
    position_delta: int = Field(default=0, description="Change in position since last scan")
    promoted: bool = Field(default=False, description="True if moved to a higher tier")
    demoted: bool = Field(default=False, description="True if moved to a lower tier")

    model_config = {"frozen": True}


class TierBoundaries(BaseModel):
    """Configurable tier percentage boundaries.

    Values represent the percentage of total assets in each tier.
    Must sum to 1.0.
    """

    s_tier_pct: float = Field(default=0.05, gt=0.0, lt=1.0, description="Top N% for S-Tier")
    a_tier_pct: float = Field(default=0.15, gt=0.0, lt=1.0, description="Next N% for A-Tier")
    b_tier_pct: float = Field(default=0.30, gt=0.0, lt=1.0, description="Next N% for B-Tier")

    model_config = {"frozen": True}

    @property
    def c_tier_pct(self) -> float:
        """Remaining percentage for C-Tier."""
        return max(0.0, 1.0 - self.s_tier_pct - self.a_tier_pct - self.b_tier_pct)


# ── Asset Models ───────────────────────────────────────────────────────────


class UniverseAsset(BaseModel):
    """Enriched asset model — the primary domain entity.

    Tracks an asset from discovery through scoring and ranking.
    """

    symbol: str = Field(..., description="Canonical symbol (e.g. BTC/USDT)")
    base_asset: str = Field(..., description="Base asset identifier (e.g. BTC)")
    quote_asset: str = Field(..., description="Quote asset identifier (e.g. USDT)")
    exchanges: list[str] = Field(default_factory=list, description="Exchanges listing this asset")
    asset_class: AssetClass = Field(default=AssetClass.CRYPTO)
    contract_type: ContractType = Field(default=ContractType.SPOT)

    # Metadata (populated by MetadataEngine)
    tick_size: float | None = Field(default=None, gt=0.0)
    lot_size: float | None = Field(default=None, gt=0.0)
    min_notional: float | None = Field(default=None, ge=0.0)
    fee_tier: str | None = Field(default=None, description="Fee tier classification")
    launch_date: datetime | None = Field(default=None, description="Approximate listing date")

    # Market data snapshots (populated during scoring)
    volume_24h_usd: float = Field(default=0.0, ge=0.0, description="24h trading volume in USD")
    price_usd: float = Field(default=0.0, ge=0.0, description="Current mid-price in USD")
    price_change_pct_24h: float = Field(default=0.0, description="24h price change percentage")
    volatility: float = Field(default=0.0, ge=0.0, description="Recent realized volatility")

    # Score (attached by ScoringEngine)
    score: AssetScore | None = Field(default=None)

    # Rank (attached by RankingEngine)
    rank: AssetRank | None = Field(default=None)

    # Timestamps
    discovered_at: datetime | None = Field(default=None)
    last_updated: datetime | None = Field(default=None)

    model_config = {"frozen": False}  # Mutable to allow pipeline enrichment


# ── Filter Models ──────────────────────────────────────────────────────────


class FilterRule(BaseModel):
    """A single configurable filter rule."""

    name: str = Field(..., description="Rule identifier")
    field: str = Field(..., description="Asset field to evaluate (e.g. 'volume_24h_usd')")
    operator: FilterOperator = Field(..., description="Comparison operator")
    threshold: float | str | list[str] = Field(..., description="Comparison value")
    enabled: bool = Field(default=True)

    model_config = {"frozen": True}


class FilterResult(BaseModel):
    """Result of evaluating a filter rule against an asset."""

    symbol: str = Field(...)
    rule_name: str = Field(...)
    passed: bool = Field(...)
    reason: str = Field(default="")

    model_config = {"frozen": True}


# ── Watchlist Models ───────────────────────────────────────────────────────


class WatchlistEntry(BaseModel):
    """A single asset entry in a watchlist."""

    symbol: str = Field(...)
    reason: str = Field(default="", description="Why this asset was added")
    added_at: datetime | None = Field(default=None)
    composite_score: float = Field(default=0.0, description="Score snapshot at time of addition")
    tier: Tier = Field(default=Tier.UNRANKED)

    model_config = {"frozen": True}


class Watchlist(BaseModel):
    """A named collection of watched assets."""

    name: str = Field(..., description="Watchlist identifier")
    watchlist_type: WatchlistType = Field(default=WatchlistType.AUTO)
    entries: list[WatchlistEntry] = Field(default_factory=list)
    last_updated: datetime | None = Field(default=None)
    description: str = Field(default="")

    model_config = {"frozen": False}  # Mutable for add/remove operations


# ── Snapshot Model ─────────────────────────────────────────────────────────


class UniverseSnapshot(BaseModel):
    """Complete state of a universe scan — the atomic unit of persistence."""

    scan_id: str = Field(..., description="Unique identifier for this scan")
    scanned_at: datetime = Field(..., description="Timestamp of scan completion")
    total_discovered: int = Field(default=0)
    total_after_filter: int = Field(default=0)
    assets: list[UniverseAsset] = Field(default_factory=list)
    tier_distribution: dict[str, int] = Field(default_factory=dict)
    watchlists: list[Watchlist] = Field(default_factory=list)
    drift_count: int = Field(default=0, description="Number of tier changes from previous scan")
    provider_statuses: dict[str, str] = Field(default_factory=dict)

    model_config = {"frozen": True}


# ── Configuration Model ───────────────────────────────────────────────────


class UniverseConfig(BaseModel):
    """Top-level configuration for the Universe Manager.

    All thresholds, weights, and boundaries are here.
    No hardcoded values anywhere else in the system.
    """

    # Scoring
    scoring_weights: ScoringWeights = Field(default_factory=ScoringWeights)

    # Ranking
    tier_boundaries: TierBoundaries = Field(default_factory=TierBoundaries)

    # Filter defaults
    min_volume_24h_usd: float = Field(default=100_000.0, description="Minimum 24h USD volume")
    min_price_usd: float = Field(default=0.001, description="Minimum price in USD")
    allowed_quote_assets: list[str] = Field(
        default_factory=lambda: ["USDT", "BUSD", "USD", "USDC"],
        description="Only include pairs with these quote assets",
    )
    min_listing_age_days: int = Field(default=7, description="Minimum days since listing")
    blacklisted_symbols: list[str] = Field(default_factory=list, description="Symbols to always exclude")
    whitelisted_symbols: list[str] = Field(default_factory=list, description="Symbols to always include")

    # Scheduler
    scan_interval_seconds: int = Field(default=14400, description="Scan frequency (default: 4 hours)")

    # Storage
    max_snapshot_history: int = Field(default=50, description="Max snapshots to retain")

    model_config = {"frozen": True}
