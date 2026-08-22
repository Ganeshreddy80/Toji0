"""TOJI Intelligence Layer.

Provides real-time decision support, universe management, scanning,
market pulse calculations, regime detection, timing windows, strategy eligibility filters,
alpha decay trackers, capital suggestions, alerts, and analytical reports.
"""

from __future__ import annotations

__version__ = "0.1.0"
__package_name__ = "toji-intelligence"

from intelligence.models import (
    Alert,
    AlertLevel,
    MarketPulse,
    Opportunity,
    RiskGrade,
)
from intelligence.universe.manager import UniverseManager
from intelligence.market_pulse.pulse import MarketPulseGenerator
from intelligence.regime.engine import RegimeEngine
from intelligence.timing.engine import TimingEngine
from intelligence.opportunities.engine import OpportunityEngine
from intelligence.asset_health.calculator import AssetHealthCalculator
from intelligence.eligibility.evaluator import (
    StrategyEligibilityConstraints,
    StrategyEligibilityEvaluator,
)
from intelligence.alpha_decay.tracker import AlphaDecayTracker
from intelligence.capital.allocator import CapitalAllocator, SizingSuggestion
from intelligence.alerts.manager import AlertManager
from intelligence.reports.generator import IntelligenceReportGenerator
from intelligence.scanner.scanner import Scanner

__all__ = [
    "Alert",
    "AlertLevel",
    "MarketPulse",
    "Opportunity",
    "RiskGrade",
    "UniverseManager",
    "MarketPulseGenerator",
    "RegimeEngine",
    "TimingEngine",
    "OpportunityEngine",
    "AssetHealthCalculator",
    "StrategyEligibilityConstraints",
    "StrategyEligibilityEvaluator",
    "AlphaDecayTracker",
    "CapitalAllocator",
    "SizingSuggestion",
    "AlertManager",
    "IntelligenceReportGenerator",
    "Scanner",
]
