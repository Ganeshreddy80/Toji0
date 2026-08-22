"""Immutable Pydantic models for Trade Journal & Performance Analytics.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class TradeScore(BaseModel):
    """Execution and parameters score metrics card."""

    execution_score: float  # 0 to 100
    risk_score: float
    total_score: float

    model_config = ConfigDict(frozen=True)


class TradeMistake(BaseModel):
    """A mistake logged post-trade."""

    mistake_id: str
    category: str  # FOMO, SLIPPAGE, RISK_BREACH, LATE_EXIT
    description: str

    model_config = ConfigDict(frozen=True)


class TradeLesson(BaseModel):
    """A lesson learned/retained post-trade."""

    lesson_id: str
    description: str
    action_item: str

    model_config = ConfigDict(frozen=True)


class TradeReview(BaseModel):
    """An AI post-trade review summary."""

    review_id: str
    summary: str
    positive_decisions: List[str] = Field(default_factory=list)
    mistakes: List[TradeMistake] = Field(default_factory=list)
    lessons: List[TradeLesson] = Field(default_factory=list)
    confidence: float
    suggestions: List[str] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class TradeStatistics(BaseModel):
    """Performance statistics aggregation summary."""

    win_rate: float
    loss_rate: float
    average_win: float
    average_loss: float
    profit_factor: float
    expectancy: float
    sharpe_ratio: float
    sortino_ratio: float
    average_holding_time_sec: float
    largest_win: float
    largest_loss: float
    win_streak: int
    loss_streak: int
    recovery_factor: float

    model_config = ConfigDict(frozen=True)


class TradeJournal(BaseModel):
    """A complete Trade Journal entry summarizing a closed trade details."""

    journal_id: str
    order_id: str
    strategy_id: str
    symbol: str
    quantity: float
    side: str
    entry_price: float
    exit_price: float
    entry_time: datetime
    exit_time: datetime
    pnl: float
    commission: float
    slippage: float
    holding_time_sec: float
    mfe: float  # Maximum Favorable Excursion
    mae: float  # Maximum Adverse Excursion
    market_regime: str
    score: TradeScore
    review: Optional[TradeReview] = None
    tags: List[str] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class TradeSnapshot(BaseModel):
    """Snapshot card summarizing portfolio returns today."""

    total_pnl: float
    total_trades_count: int
    best_strategy: str
    worst_strategy: str
    largest_winner: float
    largest_loser: float

    model_config = ConfigDict(frozen=True)


class TradeTimeline(BaseModel):
    """Timeline entry coordinates of a trade."""

    timestamp: datetime
    journal_id: str
    pnl: float

    model_config = ConfigDict(frozen=True)


class DailyJournal(BaseModel):
    """Compiled daily journal snapshot."""

    date: str  # YYYY-MM-DD
    snapshot: TradeSnapshot
    journals: List[TradeJournal] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class WeeklyJournal(BaseModel):
    """Compiled weekly journal snapshot."""

    week_start: str  # YYYY-MM-DD
    snapshot: TradeSnapshot
    journals: List[TradeJournal] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class MonthlyJournal(BaseModel):
    """Compiled monthly journal snapshot."""

    month: str  # YYYY-MM
    snapshot: TradeSnapshot
    journals: List[TradeJournal] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)
