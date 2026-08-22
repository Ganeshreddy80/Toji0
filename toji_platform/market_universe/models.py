"""Market Universe Engine models."""

from __future__ import annotations
from dataclasses import dataclass

@dataclass
class MarketStats:
    symbol: str
    quote_asset: str
    status: str  # e.g., "TRADING"
    price: float
    volume_24h: float
    spread: float
    liquidity_usd: float  # Bid/Ask order book depth inside 1% boundary
    momentum_24h: float  # 24h percentage return
    volatility_24h: float  # 24h normalized standard deviation or High/Low delta percentage

@dataclass
class ScoredMarket:
    symbol: str
    score: float
    factors: dict[str, float]
    stats: MarketStats

@dataclass
class RankedMarket:
    symbol: str
    rank: int
    score: float
    tier: str  # "A", "B", "C", "D"
    stats: MarketStats
