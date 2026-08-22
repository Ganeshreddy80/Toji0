"""Enums for the Research Platform (Sprint 6)."""

from __future__ import annotations

import enum


class ExperimentStatus(enum.Enum):
    """Lifecycle status of a research experiment."""

    CREATED = "CREATED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class StrategyType(enum.Enum):
    """Classification of quantitative strategies evaluated by the research platform."""

    QUANTITATIVE = "QUANTITATIVE"
    PRICE_ACTION = "PRICE_ACTION"
    STATISTICAL_ARBITRAGE = "STATISTICAL_ARBITRAGE"
    MOMENTUM = "MOMENTUM"
    MEAN_REVERSION = "MEAN_REVERSION"
    MACHINE_LEARNING = "MACHINE_LEARNING"
    CUSTOM = "CUSTOM"


class DatasetType(enum.Enum):
    """Type classification for immutable market research datasets."""

    OHLCV = "OHLCV"
    TICK = "TICK"
    FEATURES = "FEATURES"
    ORDER_BOOK = "ORDER_BOOK"
    SYNTHETIC = "SYNTHETIC"
    ALTERNATIVE = "ALTERNATIVE"


class SweepMethod(enum.Enum):
    """Parameter sweep search algorithms."""

    GRID = "GRID"
    RANDOM = "RANDOM"
    BAYESIAN = "BAYESIAN"


class WalkForwardType(enum.Enum):
    """Walk-forward evaluation window strategies."""

    ROLLING = "ROLLING"
    EXPANDING = "EXPANDING"


class ReportFormat(enum.Enum):
    """Supported export formats for research reports."""

    JSON = "JSON"
    MARKDOWN = "MARKDOWN"
    PDF = "PDF"


class MetricType(enum.Enum):
    """Deterministic quantitative performance and risk metric classifications."""

    SHARPE = "SHARPE"
    SORTINO = "SORTINO"
    MAX_DRAWDOWN = "MAX_DRAWDOWN"
    CALMAR = "CALMAR"
    WIN_RATE = "WIN_RATE"
    PROFIT_FACTOR = "PROFIT_FACTOR"
    CAGR = "CAGR"
    VOLATILITY = "VOLATILITY"
    EXPECTED_RETURN = "EXPECTED_RETURN"
    VAR_95 = "VAR_95"
    TAIL_RISK = "TAIL_RISK"
