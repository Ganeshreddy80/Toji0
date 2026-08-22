"""Recovery Engine executing recovery stages.
"""

from __future__ import annotations

import time
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from research_platform.recovery.interfaces import IRecoveryEngine
from research_platform.recovery.models import Checkpoint, RecoverySession
from research_platform.recovery.repository import RecoveryRepository
from research_platform.recovery.database_recovery import DatabaseRecoveryManager
from research_platform.recovery.integrity_checker import IntegrityChecker
from research_platform.recovery.session_recovery import SessionRecoveryManager
from research_platform.recovery.strategy_recovery import StrategyRecoveryManager
from research_platform.recovery.portfolio_recovery import PortfolioRecoveryManager
from research_platform.recovery.position_recovery import PositionRecoveryManager
from research_platform.recovery.scheduler_recovery import SchedulerRecoveryManager
from research_platform.recovery.runtime_recovery import RuntimeRecoveryManager

logger = logging.getLogger(__name__)


class RecoveryEngine(IRecoveryEngine):
    """Executes the complete sequenced recovery stages boot path on application startup."""

    def __init__(self, container: Any) -> None:
        self.container = container
        try:
            self.repository = container.resolve("RecoveryRepository")
            if not self.repository:
                self.repository = RecoveryRepository()
        except Exception:
            self.repository = RecoveryRepository()
        
        # Instantiate recovery subcomponents
        self.db_recovery = DatabaseRecoveryManager(container)
        self.integrity_checker = IntegrityChecker(container)
        self.session_recovery = SessionRecoveryManager(container)
        self.strategy_recovery = StrategyRecoveryManager(container)
        self.portfolio_recovery = PortfolioRecoveryManager(container)
        self.position_recovery = PositionRecoveryManager(container)
        self.scheduler_recovery = SchedulerRecoveryManager(container)
        self.runtime_recovery = RuntimeRecoveryManager(container)

    def execute_recovery(self) -> bool:
        start_time = time.perf_counter()
        session_id = str(uuid.uuid4())
        
        session = RecoverySession(
            session_id=session_id,
            timestamp=datetime.now(timezone.utc),
            status="STARTED",
            stages_executed=[]
        )
        self.repository.log_recovery_session(session)
        logger.info("Starting State Recovery Engine Session: %s...", session_id)

        try:
            # 1. Database Connectivity recovery
            if not self.db_recovery.recover_database():
                raise RuntimeError("Database recovery failed.")
            session.stages_executed.append("Database")

            # 2. Checkpoint recovery
            checkpoint = self.repository.get_latest_checkpoint()
            if not checkpoint:
                logger.info("No checkpoint records found. Starting clean slate.")
                session.status = "SUCCESS"
                session.stages_executed.append("Checkpoint (Clean)")
                session.duration_ms = (time.perf_counter() - start_time) * 1000.0
                self.repository.log_recovery_session(session)
                return True
            session.stages_executed.append("Checkpoint")

            # 3. Integrity verification
            if not self.integrity_checker.validate_integrity(checkpoint):
                # Reject corrupted checkpoint
                try:
                    eb = self.container.resolve("IEventBus")
                    if eb:
                        from research_platform.recovery.events import IntegrityCheckFailed
                        eb.publish("IntegrityCheckFailed", IntegrityCheckFailed(
                            event_id=str(uuid.uuid4()),
                            checkpoint_id=checkpoint.checkpoint_id,
                            reason="Hash mismatch or weights inconsistent"
                        ).model_dump())
                except Exception:
                    pass
                raise ValueError("Checkpoint integrity check failed.")
            session.stages_executed.append("Integrity")

            # Execute actual restorations (4-11)
            self.restore_checkpoint_state(checkpoint)
            
            for stage in ["Configuration", "Scheduler", "Strategies", "Portfolio", "OMS", "Runtime", "Monitoring", "Resume"]:
                session.stages_executed.append(stage)

            session.status = "SUCCESS"
            session.duration_ms = (time.perf_counter() - start_time) * 1000.0
            self.repository.log_recovery_session(session)
            
            # Emit success event
            try:
                eb = self.container.resolve("IEventBus")
                if eb:
                    from research_platform.recovery.events import RecoveryCompleted
                    eb.publish("RecoveryCompleted", RecoveryCompleted(
                        event_id=str(uuid.uuid4()),
                        session_id=session_id,
                        duration_ms=session.duration_ms
                    ).model_dump())
            except Exception:
                pass
                
            return True

        except Exception as e:
            logger.error("State recovery failed: %s", e)
            session.status = "FAILED"
            session.error_message = str(e)
            session.duration_ms = (time.perf_counter() - start_time) * 1000.0
            self.repository.log_recovery_session(session)
            
            # Emit failure event
            try:
                eb = self.container.resolve("IEventBus")
                if eb:
                    from research_platform.recovery.events import RecoveryFailed
                    eb.publish("RecoveryFailed", RecoveryFailed(
                        event_id=str(uuid.uuid4()),
                        session_id=session_id,
                        error_message=str(e)
                    ).model_dump())
            except Exception:
                pass
                
            return False

    def restore_checkpoint_state(self, checkpoint: Checkpoint) -> None:
        """Helper to invoke single restore blocks sequentially."""
        # 4. Configuration restoration
        # (Loaded implicitly from DB)
        
        # 5. Scheduler restoration
        self.scheduler_recovery.restore_scheduler(checkpoint.scheduler_state)
        
        # 6. Strategies restoration
        self.strategy_recovery.restore_strategies(checkpoint.strategies_state)
        
        # 7. Portfolio restoration
        self.portfolio_recovery.restore_portfolio(checkpoint.portfolio_state)
        
        # 8. OMS / Position restoration
        self.position_recovery.restore_positions(checkpoint.positions_state)
        self.session_recovery.restore_session(checkpoint.model_dump())
        
        # 9. Runtime restoration
        self.runtime_recovery.restore_runtime(checkpoint.runtime_state)
        
        # 10. Monitoring / Telemetry restoration
        # (Restored implicitly via metrics update telemetry)
        
        # 11. Resume Trading Loops
        try:
            engine = self.container.resolve("RuntimeEngine")
            if engine and hasattr(engine, "resume"):
                engine.resume()
        except Exception:
            pass
