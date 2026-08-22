"""PostgreSQL strategy scheduler repository.
"""

from __future__ import annotations

from typing import List, Optional

from research_platform.persistence.postgres.base_repository import BaseRepository
from research_platform.persistence.postgres.migrations import JobModel
from research_platform.scheduler.models import ExecutionJob, ExecutionHistoryCard


class PostgresJobRepository(BaseRepository):
    """PostgreSQL-backed Job repository implementation."""

    def __init__(self, session_manager) -> None:
        super().__init__(session_manager, JobModel)
        self._histories: dict[str, List[str]] = {}

    def save_job(self, job: ExecutionJob) -> None:
        model = self.get(job.job_id)
        if model:
            updates = {
                "name": job.name,
                "task_type": job.task_type,
                "schedule_expr": job.schedule_expr,
                "priority": job.priority,
                "status": job.status
            }
            self.update(job.job_id, updates)
        else:
            new_model = JobModel(
                job_id=job.job_id,
                name=job.name,
                task_type=job.task_type,
                schedule_expr=job.schedule_expr,
                priority=job.priority,
                status=job.status
            )
            self.create(new_model)

    def get_job(self, job_id: str) -> Optional[ExecutionJob]:
        model = self.get(job_id)
        if model:
            return ExecutionJob(
                job_id=model.job_id,
                name=model.name,
                task_type=model.task_type,
                schedule_expr=model.schedule_expr,
                priority=model.priority,
                status=model.status
            )
        return None

    def list_jobs(self) -> List[ExecutionJob]:
        models = self.list_all()
        return [
            ExecutionJob(
                job_id=m.job_id,
                name=m.name,
                task_type=m.task_type,
                schedule_expr=m.schedule_expr,
                priority=m.priority,
                status=m.status
            )
            for m in models
        ]

    def save_history(self, card: ExecutionHistoryCard) -> None:
        j_id = card.job_id
        if j_id not in self._histories:
            self._histories[j_id] = []
        self._histories[j_id].append(card.model_dump_json())

    def get_history(self, job_id: str) -> List[ExecutionHistoryCard]:
        data = self._histories.get(job_id, [])
        return [ExecutionHistoryCard.model_validate_json(d) for d in data]
