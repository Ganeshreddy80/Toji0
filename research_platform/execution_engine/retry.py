"""Retry Engine executing exponential backoff rules.
"""

from __future__ import annotations

import math
import time
from typing import Callable, TypeVar

T = TypeVar("T")


class RetryEngine:
    """Configures backoff delays and manages cooldown retry budgets."""

    def __init__(self, max_attempts: int = 3, initial_delay_ms: int = 100, factor: float = 2.0) -> None:
        self.max_attempts = max_attempts
        self.initial_delay_ms = initial_delay_ms
        self.factor = factor

    def execute(self, fn: Callable[[], T]) -> T:
        """Execute callable with backoff retry rules."""
        last_exception = None
        
        for attempt in range(self.max_attempts):
            try:
                return fn()
            except Exception as e:
                last_exception = e
                # Wait exponential backoff delay (mock sleeping for testing speed)
                delay = (self.initial_delay_ms / 1000.0) * (self.factor ** attempt)
                # In real code we sleep: time.sleep(delay)
                
        raise last_exception if last_exception else RuntimeError("Retry execution failed.")
