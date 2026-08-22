from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from portfolio_engine.core.enums import PositionSide, PositionState


class PositionUpdate(BaseModel):
    """Immutable model representing a modification update to a position."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    price: float = Field(..., description="Transaction execution price.")
    quantity: float = Field(..., description="Size changed.")
    pnl: float = Field(default=0.0, description="Realized PnL for this update.")
    action: str = Field(..., description="Action category (e.g. ENTRY, ADD, REDUCE, CLOSE).")

    model_config = ConfigDict(frozen=True)


class Position(BaseModel):
    """Immutable model representing an active (open) or historical (closed) position."""

    position_id: str = Field(..., description="Unique position identifier.")
    symbol: str = Field(..., description="Ticker symbol.")
    side: PositionSide = Field(..., description="Position direction long/short.")
    quantity: float = Field(..., description="Remaining open quantity.")
    average_entry: float = Field(..., description="Average cost price on entry.")
    average_exit: float = Field(default=0.0, description="Average close execution price.")
    current_price: float = Field(..., description="Last known market price observation.")
    market_value: float = Field(..., description="Current position value.")
    cost_basis: float = Field(..., description="Accumulated position cost basis.")
    unrealized_pnl: float = Field(default=0.0, description="Floating paper profit or loss.")
    realized_pnl: float = Field(default=0.0, description="Finalized realized profit/loss.")
    fees: float = Field(default=0.0, description="Accumulated transaction fee details.")
    funding: float = Field(default=0.0, description="Funding fee details.")
    leverage: float = Field(default=1.0, description="Applied leverage multiple.")
    margin_used: float = Field(default=0.0, description="Capital margin reserved by broker.")
    exposure: float = Field(..., description="Gross exposure value.")
    open_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    close_time: Optional[datetime] = Field(default=None)
    state: PositionState = Field(default=PositionState.OPEN)
    updates: List[PositionUpdate] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class ClosedPosition(BaseModel):
    """Immutable snapshot of a completely closed position."""

    position_id: str = Field(..., description="Unique position identifier.")
    symbol: str = Field(..., description="Ticker symbol.")
    side: PositionSide = Field(..., description="LONG or SHORT.")
    quantity: float = Field(default=0.0)
    average_entry: float = Field(...)
    average_exit: float = Field(...)
    realized_pnl: float = Field(...)
    fees: float = Field(default=0.0)
    funding: float = Field(default=0.0)
    open_time: datetime = Field(...)
    close_time: datetime = Field(...)
    updates: List[PositionUpdate] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class PortfolioMetrics(BaseModel):
    """Immutable aggregations representing live portfolio performance markers."""

    total_realized_pnl: float = Field(default=0.0, description="Sum of all closed realized PnL.")
    total_unrealized_pnl: float = Field(default=0.0, description="Sum of floating unrealized PnL.")
    gross_exposure: float = Field(default=0.0, description="Sum of absolute market values.")
    net_exposure: float = Field(default=0.0, description="Sum of signed market values.")
    portfolio_value: float = Field(default=0.0, description="Net liquidating value of positions.")
    margin_used: float = Field(default=0.0, description="Total capital margin locked in active trades.")
    leverage_ratio: float = Field(default=0.0, description="Gross exposure divided by portfolio value.")

    model_config = ConfigDict(frozen=True)


class PortfolioHealth(BaseModel):
    """Operational stability scores detailing system drawdown risk parameters."""

    status: str = Field(default="HEALTHY", description="Status code (HEALTHY, WARNING, CRITICAL).")
    drawdown: float = Field(default=0.0, description="Drawdown relative to peak portfolio value.")
    leverage_ratio: float = Field(default=0.0, description="Aggregated leverage ratio.")
    risk_exposure_ratio: float = Field(default=0.0, description="Net exposure relative to capital bounds.")

    model_config = ConfigDict(frozen=True)


class PortfolioSnapshot(BaseModel):
    """Unified snapshot summarizing the entire state of the Portfolio Engine."""

    snapshot_id: str = Field(..., description="Unique snapshot UUID.")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    positions: Dict[str, Position] = Field(default_factory=dict, description="Active open positions.")
    closed_positions: List[ClosedPosition] = Field(default_factory=list, description="List of historical positions.")
    metrics: PortfolioMetrics = Field(default_factory=PortfolioMetrics)
    health: PortfolioHealth = Field(default_factory=PortfolioHealth)

    model_config = ConfigDict(frozen=True)


class PortfolioStatistics(BaseModel):
    """Historical trading efficiency ratios."""

    winning_pct: float = Field(default=0.0, description="Winning trades count ratio.")
    losing_pct: float = Field(default=0.0, description="Losing trades count ratio.")
    average_win: float = Field(default=0.0, description="Average profit on winning trades.")
    average_loss: float = Field(default=0.0, description="Average loss on losing trades.")
    profit_factor: float = Field(default=0.0, description="Total win PnL divided by total loss PnL.")
    total_trades: int = Field(default=0, description="Completed closed trades count.")

    model_config = ConfigDict(frozen=True)
