"""Execution Report — per-trade quality analytics after every fill."""

from __future__ import annotations

from research_platform.execution_engine.simulator_models import (
    SimulatedFill,
    ExecutionQualityReport,
    OrderStatus,
)


class ExecutionAnalytics:
    """Generates an ExecutionQualityReport from a completed SimulatedFill.

    Quality score (0–100) penalises:
        - Slippage   (up to –30 pts)
        - High fees  (up to –20 pts)
        - Rejection  (–50 pts flat)
        - Partial fill (–10 pts)
    """

    # Penalty thresholds
    MAX_SLIPPAGE_BPS = 30.0   # 30 bps = score → 0 for slippage component
    MAX_FEE_BPS = 10.0        # 10 bps = score → 0 for fee component

    def generate_report(
        self,
        fill: SimulatedFill,
        liquidity_passed: bool = True,
        risk_passed: bool = True,
    ) -> ExecutionQualityReport:
        """Compute score and produce an analytics report card."""

        # Immediate disqualifiers
        if fill.status == OrderStatus.REJECTED:
            score = 50.0  # non-zero so caller can still read the report
        else:
            score = 100.0

            # Slippage penalty: linear from 0 to MAX_SLIPPAGE_BPS
            slippage_bps = (fill.slippage / fill.expected_price * 10_000.0) if fill.expected_price > 0 else 0.0
            slippage_penalty = min(slippage_bps / self.MAX_SLIPPAGE_BPS, 1.0) * 30.0
            score -= slippage_penalty

            # Fee penalty
            fee_bps = (fill.fee_paid / (fill.fill_price * fill.quantity) * 10_000.0) if (fill.fill_price * fill.quantity) > 0 else 0.0
            fee_penalty = min(fee_bps / self.MAX_FEE_BPS, 1.0) * 20.0
            score -= fee_penalty

            # Partial fill penalty
            if fill.status == OrderStatus.PARTIAL_FILLED:
                score -= 10.0

        if not liquidity_passed:
            score -= 15.0
        if not risk_passed:
            score -= 15.0

        score = max(0.0, min(score, 100.0))

        # Slippage percentage for the report
        slippage_pct = (
            (fill.slippage / fill.expected_price * 100.0) if fill.expected_price > 0 else 0.0
        )

        return ExecutionQualityReport(
            order_id=fill.order_id,
            symbol=fill.symbol,
            expected_price=fill.expected_price,
            actual_fill=fill.fill_price,
            slippage_abs=fill.slippage,
            slippage_pct=round(slippage_pct, 4),
            fee_usdt=fill.fee_paid,
            liquidity_check="PASS" if liquidity_passed else "FAIL",
            risk_check="PASS" if risk_passed else "FAIL",
            execution_score=round(score, 1),
        )
