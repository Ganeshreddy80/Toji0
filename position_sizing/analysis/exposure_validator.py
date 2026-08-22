"""Exposure Validator for checking position boundaries and risk thresholds."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ExposureValidator:
    """Validates position details against exposure, leverage, and risk constraints."""

    def validate(
        self,
        quantity: float,
        entry_price: float,
        balance: float,
        stop_distance: float,
        required_leverage: float,
        required_margin: float,
        max_leverage_limit: float = 10.0,
        max_single_trade_risk_pct: float = 0.02,
        max_portfolio_exposure_pct: float = 0.50,
        **kwargs: Any,
    ) -> tuple[bool, list[str]]:
        """Validate if the proposed sizing is within safety boundaries.

        NOTE: This is an internal component. It is designed to be called exclusively
        by PositionSizingEngine, which always passes explicit values for
        max_leverage_limit, max_single_trade_risk_pct, and max_portfolio_exposure_pct
        sourced from the configuration provider. The parameter defaults shown here
        are a last-resort safety net and must NOT be relied upon by callers.
        Direct calls to this method without explicit risk parameters are not supported.

        Returns:
            (success, violations)
        """
        violations: list[str] = []

        if quantity <= 0:
            violations.append("Quantity must be positive and non-zero.")
            return False, violations

        # 1. Leverage violation check
        if required_leverage > max_leverage_limit:
            violations.append(
                f"Leverage limit exceeded: Required leverage {required_leverage:.2f} "
                f"exceeds maximum allowed {max_leverage_limit:.2f}."
            )

        # 2. Margin capability check
        if required_margin > balance:
            violations.append(
                f"Insufficient margin: Required margin {required_margin:.2f} "
                f"exceeds available account balance {balance:.2f}."
            )

        # 3. Single trade risk limit check
        risk_amount = quantity * stop_distance
        max_single_risk = balance * max_single_trade_risk_pct
        if risk_amount > max_single_risk + 1e-5:
            violations.append(
                f"Single trade risk limit exceeded: Proposed risk ${risk_amount:.2f} "
                f"exceeds limit of ${max_single_risk:.2f} ({max_single_trade_risk_pct*100:.1f}% of balance)."
            )

        # 4. Portfolio exposure limit check
        position_value = quantity * entry_price
        max_exposure = balance * max_portfolio_exposure_pct
        if position_value > max_exposure + 1e-5:
            violations.append(
                f"Portfolio exposure limit exceeded: Position value ${position_value:.2f} "
                f"exceeds limit of ${max_exposure:.2f} ({max_portfolio_exposure_pct*100:.1f}% of balance)."
            )

        success = len(violations) == 0
        return success, violations
