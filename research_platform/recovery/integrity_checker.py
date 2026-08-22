"""Integrity validator auditing checkpoint hash signatures and consistency limits.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict

from research_platform.recovery.models import Checkpoint

logger = logging.getLogger(__name__)


class IntegrityChecker:
    """Verifies integrity checksums and runs consistency checks across subsystem properties."""

    def __init__(self, container: Any) -> None:
        self.container = container

    def compute_hash(self, checkpoint: Checkpoint) -> str:
        """Calculate SHA256 checksum of the serialized Pydantic model state fields."""
        state_dict = {
            "runtime_state": checkpoint.runtime_state,
            "portfolio_state": checkpoint.portfolio_state,
            "positions_state": checkpoint.positions_state,
            "orders_state": checkpoint.orders_state,
            "trades_state": checkpoint.trades_state,
            "scheduler_state": checkpoint.scheduler_state,
            "strategies_state": checkpoint.strategies_state,
            "monitoring_state": checkpoint.monitoring_state,
            "metrics_state": checkpoint.metrics_state
        }
        serialized = json.dumps(state_dict, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def validate_integrity(self, checkpoint: Checkpoint) -> bool:
        """Run consistency assertions. Return True if valid."""
        logger.info("Executing integrity checks on checkpoint: %s", checkpoint.checkpoint_id)
        
        # 1. Verification of Checksum Hash
        if checkpoint.integrity_hash:
            expected_hash = self.compute_hash(checkpoint)
            if checkpoint.integrity_hash != expected_hash:
                logger.error("Checkpoint validation failed: Hash checksum mismatch!")
                return False

        # 2. Portfolio Consistency check
        # Weights must sum to 1.0 (or close to it) if present
        portfolio = checkpoint.portfolio_state
        if portfolio and "weights" in portfolio:
            weights = portfolio.get("weights")
            if isinstance(weights, dict):
                # Verify individual weights are not negative
                if any(float(w) < 0.0 for w in weights.values() if w is not None):
                    logger.warning("Negative portfolio weight found. Rejecting checkpoint.")
                    return False
                total_w = sum(float(v) for v in weights.values() if v is not None)
                if total_w > 0.0 and abs(total_w - 1.0) > 0.05:
                    logger.warning("Portfolio weights sum to %f (inconsistent!). Rejecting checkpoint.", total_w)
                    return False

        # 3. Position Consistency
        # Quantities cannot be negative unless shorting is explicitly configured
        positions = checkpoint.positions_state
        for pos in positions:
            qty = pos.get("quantity")
            if qty is not None and float(qty) < 0.0:
                logger.warning("Negative position size found for %s. Rejecting checkpoint.", pos.get("symbol"))
                return False

        # 4. Scheduler Consistency
        # Verify scheduler cron state parameters
        scheduler = checkpoint.scheduler_state
        if scheduler and "jobs" in scheduler:
            jobs = scheduler.get("jobs")
            if not isinstance(jobs, list):
                logger.warning("Scheduler jobs state layout is invalid. Rejecting checkpoint.")
                return False

        # 5. Runtime consistency
        runtime = checkpoint.runtime_state
        if runtime and "status" in runtime:
            status = runtime.get("status")
            if status not in ["RUNNING", "PAUSED", "STOPPED", "BOOTING", "SHUTTING_DOWN"]:
                logger.warning("Invalid runtime execution status: %s. Rejecting checkpoint.", status)
                return False

        logger.info("Integrity checks passed successfully.")
        return True
