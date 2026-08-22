"""Risk controls during historical simulation.
"""

from __future__ import annotations

from research_platform.backtesting_engine.models import PortfolioState


class SimulationRiskController:
    """Evaluates margin ratios, peak drawdowns, and triggers stops during backtests."""

    def __init__(
        self,
        max_drawdown_pct: float = 0.20,
        maintenance_margin_pct: float = 0.30
    ) -> None:
        self._max_drawdown_pct = max_drawdown_pct
        self._maintenance_margin_pct = maintenance_margin_pct
        self._peak_equity = 0.0

    def check_risk(self, state: PortfolioState) -> tuple[bool, str]:
        """Check portfolio state for drawdown stops or margin liquidations.

        Returns:
            Tuple of (should_liquidate_flag, reason_message).
        """
        # 1. Update peak equity
        if state.equity > self._peak_equity:
            self._peak_equity = state.equity

        # 2. Check drawdown stop
        drawdown = 0.0
        if self._peak_equity > 0.0:
            drawdown = (self._peak_equity - state.equity) / self._peak_equity

        if drawdown > self._max_drawdown_pct:
            return True, f"Drawdown stop triggered: peak drawdown {drawdown:.2%} exceeded {self._max_drawdown_pct:.2%}"

        # 3. Check maintenance margin liquidation (Margin call)
        # Margin call triggers if equity < maintenance margin
        if state.margin > 0.0 and state.equity < (state.margin * self._maintenance_margin_pct):
            return True, f"Margin Call: Equity {state.equity:.2f} fell below maintenance level {state.margin * self._maintenance_margin_pct:.2f}"

        return False, ""
