import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any

from data.schemas.market_data import OHLCV
from market_gateway.providers.binance.client import BinanceGatewayProvider
from market_gateway.validation.validator import MarketDataValidator
from toji_platform.market_universe.models import MarketStats
from toji_platform.market_universe.engine import MarketUniverseEngine
from toji_platform.market_scanner.scanner import MarketScanner
from toji_platform.market_scanner import state

@pytest.fixture
def pipeline_config():
    return {
        "filters": {
            "quote_asset": "USDT",
            "status": "TRADING",
            "min_price": 0.01,
            "min_volume_24h": 1000.0,
            "min_liquidity_usd": 1000.0,
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
        "ranking": {},
        "stale_threshold_sec": 30.0,
        "volatility_threshold": 0.03,
        "min_liquidity_usd": 10000.0,
        "unusual_volume_threshold": 2.0,
        "max_spread": 0.01,
        "atr_period": 3,
        "rsi_period": 3
    }

def make_mock_candles(count=5, price=100.0, volume=1000.0):
    candles = []
    now = datetime.now(timezone.utc)
    for i in range(count):
        candles.append(OHLCV(
            symbol="BTCUSDT",
            timestamp=now - timedelta(minutes=count - i),
            open=price,
            high=price + 1.0,
            low=price - 1.0,
            close=price,
            volume=volume,
            interval="1m"
        ))
    return candles

def test_integration_normal_healthy_flow(pipeline_config):
    # 1. Initialize subsystems
    validator = MarketDataValidator()
    universe_engine = MarketUniverseEngine(pipeline_config)
    scanner = MarketScanner(pipeline_config)
    
    # 2. Mock Gateway inputs
    raw_tickers = [
        MarketStats("BTCUSDT", "USDT", "TRADING", 95000.0, 100000.0, 0.001, 50000.0, 0.02, 0.02),
        MarketStats("ETHUSDT", "USDT", "TRADING", 3400.0, 50000.0, 0.001, 30000.0, 0.01, 0.01),
    ]
    
    # 3. Validation stage (Gateway validated ticks)
    # The gateway emits stats after parsing raw tickers
    for t in raw_tickers:
        tick = OHLCV(symbol=t.symbol, timestamp=datetime.now(timezone.utc), open=t.price, high=t.price, low=t.price, close=t.price, volume=t.volume_24h, interval="1m")
        assert len(validator.validate_event(tick)) == 0
        
    # 4. Universe Engine Filtering & Scoring
    ranked = universe_engine.evaluate_universe(raw_tickers)
    assert len(ranked) == 2
    assert ranked[0].symbol == "BTCUSDT"
    
    # 5. Scanner Observation
    candles = make_mock_candles()
    scan = scanner.scan_market(ranked[0], candles, datetime.now(timezone.utc))
    
    assert scan.symbol == "BTCUSDT"
    assert state.HEALTHY in scan.market_states
    assert scan.confidence_score == 1.0
    assert scan.quality_score == 1.0

def test_integration_empty_market_list(pipeline_config):
    universe_engine = MarketUniverseEngine(pipeline_config)
    ranked = universe_engine.evaluate_universe([])
    assert ranked == []

def test_integration_invalid_market_payload():
    from pydantic import ValidationError
    # Pydantic validation rejects invalid parameters on creation
    with pytest.raises(ValidationError):
        OHLCV(symbol="BTCUSDT", timestamp=datetime.now(timezone.utc), open=-10.0, high=10.0, low=10.0, close=10.0, volume=10.0, interval="1m")

def test_integration_duplicate_market_messages():
    validator = MarketDataValidator()
    # Identical sequence timestamp
    ts = datetime.now(timezone.utc)
    t1 = OHLCV(symbol="BTCUSDT", timestamp=ts, open=100.0, high=100.0, low=100.0, close=100.0, volume=10.0, interval="1m")
    t2 = OHLCV(symbol="BTCUSDT", timestamp=ts, open=100.0, high=100.0, low=100.0, close=100.0, volume=10.0, interval="1m")
    
    # Verify duplicate detection fails
    assert len(validator.validate_event(t1)) == 0
    errors = validator.validate_event(t2)
    assert len(errors) > 0
    assert any("Duplicate event" in err for err in errors)

def test_integration_out_of_order_messages():
    validator = MarketDataValidator()
    ts1 = datetime.now(timezone.utc)
    ts2 = ts1 - timedelta(seconds=10)
    
    t1 = OHLCV(symbol="BTCUSDT", timestamp=ts1, open=100.0, high=100.0, low=100.0, close=100.0, volume=10.0, interval="1m")
    t2 = OHLCV(symbol="BTCUSDT", timestamp=ts2, open=100.0, high=100.0, low=100.0, close=100.0, volume=10.0, interval="1m")
    
    assert len(validator.validate_event(t1)) == 0
    errors = validator.validate_event(t2)
    assert len(errors) > 0
    assert any("Sequence ordering violation" in err for err in errors)

def test_integration_stale_market_data(pipeline_config):
    universe_engine = MarketUniverseEngine(pipeline_config)
    scanner = MarketScanner(pipeline_config)
    
    raw = [MarketStats("BTCUSDT", "USDT", "TRADING", 100.0, 50000.0, 0.001, 20000.0, 0.01, 0.01)]
    ranked = universe_engine.evaluate_universe(raw)
    
    candles = make_mock_candles()
    stale_time = datetime.now(timezone.utc) - timedelta(seconds=60)
    scan = scanner.scan_market(ranked[0], candles, stale_time)
    
    assert state.DATA_STALE in scan.market_states
    assert state.UNHEALTHY in scan.market_states

def test_integration_high_volatility_market(pipeline_config):
    universe_engine = MarketUniverseEngine(pipeline_config)
    scanner = MarketScanner(pipeline_config)
    
    raw = [MarketStats("BTCUSDT", "USDT", "TRADING", 100.0, 50000.0, 0.001, 20000.0, 0.01, 0.05)]  # Volatility 0.05 > 0.03
    ranked = universe_engine.evaluate_universe(raw)
    
    candles = make_mock_candles()
    scan = scanner.scan_market(ranked[0], candles, datetime.now(timezone.utc))
    
    assert state.HIGH_VOLATILITY in scan.market_states

def test_integration_low_liquidity_market(pipeline_config):
    universe_engine = MarketUniverseEngine(pipeline_config)
    scanner = MarketScanner(pipeline_config)
    
    raw = [MarketStats("BTCUSDT", "USDT", "TRADING", 100.0, 50000.0, 0.001, 1000.0, 0.01, 0.01)]  # Liquidity 1000 < 10000
    ranked = universe_engine.evaluate_universe(raw)
    
    candles = make_mock_candles()
    scan = scanner.scan_market(ranked[0], candles, datetime.now(timezone.utc))
    
    assert state.LOW_LIQUIDITY in scan.market_states
    assert state.UNHEALTHY in scan.market_states

def test_integration_multiple_market_states(pipeline_config):
    universe_engine = MarketUniverseEngine(pipeline_config)
    scanner = MarketScanner(pipeline_config)
    
    raw = [MarketStats("BTCUSDT", "USDT", "TRADING", 100.0, 50000.0, 0.001, 1000.0, 0.01, 0.05)]
    ranked = universe_engine.evaluate_universe(raw)
    
    candles = [
        OHLCV(symbol="BTCUSDT", timestamp=datetime.now(timezone.utc) - timedelta(minutes=3), open=10.0, high=11.0, low=9.0, close=10.0, volume=10.0, interval="1m"),
        OHLCV(symbol="BTCUSDT", timestamp=datetime.now(timezone.utc) - timedelta(minutes=2), open=15.0, high=16.0, low=14.0, close=15.0, volume=10.0, interval="1m"),
        OHLCV(symbol="BTCUSDT", timestamp=datetime.now(timezone.utc) - timedelta(minutes=1), open=20.0, high=21.0, low=19.0, close=20.0, volume=10.0, interval="1m"),
        OHLCV(symbol="BTCUSDT", timestamp=datetime.now(timezone.utc), open=30.0, high=31.0, low=29.0, close=30.0, volume=50.0, interval="1m")
    ]
    
    scan = scanner.scan_market(ranked[0], candles, datetime.now(timezone.utc))
    
    assert state.TRENDING_UP in scan.market_states
    assert state.HIGH_VOLATILITY in scan.market_states
    assert state.LOW_LIQUIDITY in scan.market_states
    assert state.UNUSUAL_VOLUME in scan.market_states
    assert state.UNHEALTHY in scan.market_states

def test_integration_large_market_universe(pipeline_config):
    universe_engine = MarketUniverseEngine(pipeline_config)
    
    # 500+ symbols
    markets = []
    for i in range(550):
        markets.append(MarketStats(
            symbol=f"SYM_{i}",
            quote_asset="USDT",
            status="TRADING",
            price=10.0,
            volume_24h=50000.0,
            spread=0.001,
            liquidity_usd=20000.0,
            momentum_24h=0.01,
            volatility_24h=0.02
        ))
        
    ranked = universe_engine.evaluate_universe(markets)
    assert len(ranked) == 550
    assert ranked[0].symbol == "SYM_0"
    assert ranked[0].rank == 1

def test_integration_gateway_reconnect_simulation():
    async def _run():
        provider = BinanceGatewayProvider(use_mock=True)
        provider.initialize()
        
        # Verify status is connected
        assert provider.health()["status"] == "connected"
        
        # Simulate connection drop
        provider.disconnect()
        assert provider.health()["status"] == "disconnected"
        
        # Simulate recovery reconnection
        provider.connect()
        assert provider.health()["status"] == "connected"
        
        provider.shutdown()
        await asyncio.sleep(0.01)
        
    asyncio.run(_run())

def test_integration_scanner_deterministic_output(pipeline_config):
    universe_engine = MarketUniverseEngine(pipeline_config)
    scanner = MarketScanner(pipeline_config)
    
    raw = [MarketStats("BTCUSDT", "USDT", "TRADING", 100.0, 50000.0, 0.001, 20000.0, 0.01, 0.01)]
    ranked = universe_engine.evaluate_universe(raw)
    candles = make_mock_candles()
    
    scan1 = scanner.scan_market(ranked[0], candles, datetime.now(timezone.utc))
    scan2 = scanner.scan_market(ranked[0], candles, datetime.now(timezone.utc))
    
    assert scan1.market_states == scan2.market_states
    assert scan1.metrics.atr == scan2.metrics.atr
    assert scan1.metrics.rsi == scan2.metrics.rsi
    assert scan1.confidence_score == scan2.confidence_score
    assert scan1.quality_score == scan2.quality_score
