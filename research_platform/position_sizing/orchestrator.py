"""Position Sizing and Capital Allocation Orchestrator.
"""

from __future__ import annotations

import logging
import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from toji_platform.core.event_bus import IEventBus
from research_platform.position_sizing.models import SizingConfig, SizingResult
from research_platform.portfolio_intelligence.risk_parity import RiskParityAllocator
from research_platform.risk_engine_v2.kelly_criterion import KellySizingEngine

logger = logging.getLogger(__name__)


class PositionSizingOrchestrator:
    """Manages position sizing, capital allocation, limits, and runtime exposures."""

    def __init__(self, event_bus: IEventBus, container: Any) -> None:
        self._event_bus = event_bus
        self._container = container
        self._lock = threading.RLock()
        
        # In-memory price cache from tick updates
        self._latest_prices: Dict[str, float] = {}
        
        # Historical results for logging and metrics
        self._completed_sizings: List[SizingResult] = []

        # Sizing configuration
        self._config = SizingConfig(
            method=os.getenv("POSITION_SIZING_METHOD", "fixed_risk").lower(),
            risk_percent=float(os.getenv("RISK_PERCENT", "0.01")),
            default_price=float(os.getenv("DEFAULT_PRICE", "50000.0")),
            max_portfolio_exposure_pct=float(os.getenv("MAX_PORTFOLIO_EXPOSURE_PCT", "0.50")),
            max_symbol_exposure_pct=float(os.getenv("MAX_SYMBOL_EXPOSURE_PCT", "0.20")),
            max_position_qty_cap=float(os.getenv("MAX_POSITION_QTY_CAP", "1000.0")),
            target_volatility=float(os.getenv("TARGET_VOLATILITY", "0.10")),
            # FP-3D: leverage cap — max scale = target_vol / vol before exposure caps
            max_leverage=float(os.getenv("MAX_LEVERAGE", "2.0")),
            # FP-3D: fallback annualized vol (50%/year) — risk-policy conservative floor
            fallback_volatility=float(os.getenv("FALLBACK_VOLATILITY", "0.50")),
            win_rate=float(os.getenv("WIN_RATE", "0.55")),
            payoff_ratio=float(os.getenv("PAYOFF_RATIO", "2.0")),
            kelly_leverage_frac=float(os.getenv("KELLY_LEVERAGE_FRAC", "0.5")),
            max_open_positions=int(os.getenv("MAX_OPEN_POSITIONS", "10")),
            fallback_balance=float(os.getenv("ACCOUNT_BALANCE", "100000.0")),
        )

        # Allocate engines
        self._risk_parity = RiskParityAllocator()
        self._kelly_engine = KellySizingEngine(
            fraction_multiplier=self._config.kelly_leverage_frac,
            max_fraction=self._config.max_symbol_exposure_pct
        )

    def on_tick(self, event: Any) -> None:
        """Cache prices from market ticks/valuation events."""
        try:
            payload = getattr(event, "payload", {}) or {}
            symbol = payload.get("symbol") or payload.get("s") or payload.get("ticker")
            price_raw = payload.get("price") or payload.get("p") or payload.get("last_price") or payload.get("c")
            if symbol and price_raw is not None:
                with self._lock:
                    self._latest_prices[symbol] = float(price_raw)
        except Exception as e:
            logger.error("PositionSizing: Failed to cache price from tick: %s", e)

    def calculate_size(self, symbol: str, direction: str, proposed_price: Optional[float] = None) -> SizingResult:
        """Main entry point to calculate the final safe transaction quantity."""
        with self._lock:
            # 1. Resolve pricing
            price = proposed_price or self._latest_prices.get(symbol) or self._config.default_price
            
            # 2. Retrieve balance & cash from Portfolio Accounting
            equity = self._config.fallback_balance
            cash = self._config.fallback_balance
            existing_symbol_exposure = 0.0
            total_existing_exposure = 0.0
            positions_count = 0

            accounting = None
            if self._container.has("PortfolioAccounting"):
                accounting = self._container.resolve("PortfolioAccounting")
                summary = accounting.get_portfolio_summary()
                equity = summary.get("equity", equity)
                cash = summary.get("cash_balance", cash)
                positions = accounting.valuation_engine.get_all_positions()
                positions_count = len(positions)
                
                for p in positions:
                    mv = abs(p.market_value)
                    total_existing_exposure += mv
                    if p.symbol == symbol:
                        existing_symbol_exposure = mv

            reasons: List[str] = []
            raw_qty = 0.0
            method = self._config.method

            # 3. Calculate position sizing based on method
            if method == "fixed_risk":
                stop_distance = price * 0.02  # standard 2% stop distance
                risk_amount = equity * self._config.risk_percent
                raw_qty = risk_amount / stop_distance
                reasons.append(f"Fixed Risk: risk_pct={self._config.risk_percent}, risk_amount=${risk_amount:.2f}")

            elif method == "kelly":
                kelly_frac = self._kelly_engine.calculate_sizing(self._config.win_rate, self._config.payoff_ratio)
                risk_amount = equity * kelly_frac
                raw_qty = risk_amount / (price * 0.02)
                reasons.append(f"Kelly: win_rate={self._config.win_rate}, payoff={self._config.payoff_ratio}, frac={kelly_frac:.4f}")

            elif method == "volatility":
                # FP-3D: Canonical Volatility Target Sizing
                # Queries 'annualized_vol' from the Feature Platform (canonical feature).
                # annualized_vol = sample_std(log_return, 1440) * sqrt(525600)
                # Units: dimensionless annualized fraction (e.g. 0.725 = 72.5%/year for BTC).
                # Fallback: self._config.fallback_volatility (0.50 = 50%/year, conservative risk-policy floor).
                # Safety: vol_safe = max(vol, target_volatility / max_leverage) prevents >max_leverage scale.
                # Formula: scale = min(target_volatility / vol_safe, max_leverage)
                #          target_capital = equity * scale
                vol = self._config.fallback_volatility  # 0.50 = 50% annualized fallback
                if self._container.has("FeaturePlatformOrchestrator"):
                    fp_orch = self._container.resolve("FeaturePlatformOrchestrator")
                    df = fp_orch.query_realtime(["annualized_vol"], [symbol])
                    if (
                        df is not None
                        and not df.empty
                        and "annualized_vol" in df.columns
                    ):
                        raw_val = df.iloc[0]["annualized_vol"]
                        import math as _math
                        if raw_val is not None and not _math.isnan(float(raw_val)):
                            # Only accept valid (non-NaN) values — NaN means warm-up; use fallback
                            vol = float(raw_val)

                # Minimum volatility floor: prevents leverage from exceeding max_leverage
                # floor = target_volatility / max_leverage  e.g. 0.10 / 2.0 = 0.05
                min_vol = self._config.target_volatility / self._config.max_leverage
                vol_safe = max(vol, min_vol)

                # Leverage scale capped at max_leverage (2.0 default)
                raw_scale = self._config.target_volatility / vol_safe
                scale = min(raw_scale, self._config.max_leverage)

                target_capital = equity * scale
                raw_qty = target_capital / price
                risk_amount = raw_qty * (price * 0.02)
                reasons.append(
                    f"Volatility Target (FP-3D): target_vol={self._config.target_volatility}, "
                    f"annualized_vol={vol:.4f}, vol_safe={vol_safe:.4f}, "
                    f"scale={scale:.4f}, max_leverage={self._config.max_leverage}"
                )

            elif method == "equal_weight":
                weight = 1.0 / self._config.max_open_positions
                allocated_capital = equity * weight
                raw_qty = allocated_capital / price
                risk_amount = raw_qty * (price * 0.02)
                reasons.append(f"Equal Weight: weight={weight:.4f}, slots={self._config.max_open_positions}")

            elif method == "risk_parity":
                # FP-3D: Risk parity also uses canonical annualized_vol.
                # Fallback: fallback_volatility (0.50) when Feature Platform unavailable.
                vol = self._config.fallback_volatility
                if self._container.has("FeaturePlatformOrchestrator"):
                    fp_orch = self._container.resolve("FeaturePlatformOrchestrator")
                    df = fp_orch.query_realtime(["annualized_vol"], [symbol])
                    if (
                        df is not None
                        and not df.empty
                        and "annualized_vol" in df.columns
                    ):
                        raw_val = df.iloc[0]["annualized_vol"]
                        import math as _math
                        if raw_val is not None and not _math.isnan(float(raw_val)):
                            vol = float(raw_val)

                # Compute risk parity weight against a default baseline
                vols_dict = {symbol: vol, "baseline": self._config.fallback_volatility}
                weights = self._risk_parity.calculate_weights(vols_dict)
                weight = weights.get(symbol, 0.5)
                allocated_capital = equity * weight
                raw_qty = allocated_capital / price
                risk_amount = raw_qty * (price * 0.02)
                reasons.append(f"Risk Parity: annualized_vol={vol:.4f}, weight={weight:.4f}")

            else:
                # Fallback to Fixed Risk
                stop_distance = price * 0.02
                risk_amount = equity * 0.01
                raw_qty = risk_amount / stop_distance
                reasons.append("Fallback to default Fixed Risk sizing.")

            # 4. Apply Capital Allocation constraints & caps
            final_qty = raw_qty
            proposed_exposure = final_qty * price

            # A. Symbol Exposure Cap
            max_symbol_exposure = equity * self._config.max_symbol_exposure_pct
            if proposed_exposure > max_symbol_exposure:
                final_qty = max_symbol_exposure / price
                proposed_exposure = final_qty * price
                reasons.append(f"Symbol Cap Triggered: restricted to {self._config.max_symbol_exposure_pct * 100:.1f}% equity (${max_symbol_exposure:.2f})")

            # B. Portfolio Exposure Cap
            max_portfolio_exposure = equity * self._config.max_portfolio_exposure_pct
            remaining_exposure_budget = max_portfolio_exposure - total_existing_exposure
            if remaining_exposure_budget <= 0.0:
                final_qty = 0.0
                proposed_exposure = 0.0
                reasons.append("Portfolio Exposure Budget Exhausted: 0 quantity allocated.")
            elif proposed_exposure > remaining_exposure_budget:
                final_qty = remaining_exposure_budget / price
                proposed_exposure = final_qty * price
                reasons.append(f"Portfolio Exposure Cap Triggered: remaining budget ${remaining_exposure_budget:.2f}")

            # C. Position Quantity Cap
            if final_qty > self._config.max_position_qty_cap:
                final_qty = self._config.max_position_qty_cap
                proposed_exposure = final_qty * price
                reasons.append(f"Position Qty Cap Triggered: capped at {self._config.max_position_qty_cap}")

            # D. Cash Availability Check
            if proposed_exposure > cash:
                final_qty = cash / price
                proposed_exposure = final_qty * price
                reasons.append(f"Cash Check Triggered: restricted to available cash balance ${cash:.2f}")

            # E. Lot Size Alignment (0.001)
            lot_size = 0.001
            final_qty = round(final_qty / lot_size) * lot_size
            proposed_exposure = final_qty * price

            # Compile sizing result
            res = SizingResult(
                symbol=symbol,
                direction=direction,
                method=method.upper(),
                raw_qty=raw_qty,
                final_qty=final_qty,
                allocated_capital=proposed_exposure,
                risk_amount=final_qty * (price * 0.02),
                price=price,
                reasons=reasons
            )
            
            self._completed_sizings.append(res)
            
            # Publish system.position_size_calculated
            try:
                from research_platform.position_sizing.events import PositionSizeCalculated
                self._event_bus.publish(PositionSizeCalculated(payload={
                    "symbol": symbol,
                    "direction": direction,
                    "quantity": final_qty,
                    "method": method.upper(),
                    "allocated_capital": proposed_exposure
                }))
            except Exception:
                pass

            return res

    def get_summary(self) -> dict:
        """Returns statistics for status dashboard APIs."""
        with self._lock:
            # Sizing values
            last_sizing = self._completed_sizings[-1] if self._completed_sizings else None
            
            # Fetch from accounting
            equity = self._config.fallback_balance
            cash = self._config.fallback_balance
            gross_exposure = 0.0
            
            if self._container.has("PortfolioAccounting"):
                accounting = self._container.resolve("PortfolioAccounting")
                summary = accounting.get_portfolio_summary()
                equity = summary.get("equity", equity)
                cash = summary.get("cash_balance", cash)
                for p in accounting.valuation_engine.get_all_positions():
                    gross_exposure += abs(p.market_value)

            return {
                "current_exposure": round(gross_exposure, 4),
                "capital_allocated": round(equity - cash, 4),
                "cash_remaining": round(cash, 4),
                "risk_per_trade": round(last_sizing.risk_amount, 4) if last_sizing else 0.0,
                "sizing_method": self._config.method.upper(),
                "allocation_method": "PORTFOLIO_CONSTRAINED",
                "completed_exits_count": len(self._completed_sizings)
            }
