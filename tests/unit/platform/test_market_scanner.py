import pytest
from datetime import datetime, timedelta, timezone
from data.schemas.market_data import OHLCV
from toji_platform.market_universe.models import MarketStats, RankedMarket
from toji_platform.market_scanner.scanner import MarketScanner
from toji_platform.market_scanner import state

@pytest.fixture
def scanner_config():
    return {
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

def test_healthy_market(scanner_config):
    scanner = MarketScanner(scanner_config)
    
    stats = MarketStats("BTCUSDT", "USDT", "TRADING", 100.0, 50000.0, 0.001, 20000.0, 0.01, 0.01)
    rm = RankedMarket("BTCUSDT", 1, 0.8, "A", stats)
    
    candles = make_mock_candles()
    scan = scanner.scan_market(rm, candles, datetime.now(timezone.utc))
    
    assert state.HEALTHY in scan.market_states
    assert state.DATA_STALE not in scan.market_states
    assert scan.confidence_score == 1.0
    assert scan.quality_score == 1.0

def test_stale_data(scanner_config):
    scanner = MarketScanner(scanner_config)
    
    stats = MarketStats("BTCUSDT", "USDT", "TRADING", 100.0, 50000.0, 0.001, 20000.0, 0.01, 0.01)
    rm = RankedMarket("BTCUSDT", 1, 0.8, "A", stats)
    
    candles = make_mock_candles()
    stale_time = datetime.now(timezone.utc) - timedelta(seconds=60)
    scan = scanner.scan_market(rm, candles, stale_time)
    
    assert state.DATA_STALE in scan.market_states
    assert state.UNHEALTHY in scan.market_states
    assert scan.confidence_score == 0.5
    assert scan.quality_score == 0.7

def test_unusual_volume(scanner_config):
    scanner = MarketScanner(scanner_config)
    
    stats = MarketStats("BTCUSDT", "USDT", "TRADING", 100.0, 50000.0, 0.001, 20000.0, 0.01, 0.01)
    rm = RankedMarket("BTCUSDT", 1, 0.8, "A", stats)
    
    candles = make_mock_candles(count=4, volume=100.0)
    candles.append(OHLCV(
        symbol="BTCUSDT",
        timestamp=datetime.now(timezone.utc),
        open=100.0, high=101.0, low=99.0, close=100.0,
        volume=500.0,
        interval="1m"
    ))
    
    scan = scanner.scan_market(rm, candles, datetime.now(timezone.utc))
    assert state.UNUSUAL_VOLUME in scan.market_states

def test_high_volatility(scanner_config):
    scanner = MarketScanner(scanner_config)
    
    stats = MarketStats("BTCUSDT", "USDT", "TRADING", 100.0, 50000.0, 0.001, 20000.0, 0.01, 0.05)
    rm = RankedMarket("BTCUSDT", 1, 0.8, "A", stats)
    
    candles = make_mock_candles()
    scan = scanner.scan_market(rm, candles, datetime.now(timezone.utc))
    assert state.HIGH_VOLATILITY in scan.market_states

def test_low_liquidity(scanner_config):
    scanner = MarketScanner(scanner_config)
    
    stats = MarketStats("BTCUSDT", "USDT", "TRADING", 100.0, 50000.0, 0.001, 1000.0, 0.01, 0.01)
    rm = RankedMarket("BTCUSDT", 1, 0.8, "A", stats)
    
    candles = make_mock_candles()
    scan = scanner.scan_market(rm, candles, datetime.now(timezone.utc))
    assert state.LOW_LIQUIDITY in scan.market_states
    assert state.UNHEALTHY in scan.market_states

def test_invalid_data_and_zero_safety(scanner_config):
    scanner = MarketScanner(scanner_config)
    
    stats = MarketStats("BTCUSDT", "USDT", "TRADING", 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    rm = RankedMarket("BTCUSDT", 1, 0.0, "D", stats)
    
    candles = [OHLCV(symbol="BTCUSDT", timestamp=datetime.now(timezone.utc), open=100.0, high=100.0, low=100.0, close=100.0, volume=0.0, interval="1m")]
    scan = scanner.scan_market(rm, candles, datetime.now(timezone.utc))
    
    assert scan.symbol == "BTCUSDT"
    assert scan.metrics.relative_volume == 1.0
    assert scan.metrics.atr == 0.0

def test_deterministic_output(scanner_config):
    scanner = MarketScanner(scanner_config)
    
    stats = MarketStats("BTCUSDT", "USDT", "TRADING", 100.0, 50000.0, 0.001, 20000.0, 0.01, 0.01)
    rm = RankedMarket("BTCUSDT", 1, 0.8, "A", stats)
    
    candles = make_mock_candles()
    
    scan1 = scanner.scan_market(rm, candles, datetime.now(timezone.utc))
    scan2 = scanner.scan_market(rm, candles, datetime.now(timezone.utc))
    
    assert scan1.market_states == scan2.market_states
    assert scan1.confidence_score == scan2.confidence_score
    assert scan1.quality_score == scan2.quality_score

def test_multiple_simultaneous_states(scanner_config):
    scanner = MarketScanner(scanner_config)
    
    stats = MarketStats("BTCUSDT", "USDT", "TRADING", 100.0, 50000.0, 0.001, 1000.0, 0.01, 0.05)
    rm = RankedMarket("BTCUSDT", 1, 0.8, "A", stats)
    
    candles = [
        OHLCV(symbol="BTCUSDT", timestamp=datetime.now(timezone.utc) - timedelta(minutes=3), open=10.0, high=11.0, low=9.0, close=10.0, volume=10.0, interval="1m"),
        OHLCV(symbol="BTCUSDT", timestamp=datetime.now(timezone.utc) - timedelta(minutes=2), open=15.0, high=16.0, low=14.0, close=15.0, volume=10.0, interval="1m"),
        OHLCV(symbol="BTCUSDT", timestamp=datetime.now(timezone.utc) - timedelta(minutes=1), open=20.0, high=21.0, low=19.0, close=20.0, volume=10.0, interval="1m"),
        OHLCV(symbol="BTCUSDT", timestamp=datetime.now(timezone.utc), open=30.0, high=31.0, low=29.0, close=30.0, volume=50.0, interval="1m")
    ]
    
    scan = scanner.scan_market(rm, candles, datetime.now(timezone.utc))
    
    assert state.TRENDING_UP in scan.market_states
    assert state.HIGH_VOLATILITY in scan.market_states
    assert state.LOW_LIQUIDITY in scan.market_states
    assert state.UNUSUAL_VOLUME in scan.market_states
    assert state.UNHEALTHY in scan.market_states
