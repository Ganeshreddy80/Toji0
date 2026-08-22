"""Real-Time Risk Monitor — calculates a 0–100 risk score every tick."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from research_platform.risk_governance.models import KillSwitchState, RiskSnapshot

logger = logging.getLogger(__name__)


class RealTimeRiskMonitor:
    """Computes a portfolio risk score (0 = dangerous, 100 = healthy) on every tick.

    Score components (each out of 100, then weighted average):
        exposure_score:         Penalises over-concentration.
        drawdown_score:         Penalises running drawdown.
        correlation_score:      Penalises correlated open positions.
        leverage_score:         Penalises excessive leverage.
        consecutive_loss_score: Penalises repeated losing trades.
    """

    WEIGHTS = {
        "exposure": 0.30,
        "drawdown": 0.25,
        "correlation": 0.20,
        "leverage": 0.15,
        "consecutive": 0.10,
    }

    def __init__(
        self,
        max_exposure_pct: float = 60.0,   # 60 % of capital in open trades is the cap
        max_drawdown_pct: float = 8.0,
        max_leverage: float = 3.0,
        max_consecutive_losses: int = 5,
    ) -> None:
        self.max_exposure_pct = max_exposure_pct
        self.max_drawdown_pct = max_drawdown_pct
        self.max_leverage = max_leverage
        self.max_consecutive_losses = max_consecutive_losses

    def calculate_risk_score(
        self,
        capital: float,
        open_positions: List[Dict[str, Any]],
        peak_capital: float,
        leverage: float,
        consecutive_losses: int,
        daily_pnl: float,
        correlated_pairs: int = 0,
    ) -> RiskSnapshot:
        """Compute a RiskSnapshot for the current portfolio state.

        Args:
            open_positions: List of dicts with keys 'symbol', 'notional_usdt', 'unrealized_pnl'.
        """
        # ── component scores ──────────────────────────────────────────────────

        # 1. Exposure
        total_notional = sum(p.get("notional_usdt", 0.0) for p in open_positions)
        exposure_pct = (total_notional / capital * 100.0) if capital > 0.0 else 0.0
        exposure_score = max(0.0, 100.0 - (exposure_pct / self.max_exposure_pct) * 100.0)

        # 2. Drawdown
        drawdown_pct = (peak_capital - capital) / peak_capital * 100.0 if peak_capital > 0.0 else 0.0
        drawdown_score = max(0.0, 100.0 - (drawdown_pct / self.max_drawdown_pct) * 100.0)

        # 3. Correlation
        # -5 pts per correlated pair beyond 1
        correlation_score = max(0.0, 100.0 - max(0, correlated_pairs - 1) * 5.0)

        # 4. Leverage
        leverage_score = max(0.0, 100.0 - (leverage / self.max_leverage) * 100.0)

        # 5. Consecutive losses
        consec_score = max(0.0, 100.0 - (consecutive_losses / self.max_consecutive_losses) * 100.0)

        # ── weighted composite ────────────────────────────────────────────────
        raw_score = (
            exposure_score * self.WEIGHTS["exposure"] +
            drawdown_score * self.WEIGHTS["drawdown"] +
            correlation_score * self.WEIGHTS["correlation"] +
            leverage_score * self.WEIGHTS["leverage"] +
            consec_score * self.WEIGHTS["consecutive"]
        )
        risk_score = round(max(0.0, min(raw_score, 100.0)), 1)

        # ── derive mode ───────────────────────────────────────────────────────
        if risk_score >= 80.0:
            mode = KillSwitchState.NORMAL
        elif risk_score >= 60.0:
            mode = KillSwitchState.WARNING
        elif risk_score >= 40.0:
            mode = KillSwitchState.REDUCED_RISK
        else:
            mode = KillSwitchState.HALTED

        unrealized = sum(p.get("unrealized_pnl", 0.0) for p in open_positions)

        snap = RiskSnapshot(
            risk_score=risk_score,
            mode=mode,
            exposure_pct=round(exposure_pct, 2),
            open_positions=len(open_positions),
            kill_switch_active=(mode == KillSwitchState.HALTED),
            unrealized_pnl=round(unrealized, 2),
            daily_pnl=round(daily_pnl, 2),
            consecutive_losses=consecutive_losses,
        )

        if risk_score < 50.0:
            logger.warning("Risk Score DANGER: %.1f / mode=%s", risk_score, mode.value)
        else:
            logger.info("Risk Score: %.1f / mode=%s", risk_score, mode.value)

        return snap
