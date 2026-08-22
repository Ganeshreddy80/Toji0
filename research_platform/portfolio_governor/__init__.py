"""Portfolio Governor — institutional-grade pre-execution gate.

Prevents overtrading by enforcing:
  - Duplicate position checks
  - Portfolio exposure limits
  - Per-symbol trade cooldowns
"""

from research_platform.portfolio_governor.governor import PortfolioGovernor
from research_platform.portfolio_governor.models import GovernedPosition, PortfolioDecision

__all__ = ["PortfolioGovernor", "GovernedPosition", "PortfolioDecision"]
