"""Rate Limiter implementing token-bucket limits.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone


class TokenBucketRateLimiter:
    """Limits request frequencies to exchange endpoints, supporting burst allowance."""

    def __init__(self, capacity: float = 100.0, refill_rate: float = 10.0) -> None:
        """Initialize Token Bucket.

        refill_rate: number of tokens refilled per second.
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self._last_refill = time.time()

    def allow_request(self) -> bool:
        """Evaluate if bucket has enough tokens. Consumes 1 token if True."""
        self._refill()
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False

    def _refill(self) -> None:
        now = time.time()
        elapsed = now - self._last_refill
        self._last_refill = now
        
        refill_amt = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + refill_amt)
