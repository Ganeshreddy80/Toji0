"""Checkpoint Manager aggregating platform subsystem states.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from research_platform.recovery.interfaces import ICheckpointManager
from research_platform.recovery.models import Checkpoint
from research_platform.recovery.integrity_checker import IntegrityChecker

logger = logging.getLogger(__name__)


class CheckpointManager(ICheckpointManager):
    """Orchestrates periodic state capture, checksum hash computing, and database commits."""

    def __init__(self, container: Any, repository: Any) -> None:
        self.container = container
        self.repository = repository
        self.integrity_checker = IntegrityChecker(container)

    def create_checkpoint(self) -> Checkpoint:
        """Gathers states from all active TOJI subsystems and returns a new Checkpoint."""
        logger.info("Capturing active TOJI system state for checkpointing...")
        
        # 1. Gather runtime state
        runtime_state = {}
        try:
            engine = self.container.resolve("RuntimeEngine")
            if engine and hasattr(engine, "get_state"):
                runtime_state = engine.get_state()
        except Exception:
            pass

        # 2. Gather portfolio state
        portfolio_state = {}
        try:
            port_orch = self.container.resolve("PortfolioEngineOrchestrator")
            if port_orch and hasattr(port_orch, "get_state"):
                portfolio_state = port_orch.get_state()
        except Exception:
            pass

        # 3. Gather positions
        positions_state = []
        try:
            oms = self.container.resolve("OMSOrchestrator")
            if oms and hasattr(oms, "get_positions"):
                positions_state = oms.get_positions()
        except Exception:
            pass

        # 4. Gather orders
        orders_state = []
        try:
            oms = self.container.resolve("OMSOrchestrator")
            if oms and hasattr(oms, "get_orders"):
                orders_state = oms.get_orders()
        except Exception:
            pass

        # 5. Gather scheduler state
        scheduler_state = {}
        try:
            sched = self.container.resolve("StrategySchedulerOrchestrator")
            if sched and hasattr(sched, "get_state"):
                scheduler_state = sched.get_state()
        except Exception:
            pass

        # 6. Gather strategy settings
        strategies_state = []
        try:
            strat_orch = self.container.resolve("StrategyLifecycleOrchestrator")
            if strat_orch and hasattr(strat_orch, "get_strategies"):
                strategies_state = strat_orch.get_strategies()
        except Exception:
            pass

        checkpoint = Checkpoint(
            checkpoint_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            runtime_state=runtime_state,
            portfolio_state=portfolio_state,
            positions_state=positions_state,
            orders_state=orders_state,
            scheduler_state=scheduler_state,
            strategies_state=strategies_state
        )

        # Compute hash
        checkpoint.integrity_hash = self.integrity_checker.compute_hash(checkpoint)
        return checkpoint

    def save_checkpoint(self, checkpoint: Checkpoint) -> None:
        logger.info("Saving checkpoint: %s to repository...", checkpoint.checkpoint_id)
        self.repository.save_checkpoint(checkpoint)
        
        # Publish event
        try:
            eb = self.container.resolve("IEventBus")
            if eb:
                from research_platform.recovery.events import CheckpointSaved
                eb.publish("CheckpointSaved", CheckpointSaved(event_id=str(uuid.uuid4()), checkpoint_id=checkpoint.checkpoint_id).model_dump())
        except Exception:
            pass

    def get_latest_checkpoint(self) -> Optional[Checkpoint]:
        return self.repository.get_latest_checkpoint()
