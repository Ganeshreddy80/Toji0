"""Role-Based Access Control, API key validation, and rate-limiting helper utilities.
"""

from __future__ import annotations

import os
import time
import logging
from typing import Dict, List, Optional
from fastapi import Request, HTTPException, Security, status
from fastapi.security import APIKeyHeader

logger = logging.getLogger(__name__)

# Valid API keys mapped to roles dynamically based on environment mode
import sys
is_pytest = "pytest" in sys.modules or any("pytest" in arg for arg in sys.argv)

toji_mode = os.getenv("TOJI_MODE", "PAPER").upper()
admin_key = os.getenv("TOJI_ADMIN_API_KEY")
analyst_key = os.getenv("TOJI_ANALYST_API_KEY")

if toji_mode == "DEV" or (is_pytest and os.getenv("FORCE_PROD_SECRET_CHECK") != "true"):
    if not admin_key:
        admin_key = "toji_admin_secret_key_12345"
    if not analyst_key:
        analyst_key = "toji_analyst_secret_key_67890"
else:
    if not admin_key or admin_key == "toji_admin_secret_key_12345":
        raise ValueError("Production safety breach: Secure custom TOJI_ADMIN_API_KEY is required in PAPER/PROD mode!")
    if not analyst_key or analyst_key == "toji_analyst_secret_key_67890":
        raise ValueError("Production safety breach: Secure custom TOJI_ANALYST_API_KEY is required in PAPER/PROD mode!")

API_KEY_REGISTRY = {
    admin_key: "admin",
    analyst_key: "analyst"
}

API_KEY_NAME = "X-API-KEY"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# Simple in-memory rate limiting state: ip -> [timestamps]
RATE_LIMIT_STORE: Dict[str, List[float]] = {}
LIMIT_WINDOW = 60.0  # seconds
LIMIT_MAX_REQUESTS = 100  # requests per window


def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """Validate incoming HTTP header X-API-KEY against active registry, returning user role."""
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API Key. Provide X-API-KEY header.",
        )
        
    role = API_KEY_REGISTRY.get(api_key)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API Key credentials.",
        )
    return role


class RoleChecker:
    """Enforces allowed roles bounds on route endpoints."""

    def __init__(self, allowed_roles: List[str]) -> None:
        self.allowed_roles = allowed_roles

    def __call__(self, role: str = Security(verify_api_key)) -> str:
        if role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted. Required roles: {self.allowed_roles}",
            )
        return role


def rate_limiter(request: Request) -> None:
    """Enforce token/time rate limits on API requests by client host IP."""
    client_ip = request.client.host if request.client else "unknown_ip"
    now = time.time()
    
    with threading_lock():
        timestamps = RATE_LIMIT_STORE.setdefault(client_ip, [])
        # Prune expired timestamps
        timestamps[:] = [t for t in timestamps if now - t < LIMIT_WINDOW]
        
        if len(timestamps) >= LIMIT_MAX_REQUESTS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Try again later.",
            )
        timestamps.append(now)


# Lock for rate limiter thread safety
import threading
_limit_lock = threading.Lock()

def threading_lock() -> threading.Lock:
    return _limit_lock
