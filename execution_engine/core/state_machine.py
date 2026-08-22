from typing import Set

from execution_engine.core.enums import IntentState, OrderState
from execution_engine.core.exceptions import InvalidStateTransitionError


class OrderStateMachine:
    """Strict finite state machine enforcing valid transitions on trading orders."""

    # Map of valid transitions: current_state -> set of valid next_states
    _VALID_TRANSITIONS = {
        OrderState.CREATED: {OrderState.VALIDATED, OrderState.REJECTED},
        OrderState.VALIDATED: {OrderState.QUEUED, OrderState.SUBMITTED, OrderState.REJECTED},
        OrderState.QUEUED: {OrderState.SUBMITTED, OrderState.REJECTED, OrderState.CANCELLED, OrderState.EXPIRED},
        OrderState.SUBMITTED: {OrderState.ACKNOWLEDGED, OrderState.REJECTED, OrderState.CANCELLED, OrderState.EXPIRED},
        OrderState.ACKNOWLEDGED: {
            OrderState.PARTIALLY_FILLED,
            OrderState.FILLED,
            OrderState.REJECTED,
            OrderState.CANCELLED,
            OrderState.EXPIRED,
        },
        OrderState.PARTIALLY_FILLED: {
            OrderState.PARTIALLY_FILLED,
            OrderState.FILLED,
            OrderState.CANCELLED,
            OrderState.EXPIRED,
        },
        OrderState.FILLED: set(),
        OrderState.REJECTED: set(),
        OrderState.CANCELLED: set(),
        OrderState.EXPIRED: set(),
    }

    @classmethod
    def validate_transition(cls, from_state: OrderState, to_state: OrderState) -> None:
        """Validate if a transition from from_state to to_state is allowed.

        Raises:
            InvalidStateTransitionError: If the transition is illegal.
        """
        if from_state == to_state:
            # Self-transitions are permitted generally but only PARTIALLY_FILLED -> PARTIALLY_FILLED changes data
            return

        valid_targets = cls._VALID_TRANSITIONS.get(from_state, set())
        if to_state not in valid_targets:
            raise InvalidStateTransitionError(
                f"Illegal order state transition: {from_state.value} -> {to_state.value}."
            )


class IntentStateMachine:
    """Strict finite state machine enforcing valid transitions on OrderIntents.

    The OMS intent lifecycle follows this flow:

        CREATED → VALIDATING → VALIDATED → APPROVED → ROUTING → ROUTED
                                                                  ↓
                                                              EXECUTING → COMPLETED
        Any active state may transition to REJECTED / FAILED / CANCELLED.
        FAILED may transition to RECOVERING → COMPLETED or FAILED.
    """

    _VALID_TRANSITIONS = {
        IntentState.CREATED: {IntentState.VALIDATING, IntentState.REJECTED, IntentState.CANCELLED},
        IntentState.VALIDATING: {IntentState.VALIDATED, IntentState.REJECTED, IntentState.FAILED},
        IntentState.VALIDATED: {IntentState.APPROVED, IntentState.REJECTED, IntentState.CANCELLED},
        IntentState.APPROVED: {IntentState.ROUTING, IntentState.REJECTED, IntentState.CANCELLED},
        IntentState.ROUTING: {IntentState.ROUTED, IntentState.FAILED, IntentState.CANCELLED},
        IntentState.ROUTED: {IntentState.EXECUTING, IntentState.FAILED, IntentState.CANCELLED},
        IntentState.EXECUTING: {IntentState.COMPLETED, IntentState.FAILED, IntentState.CANCELLED},
        IntentState.COMPLETED: set(),
        IntentState.REJECTED: set(),
        IntentState.FAILED: {IntentState.RECOVERING},
        IntentState.CANCELLED: set(),
        IntentState.RECOVERING: {IntentState.COMPLETED, IntentState.FAILED},
    }

    @classmethod
    def validate_transition(cls, from_state: IntentState, to_state: IntentState) -> None:
        """Validate if an intent state transition is allowed.

        Raises:
            InvalidStateTransitionError: If the transition is illegal.
        """
        if from_state == to_state:
            return

        valid_targets = cls._VALID_TRANSITIONS.get(from_state, set())
        if to_state not in valid_targets:
            raise InvalidStateTransitionError(
                f"Illegal intent state transition: {from_state.value} -> {to_state.value}."
            )

    @classmethod
    def get_terminal_states(cls) -> Set[IntentState]:
        """Return the set of terminal (non-transitionable) intent states."""
        return {IntentState.COMPLETED, IntentState.REJECTED, IntentState.CANCELLED}

    @classmethod
    def is_active(cls, state: IntentState) -> bool:
        """Return True if the intent is still in an active (non-terminal) state."""
        return state not in cls.get_terminal_states()

