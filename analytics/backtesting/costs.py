"""Commission and slippage transaction cost models for backtesting order executions."""

from __future__ import annotations

import abc


class ICommissionModel(abc.ABC):
    """Abstract contract for calculating execution commissions."""

    @abc.abstractmethod
    def calculate_commission(self, qty: float, price: float) -> float:
        """Calculate the total commission fee for a trade execution."""


class ZeroCommissionModel(ICommissionModel):
    """Fee-free commission model."""

    def calculate_commission(self, qty: float, price: float) -> float:
        return 0.0


class FixedCommissionModel(ICommissionModel):
    """Commission model that charges a flat cash fee per transaction."""

    def __init__(self, fee_per_trade: float = 1.0) -> None:
        self.fee_per_trade = fee_per_trade

    def calculate_commission(self, qty: float, price: float) -> float:
        return self.fee_per_trade


class LinearCommissionModel(ICommissionModel):
    """Commission model charging a percentage of total trade value."""

    def __init__(self, bps_rate: float = 0.001) -> None:
        self.bps_rate = bps_rate  # 0.001 represents 10 bps (0.1%)

    def calculate_commission(self, qty: float, price: float) -> float:
        return qty * price * self.bps_rate


class ISlippageModel(abc.ABC):
    """Abstract contract for calculating trade fill price slippage."""

    @abc.abstractmethod
    def calculate_slippage(self, price: float, qty: float, side: str, volatility: float = 0.0) -> float:
        """Calculate the absolute price slippage (offset to buy or sell price)."""


class ZeroSlippageModel(ISlippageModel):
    """Slippage-free model."""

    def calculate_slippage(self, price: float, qty: float, side: str, volatility: float = 0.0) -> float:
        return 0.0


class FixedSpreadSlippageModel(ISlippageModel):
    """Slippage model applying a static spread multiplier to fill prices."""

    def __init__(self, spread_fraction: float = 0.0005) -> None:
        self.spread_fraction = spread_fraction  # 0.0005 = 5 bps of the price

    def calculate_slippage(self, price: float, qty: float, side: str, volatility: float = 0.0) -> float:
        # Slippage is always positive, representing a price penalty:
        # Buy fills higher, sell fills lower.
        return price * self.spread_fraction


class VolatilityScaledSlippageModel(ISlippageModel):
    """Slippage model scaled by rolling historical volatility and quantity relative to liquidity."""

    def __init__(self, base_slip_fraction: float = 0.0002, vol_multiplier: float = 0.1) -> None:
        self.base_slip_fraction = base_slip_fraction
        self.vol_multiplier = vol_multiplier

    def calculate_slippage(self, price: float, qty: float, side: str, volatility: float = 0.0) -> float:
        # Volatility scales the slippage penalty quadratically or linearly
        multiplier = 1.0 + (volatility * self.vol_multiplier)
        return price * self.base_slip_fraction * multiplier
