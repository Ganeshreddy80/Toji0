from pydantic import BaseModel, ConfigDict, Field


class BrokerCapabilities(BaseModel):
    """Immutable model mapping advanced features supported by a broker adapter."""

    supports_market: bool = Field(default=True, description="Market orders support.")
    supports_limit: bool = Field(default=True, description="Limit orders support.")
    supports_stop: bool = Field(default=True, description="Stop market/limit orders support.")
    supports_trailing_stop: bool = Field(default=False, description="Trailing stop order support.")
    supports_reduce_only: bool = Field(default=False, description="Reduce-only executions support.")
    supports_post_only: bool = Field(default=False, description="Post-only execution limit constraints.")
    supports_hedge_mode: bool = Field(default=False, description="Supports dual-sided position holding.")
    supports_oco: bool = Field(default=False, description="One-Cancels-the-Other advanced types.")
    supports_iceberg: bool = Field(default=False, description="Iceberg orders (hidden/displayed splits).")
    supports_brackets: bool = Field(default=False, description="Brackets orders (TP/SL linkages).")
    supports_twap: bool = Field(default=False, description="Time Weighted Average Price algorithms.")
    supports_vwap: bool = Field(default=False, description="Volume Weighted Average Price algorithms.")
    max_leverage: float = Field(default=1.0, description="Highest leverage allowed.")
    precision: int = Field(default=4, description="Standard decimal precision rules.")
    tick_size: float = Field(default=0.01, description="Minimum price movement increment.")
    min_notional: float = Field(default=10.0, description="Minimum order value threshold.")

    model_config = ConfigDict(frozen=True)
