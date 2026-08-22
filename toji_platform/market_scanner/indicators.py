"""Technical indicators and mathematical helpers."""

from __future__ import annotations
from data.schemas.market_data import OHLCV

def calculate_sma(prices: list[float], period: int) -> float:
    """Calculates simple moving average."""
    if not prices or len(prices) < period:
        return 0.0
    return sum(prices[-period:]) / period

def calculate_atr(candles: list[OHLCV], period: int = 14) -> float:
    """Calculates Average True Range."""
    if len(candles) < period + 1:
        return 0.0
    
    true_ranges = []
    for i in range(1, len(candles)):
        high = candles[i].high
        low = candles[i].low
        prev_close = candles[i-1].close
        
        tr = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close)
        )
        true_ranges.append(tr)
        
    return sum(true_ranges[-period:]) / period

def calculate_rsi(prices: list[float], period: int = 14) -> float:
    """Calculates Relative Strength Index."""
    if len(prices) < period + 1:
        return 50.0
        
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    
    gains = [d if d > 0 else 0.0 for d in deltas[-period:]]
    losses = [-d if d < 0 else 0.0 for d in deltas[-period:]]
    
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    
    if avg_loss == 0.0:
        return 100.0
        
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))
