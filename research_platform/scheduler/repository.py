"""Strategy scheduler repository with PostgreSQL delegation and memory fallbacks.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional
from research_platform.scheduler.interfaces import IJobRepository
from research_platform.scheduler.models import ExecutionJob, ExecutionHistoryCard
from research_platform.platform.service_registry import ServiceRegistry
from research_platform.persistence.repositories.scheduler_repository import PostgresJobRepository


class JobRepository(IJobRepository):
    """Memory-backed job repository with PostgreSQL delegation capabilities."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: Dict[str, ExecutionJob] = {}
        self._histories: Dict[str, List[ExecutionHistoryCard]] = {}

    def _get_pg_repo(self) -> Optional[PostgresJobRepository]:
        registry = ServiceRegistry()
        db = registry.get_service("Database")
        if db:
            from research_platform.persistence.postgres.session import DatabaseSessionManager
            session_manager = DatabaseSessionManager(db)
            return PostgresJobRepository(session_manager)
        return None

    def save_job(self, job: ExecutionJob) -> None:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            pg_repo.save_job(job)
            
        with self._lock:
            self._jobs[job.job_id] = job

    def get_job(self, job_id: str) -> Optional[ExecutionJob]:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            return pg_repo.get_job(job_id)
            
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self) -> List[ExecutionJob]:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            return pg_repo.list_jobs()
            
        with self._lock:
            return list(self._jobs.values())

    def save_history(self, card: ExecutionHistoryCard) -> None:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            pg_repo.save_history(card)
            
        with self._lock:
            j_id = card.job_id
            if j_id not in self._histories:
                self._histories[j_id] = []
            self._histories[j_id].append(card)

    def get_history(self, job_id: str) -> List[ExecutionHistoryCard]:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            return pg_repo.get_history(job_id)
            
        with self._lock:
            return list(self._histories.get(job_id, []))
