"""Tests for the tiered ranking engine with drift detection."""

from __future__ import annotations

from universe.core.models import (
    AssetRank,
    AssetScore,
    Tier,
    TierBoundaries,
    UniverseAsset,
)
from universe.ranking.engine import RankingEngine


def _make_scored_asset(
    symbol: str,
    composite: float,
    exchanges: list[str] | None = None,
) -> UniverseAsset:
    return UniverseAsset(
        symbol=symbol,
        base_asset=symbol.split("/")[0],
        quote_asset="USDT",
        exchanges=exchanges or ["Binance"],
        score=AssetScore(composite_score=composite),
    )


class TestRankingEngine:
    """Test tiered ranking and drift detection."""

    def test_rank_assigns_tiers(self) -> None:
        engine = RankingEngine()
        # Create 20 assets with decreasing scores
        assets = [
            _make_scored_asset(f"ASSET{i}/USDT", composite=100.0 - i * 5)
            for i in range(20)
        ]
        ranked = engine.rank(assets)
        assert len(ranked) == 20

        # Check that all have ranks
        for asset in ranked:
            assert asset.rank is not None
            assert asset.rank.tier in (Tier.S, Tier.A, Tier.B, Tier.C)

    def test_s_tier_is_top_percentage(self) -> None:
        boundaries = TierBoundaries(s_tier_pct=0.10, a_tier_pct=0.20, b_tier_pct=0.30)
        engine = RankingEngine(boundaries=boundaries)
        assets = [
            _make_scored_asset(f"A{i}/USDT", composite=100.0 - i)
            for i in range(10)
        ]
        ranked = engine.rank(assets)
        s_tier = [a for a in ranked if a.rank.tier == Tier.S]
        assert len(s_tier) >= 1  # At least 10% of 10 = 1

    def test_positions_are_sequential(self) -> None:
        engine = RankingEngine()
        assets = [
            _make_scored_asset(f"A{i}/USDT", composite=50.0 + i)
            for i in range(5)
        ]
        ranked = engine.rank(assets)
        positions = [a.rank.position for a in ranked]
        assert sorted(positions) == list(range(1, 6))

    def test_higher_score_gets_higher_rank(self) -> None:
        engine = RankingEngine()
        assets = [
            _make_scored_asset("LOW/USDT", composite=10.0),
            _make_scored_asset("HIGH/USDT", composite=90.0),
        ]
        ranked = engine.rank(assets)
        rank_map = {a.symbol: a.rank for a in ranked}
        assert rank_map["HIGH/USDT"].position < rank_map["LOW/USDT"].position

    def test_drift_detection_promotion(self) -> None:
        engine = RankingEngine()
        assets = [
            _make_scored_asset(f"A{i}/USDT", composite=100.0 - i * 5)
            for i in range(20)
        ]
        # Previous: A15 was C-tier
        previous_ranks = {
            "A0/USDT": AssetRank(tier=Tier.S, position=1),
            "A15/USDT": AssetRank(tier=Tier.C, position=16),
        }

        # Now make A15 the top scorer
        assets_modified = list(assets)
        for i, a in enumerate(assets_modified):
            if a.symbol == "A15/USDT":
                assets_modified[i] = _make_scored_asset("A15/USDT", composite=99.0)

        ranked = engine.rank(assets_modified, previous_ranks)
        a15 = next(a for a in ranked if a.symbol == "A15/USDT")
        assert a15.rank.promoted is True
        assert a15.rank.previous_tier == Tier.C

    def test_drift_detection_demotion(self) -> None:
        engine = RankingEngine()
        assets = [
            _make_scored_asset(f"A{i}/USDT", composite=100.0 - i * 5)
            for i in range(20)
        ]
        # Previous: A0 was S-tier position 1
        previous_ranks = {
            "A0/USDT": AssetRank(tier=Tier.S, position=1),
        }

        # Now make A0 the worst scorer
        assets_modified = list(assets)
        for i, a in enumerate(assets_modified):
            if a.symbol == "A0/USDT":
                assets_modified[i] = _make_scored_asset("A0/USDT", composite=1.0)

        ranked = engine.rank(assets_modified, previous_ranks)
        a0 = next(a for a in ranked if a.symbol == "A0/USDT")
        assert a0.rank.demoted is True
        assert a0.rank.previous_tier == Tier.S

    def test_rank_empty_list(self) -> None:
        engine = RankingEngine()
        assert engine.rank([]) == []

    def test_single_asset_gets_s_tier(self) -> None:
        engine = RankingEngine()
        ranked = engine.rank([_make_scored_asset("ONLY/USDT", composite=50.0)])
        assert len(ranked) == 1
        assert ranked[0].rank.tier == Tier.S
        assert ranked[0].rank.position == 1
