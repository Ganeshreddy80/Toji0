"""Database repository saving risk evaluations and alerts history.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional

from research_platform.risk_management.interfaces import IRiskRepository
from research_platform.risk_management.models import RiskAlert, RiskEvaluation


class RiskRepository(IRiskRepository):
    """Memory database repository for risk evaluations."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._evaluations: Dict[str, RiskEvaluation] = {}
        self._alerts: Dict[str, RiskAlert] = {}

    def save_evaluation(self, evaluation: RiskEvaluation) -> None:
        with self._lock:
            self._evaluations[evaluation.evaluation_id] = evaluation

    def get_evaluation(self, evaluation_id: str) -> Optional[RiskEvaluation]:
        with self._lock:
            return self._evaluations.get(evaluation_id)

    def save_alert(self, alert: RiskAlert) -> None:
        with self._lock:
            self._alerts[alert.alert_id] = alert

    def get_alert(self, alert_id: str) -> Optional[RiskAlert]:
        with self._lock:
            return self._alerts.get(alert_id)

    def list_alerts(self) -> List[RiskAlert]:
        with self._lock:
            return list(self._alerts.values())
