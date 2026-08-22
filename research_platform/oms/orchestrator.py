"""Order Management System Orchestrator compatibility subclass.
"""

from __future__ import annotations

from research_platform.oms.oms_core import OmsCore

class OrderManagementSystemOrchestrator(OmsCore):
    """Compatibility wrapper that inherits from OmsCore to prevent type collisions."""
    pass
