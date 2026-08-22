"""Tests for the multi-factor scoring engine."""

from __future__ import annotations

from universe.core.models import AssetScore, ScoringWeights, UniverseAsset
from universe.scoring.engine import ScoringEngine


def _make_asset(
    symbol: str = "BTC/USDT",
    volume: float = 1_000_000.0,
    volatility: float = 0.05,
    price_change: float = 2.5,
    exchanges: list[str] | None = None,
) -> UniverseAsset:
    return UniverseAsset(
        symbol=symbol,
        base_asset=symbol.split("/")[0],
        quote_asset=symbol.split("/")[1] if "/" in symbol else "USDT",
        exchanges=exchanges or ["Binance"],
        volume_24h_usd=volume,
        volatility=volatility,
        price_change_pct_24h=price_change,
    )


class TestScoringEngine:
    """Test multi-factor weighted scoring."""

    def test_score_attaches_score_to_assets(self) -> None:
        engine = ScoringEngine()
        assets = [_make_asset(), _make_asset(symbol="ETH/USDT", volume=500_000.0)]
        scored = engine.score(assets)
        assert len(scored) == 2
        for asset in scored:
            assert asset.score is not None
            assert isinstance(asset.score, AssetScore)

    def test_composite_score_in_range(self) -> None:
        engine = ScoringEngine()
        assets = [
            _make_asset(volume=5_000_000.0, volatility=0.1, price_change=5.0),
            _make_asset(symbol="ETH/USDT", volume=100.0, volatility=0.001, price_change=-10.0),
        ]
        scored = engine.score(assets)
        for asset in scored:
            assert 0.0 <= asset.score.composite_score <= 100.0

    def test_higher_volume_scores_higher_liquidity(self) -> None:
        engine = ScoringEngine()
        high_vol = _make_asset(symbol="A/USDT", volume=10_000_000.0)
        low_vol = _make_asset(symbol="B/USDT", volume=1_000.0)
        scored = engine.score([high_vol, low_vol])
        scores = {a.symbol: a.score for a in scored}
        assert scores["A/USDT"].liquidity_score > scores["B/USDT"].liquidity_score

    def test_more_exchanges_scores_higher_coverage(self) -> None:
        engine = ScoringEngine()
        multi = _make_asset(symbol="A/USDT", exchanges=["Binance", "Bybit", "Coinbase"])
        single = _make_asset(symbol="B/USDT", exchanges=["Binance"])
        scored = engine.score([multi, single])
        scores = {a.symbol: a.score for a in scored}
        assert scores["A/USDT"].exchange_coverage_score > scores["B/USDT"].exchange_coverage_score

    def test_custom_weights(self) -> None:
        weights = ScoringWeights(
            liquidity=1.0,
            volatility=0.0,
            momentum=0.0,
            correlation=0.0,
            exchange_coverage=0.0,
        )
        engine = ScoringEngine(weights=weights)
        assets = [_make_asset(volume=1_000_000.0)]
        scored = engine.score(assets)
        # With only liquidity weight, composite should equal liquidity score
        assert scored[0].score.composite_score == scored[0].score.liquidity_score

    def test_score_empty_list(self) -> None:
        engine = ScoringEngine()
        assert engine.score([]) == []

    def test_single_asset_scoring(self) -> None:
        engine = ScoringEngine()
        scored = engine.score([_make_asset()])
        assert len(scored) == 1
        assert scored[0].score is not None
        assert scored[0].score.composite_score > 0

    def test_zero_volume_gets_zero_liquidity(self) -> None:
        engine = ScoringEngine()
        scored = engine.score([_make_asset(volume=0.0)])
        assert scored[0].score.liquidity_score == 0.0
