class ExecutionEngineError(Exception):
    """Base exception for all Execution Engine failures."""
    pass


class ValidationError(ExecutionEngineError):
    """Exception raised when an execution request or order fails pre-trade checks."""
    pass


class BrokerError(ExecutionEngineError):
    """Exception raised when an external broker or exchange operation fails."""
    pass


class InvalidStateTransitionError(ExecutionEngineError):
    """Exception raised when an order state transition violates the state machine rules."""
    pass


class OrchestratorError(ExecutionEngineError):
    """Exception raised when orchestrator workflow coordination fails."""
    pass


class RepositoryError(ExecutionEngineError):
    """Exception raised when database persistence fails."""
    pass


class IdempotencyError(ExecutionEngineError):
    """Exception raised when a duplicate execution request is detected."""
    pass
