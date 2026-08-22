"""Tests for the configurable filter engine."""

from __future__ import annotations

from universe.core.models import (
    FilterOperator,
    FilterRule,
    UniverseAsset,
    UniverseConfig,
)
from universe.filters.engine import FilterEngine


def _make_asset(
    symbol: str = "BTC/USDT",
    base: str = "BTC",
    quote: str = "USDT",
    volume: float = 1_000_000.0,
    price: float = 95000.0,
) -> UniverseAsset:
    return UniverseAsset(
        symbol=symbol,
        base_asset=base,
        quote_asset=quote,
        volume_24h_usd=volume,
        price_usd=price,
    )


class TestFilterEngine:
    """Test configurable filter chain."""

    def test_default_filters_pass_valid_asset(self) -> None:
        config = UniverseConfig(min_volume_24h_usd=100_000.0, min_price_usd=0.001)
        engine = FilterEngine(config=config)
        assets = [_make_asset(volume=500_000.0, price=95000.0)]
        passed, results = engine.apply(assets)
        assert len(passed) == 1
        assert passed[0].symbol == "BTC/USDT"

    def test_volume_filter_rejects_low_volume(self) -> None:
        config = UniverseConfig(min_volume_24h_usd=1_000_000.0)
        engine = FilterEngine(config=config)
        assets = [_make_asset(volume=500.0)]
        passed, results = engine.apply(assets)
        assert len(passed) == 0
        rejected = [r for r in results if not r.passed]
        assert len(rejected) >= 1
        assert "min_volume" in rejected[0].rule_name

    def test_price_filter_rejects_low_price(self) -> None:
        config = UniverseConfig(min_price_usd=1.0)
        engine = FilterEngine(config=config)
        assets = [_make_asset(price=0.0001)]
        passed, _ = engine.apply(assets)
        assert len(passed) == 0

    def test_quote_asset_filter(self) -> None:
        config = UniverseConfig(
            allowed_quote_assets=["USDT"],
            min_volume_24h_usd=0.0,
            min_price_usd=0.0,
        )
        engine = FilterEngine(config=config)
        assets = [
            _make_asset(quote="USDT"),
            _make_asset(symbol="BTC/EUR", base="BTC", quote="EUR"),
        ]
        passed, _ = engine.apply(assets)
        assert len(passed) == 1
        assert passed[0].symbol == "BTC/USDT"

    def test_blacklist_rejects_symbol(self) -> None:
        config = UniverseConfig(blacklisted_symbols=["BTC/USDT"])
        engine = FilterEngine(config=config)
        assets = [_make_asset()]
        passed, results = engine.apply(assets)
        assert len(passed) == 0
        rejected = [r for r in results if not r.passed]
        assert any("blacklist" in r.rule_name for r in rejected)

    def test_whitelist_overrides_rejection(self) -> None:
        config = UniverseConfig(
            min_volume_24h_usd=999_999_999.0,  # Would reject everything
            whitelisted_symbols=["BTC/USDT"],
        )
        engine = FilterEngine(config=config)
        assets = [_make_asset(volume=1.0)]
        passed, results = engine.apply(assets)
        assert len(passed) == 1
        assert passed[0].symbol == "BTC/USDT"

    def test_custom_rules(self) -> None:
        custom = [
            FilterRule(
                name="high_volume_only",
                field="volume_24h_usd",
                operator=FilterOperator.GT,
                threshold=2_000_000.0,
            )
        ]
        engine = FilterEngine(custom_rules=custom)
        assets = [
            _make_asset(symbol="A/USDT", base="A", volume=3_000_000.0),
            _make_asset(symbol="B/USDT", base="B", volume=500_000.0),
        ]
        passed, _ = engine.apply(assets)
        assert len(passed) == 1
        assert passed[0].symbol == "A/USDT"

    def test_disabled_rule_is_skipped(self) -> None:
        custom = [
            FilterRule(
                name="disabled_rule",
                field="volume_24h_usd",
                operator=FilterOperator.GT,
                threshold=999_999_999.0,
                enabled=False,
            )
        ]
        engine = FilterEngine(custom_rules=custom)
        assets = [_make_asset(volume=1.0)]
        passed, _ = engine.apply(assets)
        assert len(passed) == 1

    def test_empty_assets_returns_empty(self) -> None:
        engine = FilterEngine()
        passed, results = engine.apply([])
        assert passed == []
        assert results == []
