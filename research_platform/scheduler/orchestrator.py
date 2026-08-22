"""Strategy Scheduler orchestrator coordinating priorities, executors, and retry backoffs.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any, List, Dict, Optional

from toji_platform.core.event_bus import IEventBus

from research_platform.scheduler.interfaces import ISchedulerEngine
from research_platform.scheduler.models import ExecutionJob, ExecutionHistoryCard, PriorityQueueCard
from research_platform.scheduler.repository import JobRepository
from research_platform.scheduler.scheduler_engine import SchedulerEngine
from research_platform.scheduler.job_executor import JobExecutor
from research_platform.scheduler.calendar_engine import CalendarEngine
from research_platform.scheduler.retry_engine import RetryEngine
from research_platform.scheduler.events import (
    JobScheduled,
    JobStarted,
    JobCompleted,
    JobFailed,
    JobCanceled,
)

logger = logging.getLogger(__name__)


class StrategySchedulerOrchestrator(ISchedulerEngine):
    """Central orchestrator managing cron execution schedules."""

    def __init__(self, event_bus: IEventBus, container: Optional[Any] = None) -> None:
        self._event_bus = event_bus
        self._container = container
        
        self._repo = JobRepository()
        self._engine = SchedulerEngine()
        self._executor = JobExecutor()
        self._calendar = CalendarEngine()
        self._retry = RetryEngine()

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._callbacks: Dict[str, Any] = {}

    @property
    def repository(self) -> JobRepository:
        return self._repo

    @property
    def job_executor(self) -> JobExecutor:
        return self._executor

    @property
    def calendar_engine(self) -> CalendarEngine:
        return self._calendar

    @property
    def retry_engine(self) -> RetryEngine:
        return self._retry

    # ── Downstream Subsystem Resolvers ───────────────────────────────

    def _resolve(self, key: str) -> Optional[Any]:
        if self._container and self._container.has(key):
            try:
                return self._container.resolve(key)
            except Exception as e:
                logger.error("StrategyScheduler: Failed to resolve registry key %s: %s", key, e)
        return None

    def _get_memory_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator")

    def _get_kg_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator")

    def _get_ops_orchestrator(self) -> Optional[Any]:
        return self._resolve("research_platform.operations_center.operations_orchestrator.OperationsOrchestrator")

    # ── ISchedulerEngine Action ──────────────────────────────────────

    def schedule_job(
        self,
        job_id: str,
        name: str,
        task_type: str,
        schedule_expr: str,
        priority: int
    ) -> ExecutionJob:
        """Enqueue task job verifying parameters formatting."""
        job = self._engine.initiate_job(
            job_id=job_id,
            name=name,
            task_type=task_type,
            schedule_expr=schedule_expr,
            priority=priority
        )
        self._repo.save_job(job)

        self._event_bus.publish(JobScheduled(payload={"job_id": job_id}))
        self._log_downstream_registries(job, "Job Scheduled")

        return job

    def run_job(self, job_id: str, callback: Any = None) -> ExecutionHistoryCard:
        job = self._repo.get_job(job_id)
        if not job:
            raise ValueError(f"Job '{job_id}' not found.")

        # Update status to RUNNING
        running = job.model_copy(update={"status": "RUNNING", "last_run": datetime.now(timezone.utc)})
        self._repo.save_job(running)
        
        self._event_bus.publish(JobStarted(payload={"job_id": job_id}))

        # Execute
        card = self._executor.execute(job_id, callback)
        self._repo.save_history(card)

        if card.status == "COMPLETED":
            completed = running.model_copy(update={"status": "COMPLETED"})
            self._repo.save_job(completed)
            self._event_bus.publish(JobCompleted(payload={"job_id": job_id}))
            self._log_downstream_registries(completed, "Job Executed Successfully")
        else:
            # Check retries
            if self._retry.evaluate_retry(running):
                failed = running.model_copy(update={
                    "status": "PENDING",
                    "retries_left": running.retries_left - 1
                })
                self._repo.save_job(failed)
                self._event_bus.publish(JobFailed(payload={"job_id": job_id, "error": card.error_message}))
                self._log_downstream_registries(failed, f"Job Run Failed: Retrying ({failed.retries_left} left)")
            else:
                failed = running.model_copy(update={"status": "FAILED"})
                self._repo.save_job(failed)
                self._event_bus.publish(JobFailed(payload={"job_id": job_id, "error": card.error_message}))
                self._log_downstream_registries(failed, f"Job Run Failed: Exhausted Retries ({card.error_message})")

        return card

    def cancel_job(self, job_id: str) -> ExecutionJob:
        job = self._repo.get_job(job_id)
        if not job:
            raise ValueError(f"Job '{job_id}' not found.")

        canceled = job.model_copy(update={"status": "CANCELED"})
        self._repo.save_job(canceled)
        self._event_bus.publish(JobCanceled(payload={"job_id": job_id}))
        self._log_downstream_registries(canceled, "Job Canceled")
        return canceled

    def list_queued_jobs(self) -> List[ExecutionJob]:
        # Priority sort descending
        jobs = [j for j in self._repo.list_jobs() if j.status in ["PENDING", "RUNNING"]]
        jobs.sort(key=lambda x: x.priority, reverse=True)
        return jobs

    def get_priority_queue_stats(self) -> PriorityQueueCard:
        jobs = self.list_queued_jobs()
        return PriorityQueueCard(
            queue_name="MAIN_EXECUTION_QUEUE",
            jobs_count=len(jobs)
        )

    def _log_downstream_registries(self, job: ExecutionJob, message: str) -> None:
        # 1. Institutional Memory (R16)
        mem = self._get_memory_orchestrator()
        if mem:
            try:
                mem.publish_memory("observability", {
                    "job_id": job.job_id,
                    "status": job.status,
                    "message": message
                })
            except Exception as e:
                logger.error("StrategyScheduler Audit: Failed to write to memory: %s", e)

        # 2. Knowledge Graph (R17)
        kg = self._get_kg_orchestrator()
        if kg:
            try:
                kg.register_node(
                    node_id=job.job_id,
                    node_type="JOB",
                    subsystem="scheduler",
                    event="JobScheduled",
                    author="scheduler",
                    properties={"status": job.status, "priority": job.priority}
                )
            except Exception as e:
                logger.error("StrategyScheduler Audit: Failed to write to graph: %s", e)

        # 3. Operations Center (R30.5)
        ops = self._get_ops_orchestrator()
        if ops:
            try:
                ops.compile_dashboard_snapshot()
            except Exception as e:
                logger.error("StrategyScheduler: Failed to refresh operations center: %s", e)

    # ── Daemon / Loop Methods for R56 ───────────────────────────────

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="StrategySchedulerOrchestrator")
        self._thread.start()
        logger.info("StrategySchedulerOrchestrator daemon started.")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        logger.info("StrategySchedulerOrchestrator daemon stopped.")

    def register_callback(self, task_type: str, callback: Any) -> None:
        self._callbacks[task_type] = callback

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._run_due_jobs()
            except Exception as e:
                logger.error("Error in scheduler loop run: %s", e)
            self._stop_event.wait(5.0)

    def _run_due_jobs(self) -> None:
        now = datetime.now(timezone.utc)
        jobs = [j for j in self._repo.list_jobs() if j.status == "PENDING"]
        for job in jobs:
            if self._calendar.is_due(job, now):
                callback = self._callbacks.get(job.task_type) or self._callbacks.get(job.name)
                logger.info("Running scheduled job '%s' (%s)", job.name, job.job_id)
                self.run_job(job.job_id, callback)
