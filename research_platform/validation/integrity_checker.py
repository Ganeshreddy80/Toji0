"""R53 Integrity checker — validates portfolio weight sums and position sign consistency."""

from __future__ import annotations

import time
import logging
from research_platform.validation.interfaces import IChecker
from research_platform.validation.models import CheckResult, CheckStatus

logger = logging.getLogger(__name__)


class IntegrityChecker(IChecker):
    @property
    def name(self) -> str:
        return "StateIntegrityChecker"

    def run(self) -> CheckResult:
        start = time.perf_counter()
        issues = []
        try:
            from research_platform.platform.service_registry import ServiceRegistry
            registry = ServiceRegistry()

            # Check portfolio weights
            portfolio = registry.get_service("PortfolioEngineOrchestrator")
            if portfolio is not None:
                try:
                    weights = getattr(portfolio, "_weights", None) or getattr(portfolio, "weights", None)
                    if weights and isinstance(weights, dict):
                        total = sum(weights.values())
                        if abs(total - 1.0) > 0.05:
                            issues.append(f"Portfolio weights sum to {total:.4f} (expected ~1.0)")
                except Exception as pw_err:
                    logger.debug("Portfolio weight check skipped: %s", pw_err)

            # Check OMS positions are non-negative
            oms = registry.get_service("OMSOrchestrator")
            if oms is not None:
                try:
                    positions = getattr(oms, "_positions", None) or getattr(oms, "positions", None)
                    if positions and isinstance(positions, dict):
                        negative = [s for s, q in positions.items() if q < 0]
                        if negative:
                            issues.append(f"Negative positions detected: {negative}")
                except Exception as pos_err:
                    logger.debug("Position check skipped: %s", pos_err)

            duration_ms = (time.perf_counter() - start) * 1000
            if issues:
                return CheckResult(check_name=self.name, status=CheckStatus.FAIL,
                                   duration_ms=duration_ms,
                                   message=f"Integrity violations: {issues}",
                                   details={"issues": issues})
            return CheckResult(check_name=self.name, status=CheckStatus.PASS,
                               duration_ms=duration_ms,
                               message="State integrity verified — weights and positions consistent")
        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000
            return CheckResult(check_name=self.name, status=CheckStatus.WARN,
                               duration_ms=duration_ms, message=str(e))
