"""Unit tests for the Scanner."""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from data.schemas.market_data import AssetMetadata
from toji_platform.core.types import AssetClass
from intelligence.universe.manager import UniverseManager
from intelligence.eligibility.evaluator import StrategyEligibilityConstraints
from intelligence.models import RiskGrade
from intelligence.scanner.scanner import Scanner


@pytest.fixture
def scanner_and_universe() -> tuple[Scanner, UniverseManager]:
    """Provide a Scanner instance and its associated UniverseManager."""
    um = UniverseManager()

    # Register assets
    btc = AssetMetadata(
        symbol="BTC/USDT",
        asset_class=AssetClass.CRYPTO,
        base_asset="BTC",
        quote_asset="USDT",
        exchange="Binance",
    )
    um.register_asset(btc, sector="L1", market_group="Majors", custom_attributes={"evidence_count": 3})

    eth = AssetMetadata(
        symbol="ETH/USDT",
        asset_class=AssetClass.CRYPTO,
        base_asset="ETH",
        quote_asset="USDT",
        exchange="Coinbase",
    )
    um.register_asset(eth, sector="L1", market_group="Majors", custom_attributes={"evidence_count": 1})

    aapl = AssetMetadata(
        symbol="AAPL",
        asset_class=AssetClass.STOCKS,
        base_asset="AAPL",
        quote_asset="USD",
        exchange="NASDAQ",
    )
    um.register_asset(aapl, sector="Tech", market_group="US Equities", custom_attributes={"evidence_count": 0})

    scanner = Scanner(universe_manager=um)
    return scanner, um


def test_scan_produces_opportunities(scanner_and_universe: tuple[Scanner, UniverseManager]) -> None:
    """Test that a scanner scan compiles valid opportunities."""
    scanner, um = scanner_and_universe

    # 1. Setup mock data
    market_data = {
        "BTC/USDT": {
            "prices": [100.0, 102.0, 104.0, 106.0, 108.0, 111.0],  # Markup regime
            "volumes": [1000.0, 1200.0, 1100.0, 1300.0, 1400.0, 1800.0],
            "spreads": [0.0002, 0.0003, 0.0002, 0.0001, 0.0002, 0.0002],
        },
        "ETH/USDT": {
            "prices": [100.0, 99.0, 100.5, 99.5, 100.0, 100.2],  # Consolidation
            "volumes": [1000.0, 1100.0, 1200.0, 1300.0, 1500.0, 1700.0],
            "spreads": [0.0005, 0.0006, 0.0005, 0.0006, 0.0005, 0.0005],
        },
    }

    # 2. Setup strategy constraints
    constraints = [
        StrategyEligibilityConstraints(
            strategy_id="trend-following",
            target_regimes=["Markup", "Expansion"],
            min_market_health=0.2,
            max_market_risk=0.8,
        )
    ]

    strategy_stats = {
        "trend-following": {"win_rate": 0.60, "sharpe": 2.2},
    }

    # 3. Perform scan (no filters)
    opportunities = scanner.scan(
        market_data=market_data,
        strategy_constraints=constraints,
        strategy_stats=strategy_stats,
    )

    # BTC is in Markup regime, so it should match "trend-following" strategy target.
    # ETH is in consolidation/Recovery regime, so it should be skipped.
    assert len(opportunities) == 1
    assert opportunities[0].symbol == "BTC/USDT"
    assert opportunities[0].strategy_id == "trend-following"
    assert opportunities[0].regime == "Markup"
    assert opportunities[0].risk_grade in [RiskGrade.A, RiskGrade.B]
    assert opportunities[0].score > 0.0


def test_scan_filters(scanner_and_universe: tuple[Scanner, UniverseManager]) -> None:
    """Test that scanning supports universe-level metadata filters."""
    scanner, um = scanner_and_universe

    market_data = {
        "BTC/USDT": {
            "prices": [100.0, 102.0, 104.0, 106.0, 108.0, 111.0],
            "volumes": [1000.0, 1200.0, 1100.0, 1300.0, 1400.0, 1800.0],
        },
        "ETH/USDT": {
            "prices": [100.0, 102.0, 104.0, 106.0, 108.0, 111.0],
            "volumes": [1000.0, 1200.0, 1100.0, 1300.0, 1400.0, 1800.0],
        },
    }

    constraints = [
        StrategyEligibilityConstraints(
            strategy_id="trend-following",
            target_regimes=["Markup"],
        )
    ]
    strategy_stats = {"trend-following": {"win_rate": 0.60, "sharpe": 2.0}}

    # Filter for Binance exchange
    binance_opps = scanner.scan(
        market_data=market_data,
        strategy_constraints=constraints,
        strategy_stats=strategy_stats,
        filters={"exchange": "Binance"},
    )
    # Only BTC is on Binance
    assert len(binance_opps) == 1
    assert binance_opps[0].symbol == "BTC/USDT"
