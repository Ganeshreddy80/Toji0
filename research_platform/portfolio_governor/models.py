"""Pydantic models for the Portfolio Governor subsystem."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


DecisionReason = Literal[
    "APPROVED",
    "DUPLICATE_POSITION",
    "EXPOSURE_LIMIT",
    "MAX_POSITIONS",
    "COOLDOWN_ACTIVE",
]


class GovernedPosition(BaseModel):
    """Tracks a single symbol's live position state."""

    symbol: str
    side: Literal["LONG", "SHORT"]       # LONG = net-positive qty, SHORT = net-negative
    quantity: float                       # always positive
    average_entry_price: float
    current_price: float
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    opened_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=False)  # mutable: updated on price ticks

    def update_price(self, price: float) -> None:
        """Recompute unrealized PnL on price update."""
        self.current_price = price
        if self.side == "LONG":
            self.unrealized_pnl = (price - self.average_entry_price) * self.quantity
        else:
            self.unrealized_pnl = (self.average_entry_price - price) * self.quantity
        self.updated_at = datetime.now(timezone.utc)


class PortfolioDecision(BaseModel):
    """Result produced by PortfolioGovernor.evaluate()."""

    approved: bool
    reason: DecisionReason
    symbol: str
    direction: str    # BUY | SELL
    signal_id: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class CooldownConfig(BaseModel):
    """Per-symbol cooldown configuration."""

    cooldown_seconds: float = 300.0

    model_config = ConfigDict(frozen=True)


class GovernorConfig(BaseModel):
    """Runtime configuration for the Portfolio Governor."""

    max_open_positions: int = 5
    max_portfolio_exposure_pct: float = 0.80   # 80 % of capital
    max_symbol_exposure_pct: float = 0.25      # 25 % per symbol
    default_cooldown_seconds: float = 300.0
    symbol_cooldowns: Dict[str, float] = Field(default_factory=dict)
    allow_opposite_side: bool = False           # block same-symbol opposite side by default

    model_config = ConfigDict(frozen=True)
