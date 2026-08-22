"""Contradiction engine for identifying conflicts in rules, beliefs, and statistics."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
import numpy as np
from pydantic import BaseModel, Field
from knowledge.models import Rule, Belief, Evidence


class InvestigationTask(BaseModel):
    """A diagnostic task created when the contradiction engine detects conflicting nodes."""

    task_id: str = Field(...)
    contradiction_type: str = Field(...)
    description: str = Field(...)
    offending_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"frozen": True}


class ContradictionEngine:
    """Detects logical inconsistencies across the knowledge graph and schedules investigations."""

    def __init__(self) -> None:
        self.tasks: list[InvestigationTask] = []

    def detect_rule_conflicts(self, rules: list[Rule]) -> list[InvestigationTask]:
        """Detect conflicting strategies rules.
        
        Identifies rules that share identical conditional expressions but have different weights or logic.
        """
        new_tasks = []
        # Group by expression to find exact condition duplicates with differing metadata
        by_expr: dict[str, list[Rule]] = {}
        for r in rules:
            by_expr.setdefault(r.expression, []).append(r)
            
        for expr, matches in by_expr.items():
            if len(matches) > 1:
                # Potential duplication or weight conflict
                ids = [m.rule_id for m in matches]
                desc = (
                    f"Conflicting rules found sharing identical expression: '{expr}'. "
                    f"Rules: {', '.join(m.name for m in matches)}."
                )
                task = InvestigationTask(
                    task_id=str(uuid.uuid4()),
                    contradiction_type="rule_conflict",
                    description=desc,
                    offending_ids=ids,
                    created_at=datetime.now(timezone.utc)
                )
                new_tasks.append(task)
                self.tasks.append(task)
                
        return new_tasks

    def detect_belief_conflicts(self, beliefs: list[Belief]) -> list[InvestigationTask]:
        """Detect conflicting active beliefs.
        
        Checks for declared conflicts and semantic opposites (e.g. 'Asset X is bullish' vs 'Asset X is bearish').
        """
        new_tasks = []
        n = len(beliefs)
        
        # 1. Declared conflicts check
        for b in beliefs:
            if b.conflicting_belief_ids:
                for c_id in b.conflicting_belief_ids:
                    # Avoid double creating tasks (A-B and B-A)
                    existing = [t for t in new_tasks if b.belief_id in t.offending_ids and c_id in t.offending_ids]
                    if not existing:
                        desc = f"Declared conflict between beliefs: '{b.claim}' and conflicting belief node."
                        task = InvestigationTask(
                            task_id=str(uuid.uuid4()),
                            contradiction_type="belief_conflict",
                            description=desc,
                            offending_ids=[b.belief_id, c_id],
                            created_at=datetime.now(timezone.utc)
                        )
                        new_tasks.append(task)
                        self.tasks.append(task)
                        
        # 2. Semantic opposites heuristic (e.g. sharing target asset but claiming opposites)
        for i in range(n):
            for j in range(i + 1, n):
                b1 = beliefs[i]
                b2 = beliefs[j]
                
                # Check if they reference the same words but differ in direction (e.g. bullish vs bearish)
                words1 = set(b1.claim.lower().split())
                words2 = set(b2.claim.lower().split())
                
                # If they share almost all context words but swap bullish/bearish, buy/sell
                common = words1.intersection(words2)
                if len(common) > 1:
                    has_opposite = (
                        ("bullish" in words1 and "bearish" in words2) or
                        ("bearish" in words1 and "bullish" in words2) or
                        ("buy" in words1 and "sell" in words2) or
                        ("sell" in words1 and "buy" in words2)
                    )
                    if has_opposite:
                        existing = [t for t in new_tasks if b1.belief_id in t.offending_ids and b2.belief_id in t.offending_ids]
                        if not existing:
                            desc = f"Semantic contradiction identified: '{b1.claim}' vs '{b2.claim}'."
                            task = InvestigationTask(
                                task_id=str(uuid.uuid4()),
                                contradiction_type="belief_conflict",
                                description=desc,
                                offending_ids=[b1.belief_id, b2.belief_id],
                                created_at=datetime.now(timezone.utc)
                            )
                            new_tasks.append(task)
                            self.tasks.append(task)
                            
        return new_tasks

    def detect_statistics_conflicts(self, evidence_list: list[Evidence]) -> list[InvestigationTask]:
        """Detect conflicting statistics across different evidence entries.
        
        Flags cases where the same experiment run claims different values for the same metric.
        """
        new_tasks = []
        # Group by (source_ref_id, metric_name)
        grouped: dict[tuple[str, str], list[Evidence]] = {}
        for e in evidence_list:
            key = (e.source.ref_id, e.metric_name)
            grouped.setdefault(key, []).append(e)
            
        for (ref_id, metric), matches in grouped.items():
            if len(matches) > 1:
                # Check variance in values
                values = [m.metric_value for m in matches]
                variance = float(np.var(values))
                if variance > 1e-4:  # Significant statistical variance
                    ids = [m.evidence_id for m in matches]
                    desc = (
                        f"Statistical conflict detected for metric '{metric}' on source '{ref_id}'. "
                        f"Observed discrepant values: {values} (variance={variance:.6f})."
                    )
                    task = InvestigationTask(
                        task_id=str(uuid.uuid4()),
                        contradiction_type="statistics_conflict",
                        description=desc,
                        offending_ids=ids,
                        created_at=datetime.now(timezone.utc)
                    )
                    new_tasks.append(task)
                    self.tasks.append(task)
                    
        return new_tasks
