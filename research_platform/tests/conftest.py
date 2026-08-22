"""Pytest configuration and global fixtures.
"""

from __future__ import annotations

import pytest
from research_platform.platform.service_registry import ServiceRegistry


@pytest.fixture(autouse=True)
def clean_service_registry():
    """Clear the global ServiceRegistry singleton before every test to prevent test pollution."""
    ServiceRegistry().clear()
