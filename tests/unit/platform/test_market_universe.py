import pytest
from toji_platform.market_universe.models import MarketStats
from toji_platform.market_universe.engine import MarketUniverseEngine

@pytest.fixture
def base_config():
    return {
        "filters": {
            "quote_asset": "USDT",
            "status": "TRADING",
            "min_price": 0.01,
            "min_volume_24h": 10000.0,
            "min_liquidity_usd": 5000.0,
            "max_spread": 0.02,
            "whitelist": ["SPECIAL"],
            "blacklist": ["BAD"]
        },
        "scoring": {
            "weights": {
                "liquidity": 0.3,
                "volume": 0.3,
                "volatility": 0.1,
                "spread": 0.1,
                "momentum": 0.2
            }
        },
        "ranking": {}
    }

def test_filtering(base_config):
    engine = MarketUniverseEngine(base_config)
    
    # Valid candidate
    m1 = MarketStats("BTCUSDT", "USDT", "TRADING", 95000.0, 100000.0, 0.001, 50000.0, 0.02, 0.05)
    # Invalid quote
    m2 = MarketStats("BTCFDUSD", "FDUSD", "TRADING", 95000.0, 100000.0, 0.001, 50000.0, 0.02, 0.05)
    # Invalid status
    m3 = MarketStats("ETHUSDT", "USDT", "BREAK", 3400.0, 50000.0, 0.001, 30000.0, -0.01, 0.04)
    # Low volume
    m4 = MarketStats("LOWVOL", "USDT", "TRADING", 1.0, 100.0, 0.001, 10000.0, 0.0, 0.01)
    
    res = engine.evaluate_universe([m1, m2, m3, m4])
    assert len(res) == 1
    assert res[0].symbol == "BTCUSDT"

def test_blacklist_whitelist(base_config):
    engine = MarketUniverseEngine(base_config)
    
    # Whitelisted bypasses status filter
    m1 = MarketStats("SPECIAL", "USDT", "BREAK", 0.001, 1.0, 0.5, 1.0, 0.0, 0.0)
    # Blacklisted is filtered out even if otherwise valid
    m2 = MarketStats("BAD", "USDT", "TRADING", 95000.0, 100000.0, 0.001, 50000.0, 0.02, 0.05)
    
    res = engine.evaluate_universe([m1, m2])
    assert len(res) == 1
    assert res[0].symbol == "SPECIAL"

def test_scoring_and_ranking(base_config):
    engine = MarketUniverseEngine(base_config)
    
    # Generate 5 markets
    markets = [
        MarketStats("M1", "USDT", "TRADING", 10.0, 100000.0, 0.001, 50000.0, 0.05, 0.05),
        MarketStats("M2", "USDT", "TRADING", 10.0, 80000.0, 0.002, 40000.0, 0.04, 0.04),
        MarketStats("M3", "USDT", "TRADING", 10.0, 60000.0, 0.003, 30000.0, 0.03, 0.03),
        MarketStats("M4", "USDT", "TRADING", 10.0, 40000.0, 0.004, 20000.0, 0.02, 0.02),
        MarketStats("M5", "USDT", "TRADING", 10.0, 20000.0, 0.005, 10000.0, 0.01, 0.01),
    ]
    
    ranked = engine.evaluate_universe(markets)
    assert len(ranked) == 5
    
    # Deterministic ranking check
    assert ranked[0].symbol == "M1"
    assert ranked[0].rank == 1
    assert ranked[0].tier == "B"  # 1/5 = 20% -> Tier B (A is top 15%)
    assert ranked[4].symbol == "M5"
    assert ranked[4].rank == 5
    assert ranked[4].tier == "D"  # 5/5 = 100% -> Tier D

def test_deterministic_output(base_config):
    engine = MarketUniverseEngine(base_config)
    
    # Equal score candidates
    m1 = MarketStats("B_TIE", "USDT", "TRADING", 10.0, 50000.0, 0.001, 20000.0, 0.02, 0.02)
    m2 = MarketStats("A_TIE", "USDT", "TRADING", 10.0, 50000.0, 0.001, 20000.0, 0.02, 0.02)
    
    ranked = engine.evaluate_universe([m1, m2])
    assert len(ranked) == 2
    assert ranked[0].symbol == "A_TIE"  # Alphabetical secondary key
    assert ranked[1].symbol == "B_TIE"

def test_empty_market_list(base_config):
    engine = MarketUniverseEngine(base_config)
    ranked = engine.evaluate_universe([])
    assert ranked == []

def test_invalid_market_data(base_config):
    engine = MarketUniverseEngine(base_config)
    
    # Volatility / Liquidity 0.0 to check division by zero safety
    # Named "SPECIAL" to bypass filters via whitelist
    m1 = MarketStats("SPECIAL", "USDT", "TRADING", 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    
    ranked = engine.evaluate_universe([m1])
    assert len(ranked) == 1
    assert abs(ranked[0].score - 0.1) < 1e-6  # Only spread yields score (1.0 - 0.0) * 0.1 = 0.1
