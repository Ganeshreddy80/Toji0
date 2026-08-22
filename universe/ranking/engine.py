"""Tiered asset ranking engine with drift detection.

Sorts scored assets by composite score, assigns S/A/B/C tiers,
and detects promotions/demotions compared to the previous scan.
"""

from __future__ import annotations

import logging
import math

from universe.core.interfaces import IAssetRanker
from universe.core.models import (
    AssetRank,
    Tier,
    TierBoundaries,
    UniverseAsset,
)

logger = logging.getLogger(__name__)


class RankingEngine(IAssetRanker):
    """Rank scored assets into tiers with drift detection.

    Tier Assignment:
    - S-Tier: top N% (default 5%)
    - A-Tier: next N% (default 15%)
    - B-Tier: next N% (default 30%)
    - C-Tier: remaining (default 50%)

    Drift Detection:
    - Compares current rank to previous_ranks
    - Flags promotions (moved to higher tier)
    - Flags demotions (moved to lower tier)
    """

    # Tier ordering for comparison (higher index = better tier)
    _TIER_ORDER: dict[Tier, int] = {
        Tier.UNRANKED: 0,
        Tier.C: 1,
        Tier.B: 2,
        Tier.A: 3,
        Tier.S: 4,
    }

    def __init__(self, boundaries: TierBoundaries | None = None) -> None:
        self._boundaries = boundaries or TierBoundaries()

    def rank(
        self,
        assets: list[UniverseAsset],
        previous_ranks: dict[str, AssetRank] | None = None,
    ) -> list[UniverseAsset]:
        """Assign tier rankings and detect drift.

        Assets must have scores attached (score.composite_score).
        """
        if not assets:
            return []

        previous = previous_ranks or {}

        # Sort by composite score descending
        sorted_assets = sorted(
            assets,
            key=lambda a: a.score.composite_score if a.score else 0.0,
            reverse=True,
        )

        total = len(sorted_assets)
        # Calculate tier boundaries (absolute positions)
        s_count = max(1, math.ceil(total * self._boundaries.s_tier_pct))
        a_count = max(1, math.ceil(total * self._boundaries.a_tier_pct))
        b_count = max(1, math.ceil(total * self._boundaries.b_tier_pct))

        ranked: list[UniverseAsset] = []
        for position_idx, asset in enumerate(sorted_assets):
            position = position_idx + 1  # 1-indexed

            # Assign tier
            if position <= s_count:
                tier = Tier.S
            elif position <= s_count + a_count:
                tier = Tier.A
            elif position <= s_count + a_count + b_count:
                tier = Tier.B
            else:
                tier = Tier.C

            # Drift detection
            prev = previous.get(asset.symbol)
            previous_tier = prev.tier if prev else None
            previous_position = prev.position if prev else None
            position_delta = (previous_position - position) if previous_position else 0
            promoted = False
            demoted = False

            if prev:
                current_order = self._TIER_ORDER[tier]
                prev_order = self._TIER_ORDER[prev.tier]
                promoted = current_order > prev_order
                demoted = current_order < prev_order

            rank = AssetRank(
                tier=tier,
                position=position,
                previous_tier=previous_tier,
                previous_position=previous_position,
                position_delta=position_delta,
                promoted=promoted,
                demoted=demoted,
            )

            ranked_asset = asset.model_copy(update={"rank": rank})
            ranked.append(ranked_asset)

        # Log tier distribution
        tier_dist = self._compute_distribution(ranked)
        logger.info(
            "Ranking: %d assets ranked — S:%d A:%d B:%d C:%d",
            total,
            tier_dist.get("S", 0),
            tier_dist.get("A", 0),
            tier_dist.get("B", 0),
            tier_dist.get("C", 0),
        )
        return ranked

    def _compute_distribution(
        self, assets: list[UniverseAsset]
    ) -> dict[str, int]:
        """Count assets per tier."""
        dist: dict[str, int] = {}
        for asset in assets:
            if asset.rank:
                tier_name = asset.rank.tier.value
                dist[tier_name] = dist.get(tier_name, 0) + 1
        return dist
