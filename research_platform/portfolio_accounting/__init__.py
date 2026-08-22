"""Portfolio Accounting subsystem for TOJI trading platform.

Exports:
  - AccountingService   — top-level facade (event-driven)
  - PortfolioAccountingPlugin — DI boot plugin
  - ValuatedPosition, PortfolioSnapshot, TradeRecord, PortfolioMetrics
"""

from research_platform.portfolio_accounting.accounting_service import AccountingService
from research_platform.portfolio_accounting.models import (
    PortfolioMetrics,
    PortfolioSnapshot,
    TradeRecord,
    ValuatedPosition,
)
from research_platform.portfolio_accounting.plugin import PortfolioAccountingPlugin

__all__ = [
    "AccountingService",
    "PortfolioAccountingPlugin",
    "ValuatedPosition",
    "PortfolioSnapshot",
    "TradeRecord",
    "PortfolioMetrics",
]
