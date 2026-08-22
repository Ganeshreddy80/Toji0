"""Abstract contracts for the Market Regime Intelligence Engine.
"""

from __future__ import annotations

import abc
from typing import Any, Dict, List, Optional
from research_platform.market_regime.models import (
    HistoricalRegimeRecord,
    MarketRegime,
    MarketStructure,
    RegimeTransition,
)


class IMarketRegimeRepository(abc.ABC):
    """Abstract contract for persisting and retrieving regime analysis and transition history."""

    @abc.abstractmethod
    def save_regime(self, record: HistoricalRegimeRecord) -> None:
        """Persist a regime timeline record."""

    @abc.abstractmethod
    def get_latest_regime(self, symbol: str) -> Optional[MarketRegime]:
        """Retrieve the most recently detected market regime for a symbol."""

    @abc.abstractmethod
    def list_regime_history(self, symbol: str) -> List[HistoricalRegimeRecord]:
        """List historical regime records for a symbol."""

    @abc.abstractmethod
    def save_transition(self, transition: RegimeTransition) -> None:
        """Persist a regime transition log."""

    @abc.abstractmethod
    def list_transitions(self, symbol: str) -> List[RegimeTransition]:
        """List historical regime transitions for a symbol."""

    @abc.abstractmethod
    def save_market_structure(self, structure: MarketStructure) -> None:
        """Persist a market structure analysis."""

    @abc.abstractmethod
    def get_latest_market_structure(self, symbol: str) -> Optional[MarketStructure]:
        """Retrieve the latest market structure analysis for a symbol."""


class IVolatilityDetector(abc.ABC):
    """Abstract contract for volatility regime detection."""

    @abc.abstractmethod
    def detect_volatility(self, prices: List[float], atr_values: List[float]) -> Any:
        """Analyze prices/ATR list to determine volatility regime."""


class ILiquidityDetector(abc.ABC):
    """Abstract contract for liquidity regime detection."""

    @abc.abstractmethod
    def detect_liquidity(self, volumes: List[float], spreads: List[float]) -> Any:
        """Analyze volumes/spreads to determine liquidity regime."""


class ITrendDetector(abc.ABC):
    """Abstract contract for trend regime detection."""

    @abc.abstractmethod
    def detect_trend(self, prices: List[float]) -> Any:
        """Analyze price history list to determine trend regime."""


class IMarketStructureAnalyzer(abc.ABC):
    """Abstract contract for market structure level analysis."""

    @abc.abstractmethod
    def analyze_structure(self, prices: List[float], highs: List[float], lows: List[float]) -> MarketStructure:
        """Detect support, resistance levels, breakouts and order blocks."""


class IMarketRegimeOrchestrator(abc.ABC):
    """Abstract contract for the Market Regime Intelligence orchestrator."""
    pass
