import pytest

from execution_engine.core.enums import OrderState
from execution_engine.core.exceptions import InvalidStateTransitionError
from execution_engine.core.state_machine import OrderStateMachine


def test_valid_state_transitions():
    # Should compile without exception
    OrderStateMachine.validate_transition(OrderState.CREATED, OrderState.VALIDATED)
    OrderStateMachine.validate_transition(OrderState.VALIDATED, OrderState.QUEUED)
    OrderStateMachine.validate_transition(OrderState.QUEUED, OrderState.SUBMITTED)
    OrderStateMachine.validate_transition(OrderState.SUBMITTED, OrderState.ACKNOWLEDGED)
    OrderStateMachine.validate_transition(OrderState.ACKNOWLEDGED, OrderState.FILLED)


def test_invalid_state_transitions():
    # CREATED cannot jump directly to FILLED
    with pytest.raises(InvalidStateTransitionError):
        OrderStateMachine.validate_transition(OrderState.CREATED, OrderState.FILLED)

    # FILLED is terminal, cannot transition back to SUBMITTED
    with pytest.raises(InvalidStateTransitionError):
        OrderStateMachine.validate_transition(OrderState.FILLED, OrderState.SUBMITTED)
        
    # ACKNOWLEDGED cannot transition back to CREATED
    with pytest.raises(InvalidStateTransitionError):
        OrderStateMachine.validate_transition(OrderState.ACKNOWLEDGED, OrderState.CREATED)
