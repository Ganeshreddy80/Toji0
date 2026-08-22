from __future__ import annotations

import logging
import time
from typing import Any, Callable, Type, Dict

from execution_engine.core.exceptions import BrokerError, ValidationError

logger = logging.getLogger(__name__)


class RetryManager:
    """Manages retry loops and backoff delays for transient errors."""

    def __init__(self, policy: Dict[str, Any]) -> None:
        self._max_retries = int(policy.get("max_retries", 3))
        self._backoff_multiplier = float(policy.get("backoff_multiplier", 2.0))
        self._initial_delay_sec = float(policy.get("initial_delay_seconds", 0.5))

    def is_recoverable(self, exception: Exception) -> bool:
        """Evaluate if the raised exception is a transient error.

        Terminal errors (like Validation or missing attributes) should fail immediately.
        """
        if isinstance(exception, ValidationError):
            return False

        err_msg = str(exception).lower()
        terminal_keywords = ["insufficient balance", "invalid symbol", "balance deficit", "precision violation", "min notional"]
        for keyword in terminal_keywords:
            if keyword in err_msg:
                return False

        # Broker connection timeouts/network interruptions are recoverable
        if isinstance(exception, BrokerError) or "timeout" in err_msg or "connection" in err_msg:
            return True

        return False

    def execute_with_retry(self, operation: Callable[[], Any]) -> Any:
        """Run the callable task, executing retry attempts with exponential backoff on transient errors."""
        retries = 0
        delay = self._initial_delay_sec

        while True:
            try:
                return operation()
            except Exception as e:
                retries += 1
                if not self.is_recoverable(e) or retries > self._max_retries:
                    logger.error("RetryManager: Operation failed terminally. Error: %s", e)
                    raise

                logger.warning(
                    "RetryManager: Transient error detected: %s. Retrying attempt %d/%d in %.2fs...",
                    e,
                    retries,
                    self._max_retries,
                    delay,
                )
                time.sleep(delay)
                delay *= self._backoff_multiplier
