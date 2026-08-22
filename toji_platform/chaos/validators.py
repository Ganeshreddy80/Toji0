"""Chaos validation and guard rails."""

import os

def is_chaos_permitted() -> bool:
    """Chaos injection is ONLY permitted if TOJI_CHAOS_ENABLED is set to 'true' or '1'."""
    val = os.getenv("TOJI_CHAOS_ENABLED", "").lower()
    return val in ("true", "1")
