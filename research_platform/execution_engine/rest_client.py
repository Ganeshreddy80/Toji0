"""REST Client simulating authentication checks and request signings.
"""

from __future__ import annotations

import hashlib
import hmac
import urllib.parse
from typing import Any, Dict


class RestClient:
    """Handles API requests, signature hashing, and endpoint parameters format."""

    def __init__(self, api_key: str, api_secret: str) -> None:
        self.api_key = api_key
        self.api_secret = api_secret.encode("utf-8")

    def sign_request(self, params: Dict[str, Any]) -> str:
        """Create HMAC-SHA256 signature for parameters."""
        query_str = urllib.parse.urlencode(sorted(params.items()))
        signature = hmac.new(
            self.api_secret,
            query_str.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        return signature
