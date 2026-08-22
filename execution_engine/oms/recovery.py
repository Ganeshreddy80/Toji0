"""OMS Crash Recovery Manager.

Handles reconciliation of in-flight orders after a system restart:
1. Loads persisted intent snapshots from the repository.
2. Queries broker adapters for the actual status of working orders.
3. Transitions intents to their correct states based on broker reality.
4. Emits OMSRecovered once reconciliation is complete.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from execution_engine.brokers.broker_router import BrokerRouter
from execution_engine.core.audit import ExecutionAuditRecord
from execution_engine.core.enums import IntentState, OrderState
from execution_engine.core.events import OMSRecovered
from execution_engine.core.models import OrderIntent
from execution_engine.core.state_machine import IntentStateMachine

logger = logging.getLogger(__name__)


class RecoveryManager:
    """Crash recovery reconciliation for the OMS subsystem.

    After a restart, this manager:
    - Loads all intents that were in active states when the system stopped.
    - Queries the broker for the actual status of their child orders.
    - Reconciles state: completed orders -> COMPLETED, active orders -> resume, lost orders -> FAILED.
    """

    def __init__(
        self,
        broker_router: BrokerRouter,
        event_bus: Any = None,
        execution_repository: Any = None,
    ) -> None:
        self._broker_router = broker_router
        self._event_bus = event_bus
        self._execution_repository = execution_repository

    def reconcile(
        self,
        persisted_intents: List[OrderIntent],
        intent_store: Any,
    ) -> Dict[str, str]:
        """Execute reconciliation on persisted active intents.

        Args:
            persisted_intents: Intents loaded from the persistence layer.
            intent_store: The live IntentStore to update with reconciled states.

        Returns:
            Dict mapping intent_id -> reconciled state value.
        """
        results: Dict[str, str] = {}
        reconciled_count = 0
        failed_count = 0

        logger.info(
            "RecoveryManager: Starting reconciliation of %d persisted intents.",
            len(persisted_intents),
        )

        for intent in persisted_intents:
            if not IntentStateMachine.is_active(intent.state):
                # Already terminal — skip
                results[intent.intent_id] = intent.state.value
                continue

            try:
                new_state = self._reconcile_intent(intent)
                updated = intent.model_copy(update={
                    "state": new_state,
                    "updated_at": datetime.now(timezone.utc),
                })
                intent_store.update_intent(updated)
                results[intent.intent_id] = new_state.value
                reconciled_count += 1

                # Write audit record
                if self._execution_repository:
                    record = ExecutionAuditRecord(
                        execution_id=intent.execution_id,
                        correlation_id=intent.correlation_id,
                        actor="recovery_manager",
                        action="RECONCILE",
                        before={"state": intent.state.value},
                        after={"state": new_state.value},
                        reason="Crash recovery reconciliation.",
                    )
                    self._execution_repository.save_audit_record(record)

                logger.info(
                    "RecoveryManager: Intent %s reconciled: %s → %s",
                    intent.intent_id, intent.state.value, new_state.value,
                )

            except Exception as e:
                logger.error(
                    "RecoveryManager: Failed to reconcile intent %s: %s",
                    intent.intent_id, e,
                )
                failed_count += 1
                results[intent.intent_id] = "RECOVERY_FAILED"

        # Emit recovery completed event
        if self._event_bus:
            try:
                event = OMSRecovered(
                    source="recovery_manager",
                    payload={
                        "reconciled_count": reconciled_count,
                        "failed_count": failed_count,
                        "total_persisted": len(persisted_intents),
                    },
                )
                self._event_bus.publish(event)
            except Exception as e:
                logger.warning("RecoveryManager: Failed to emit OMSRecovered event: %s", e)

        logger.info(
            "RecoveryManager: Reconciliation complete. Reconciled=%d, Failed=%d.",
            reconciled_count, failed_count,
        )
        return results

    def _reconcile_intent(self, intent: OrderIntent) -> IntentState:
        """Reconcile a single intent against broker state.

        For intents in ROUTED or EXECUTING state, we check the broker
        for the status of child orders. For earlier states (CREATED,
        VALIDATING, VALIDATED, APPROVED, ROUTING), we restart them.
        """
        # Intents that never reached the broker can be safely re-tried or cancelled
        pre_broker_states = {
            IntentState.CREATED,
            IntentState.VALIDATING,
            IntentState.VALIDATED,
            IntentState.APPROVED,
            IntentState.ROUTING,
        }

        if intent.state in pre_broker_states:
            # These intents never made it to the broker — mark as cancelled for re-submission
            logger.info(
                "RecoveryManager: Intent %s was pre-broker (state=%s), marking CANCELLED.",
                intent.intent_id, intent.state.value,
            )
            return IntentState.CANCELLED

        # For ROUTED / EXECUTING intents, check broker for child order statuses
        if intent.state in (IntentState.ROUTED, IntentState.EXECUTING):
            return self._check_broker_orders(intent)

        # RECOVERING state — attempt completion
        if intent.state == IntentState.RECOVERING:
            return self._check_broker_orders(intent)

        # FAILED — transition to RECOVERING for retry
        if intent.state == IntentState.FAILED:
            return IntentState.RECOVERING

        return intent.state

    def _check_broker_orders(self, intent: OrderIntent) -> IntentState:
        """Query the broker for the status of child orders.

        If all child orders are filled → COMPLETED.
        If any orders are still active → keep EXECUTING.
        If orders are rejected/cancelled → FAILED.
        """
        if not intent.child_order_ids:
            # No child orders generated — mark as failed
            return IntentState.FAILED

        try:
            adapter = self._broker_router.get_adapter("paper")

            all_filled = True
            any_active = False

            for order_id in intent.child_order_ids:
                try:
                    broker_order = adapter.get_order(order_id)
                    if broker_order.state == OrderState.FILLED:
                        continue
                    elif broker_order.state in (
                        OrderState.CREATED, OrderState.QUEUED,
                        OrderState.SUBMITTED, OrderState.ACKNOWLEDGED,
                        OrderState.PARTIALLY_FILLED,
                    ):
                        any_active = True
                        all_filled = False
                    else:
                        all_filled = False
                except Exception:
                    # Can't find the order — assume it's gone
                    all_filled = False

            if all_filled:
                return IntentState.COMPLETED
            elif any_active:
                return IntentState.EXECUTING
            else:
                return IntentState.FAILED

        except Exception as e:
            logger.error(
                "RecoveryManager: Broker query failed for intent %s: %s",
                intent.intent_id, e,
            )
            return IntentState.FAILED
