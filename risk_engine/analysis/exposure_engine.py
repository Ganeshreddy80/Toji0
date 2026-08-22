"""Portfolio Exposure Engine for calculating asset exposures, concentrations, and correlation metrics."""

from __future__ import annotations

import logging
from typing import Any

from risk_engine.core.models import ExposureRisk, PortfolioRisk

logger = logging.getLogger(__name__)


class ExposureEngine:
    """Aggregates active positions and balance data to compute multi-dimensional exposures."""

    def __init__(self) -> None:
        pass

    def calculate_exposures(
        self,
        positions: list[Any],
        equity: float,
        balance: float,
        sector_mapping: dict[str, str] | None = None,
        exchange_mapping: dict[str, str] | None = None,
        correlation_matrix: dict[str, dict[str, float]] | None = None,
        total_risk_budget: float = 100000.0,
    ) -> tuple[ExposureRisk, PortfolioRisk]:
        """
        Aggregate positions and compute metrics.
        Arguments:
            - positions: List of active Position models
            - equity: current account equity
            - balance: current account balance
            - sector_mapping: mapping of symbol to sector (default fallbacks)
            - exchange_mapping: mapping of symbol to exchange
            - correlation_matrix: rolling asset correlation dict
            - total_risk_budget: maximum dollar risk budget
        """
        symbol_exposure: dict[str, float] = {}
        sector_exposure: dict[str, float] = {}
        coin_exposure: dict[str, float] = {}
        exchange_exposure: dict[str, float] = {}

        long_exp = 0.0
        short_exp = 0.0
        gross_exp = 0.0
        net_exp = 0.0
        portfolio_heat = 0.0

        default_sectors = {
            "BTC/USDT": "Layer1",
            "ETH/USDT": "Layer1",
            "SOL/USDT": "Layer1",
            "BNB/USDT": "ExchangeToken",
            "ADA/USDT": "Layer1",
            "XRP/USDT": "Payment",
        }

        resolved_sectors = default_sectors.copy()
        if sector_mapping:
            resolved_sectors.update(sector_mapping)

        for pos in positions:
            symbol = pos.symbol
            val = float(pos.market_value)
            qty = float(pos.quantity)
            side = str(pos.side.value if hasattr(pos.side, "value") else pos.side).upper()
            margin = float(pos.margin_used)

            # Accumulate exposures
            symbol_exposure[symbol] = symbol_exposure.get(symbol, 0.0) + val
            gross_exp += val
            portfolio_heat += margin

            if "BUY" in side or "LONG" in side:
                long_exp += val
                net_exp += val
            else:
                short_exp += val
                net_exp -= val

            # Sector exposure
            sec = resolved_sectors.get(symbol, "Other")
            sector_exposure[sec] = sector_exposure.get(sec, 0.0) + val

            # Coin exposure (base asset, e.g. BTC)
            coin = symbol.split("/")[0] if "/" in symbol else symbol
            coin_exposure[coin] = coin_exposure.get(coin, 0.0) + val

            # Exchange exposure
            exch = exchange_mapping.get(symbol, "Binance") if exchange_mapping else "Binance"
            exchange_exposure[exch] = exchange_exposure.get(exch, 0.0) + val

        # Calculate stablecoin allocation
        # Stablecoin allocation = (Equity - Gross Exposure) / Equity if Equity > 0 else 100%
        used_capital = gross_exp
        stable_alloc = max(0.0, min(100.0, ((equity - used_capital) / equity * 100.0))) if equity > 0 else 100.0

        # Calculate remaining risk budget
        remaining_budget = max(0.0, total_risk_budget - portfolio_heat)

        # Diversification Score: Simpson's Index or Herfindahl-Hirschman Index (HHI) variant
        # If HHI = sum((val/gross)^2). Diversification = 1.0 - HHI.
        if gross_exp > 0:
            hhi = sum((v / gross_exp) ** 2 for v in symbol_exposure.values())
            diversification = round(1.0 - hhi, 4)
        else:
            diversification = 1.0

        exposure_risk = ExposureRisk(
            symbol_exposure=symbol_exposure,
            sector_exposure=sector_exposure,
            coin_exposure=coin_exposure,
            stablecoin_allocation=round(stable_alloc, 2),
            exchange_exposure=exchange_exposure,
        )

        portfolio_risk = PortfolioRisk(
            gross_exposure=round(gross_exp, 2),
            net_exposure=round(net_exp, 2),
            long_exposure=round(long_exp, 2),
            short_exposure=round(short_exp, 2),
            open_positions_count=len(positions),
            diversification_score=diversification,
            portfolio_heat=round(portfolio_heat, 2),
            remaining_risk_budget=round(remaining_budget, 2),
        )

        return exposure_risk, portfolio_risk
