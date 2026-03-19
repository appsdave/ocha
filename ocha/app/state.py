from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import StrEnum


class WorkerStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"
    QUEUED = "queued"


class WorkerRole(StrEnum):
    COORDINATOR = "coordinator"
    LEAD = "lead"
    BUILDER = "builder"
    REVIEWER = "reviewer"


class OutputMode(StrEnum):
    WORKFLOW = "workflow"
    RAW = "raw"


STATUS_PRIORITY = {
    WorkerStatus.RUNNING: 0,
    WorkerStatus.FAILED: 1,
    WorkerStatus.QUEUED: 2,
    WorkerStatus.COMPLETED: 3,
    WorkerStatus.STOPPED: 4,
}


@dataclass(slots=True)
class WorkerSession:
    session_id: str
    task_id: str
    title: str
    role: WorkerRole
    status: WorkerStatus
    branch: str
    worktree_path: str
    owned_directory: str
    summary: str
    workflow_log: list[str] = field(default_factory=list)
    raw_log: list[str] = field(default_factory=list)
    task_prompt: str = ""
    role_prompt_path: str = ""
    latest_event: str = ""
    retry_count: int = 0
    started_at: datetime = field(default_factory=datetime.now)
    finished_at: datetime | None = None

    @property
    def elapsed(self) -> str:
        end = self.finished_at or datetime.now()
        duration = end - self.started_at
        total_seconds = max(0, int(duration.total_seconds()))
        minutes, seconds = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}h {minutes}m"
        if minutes:
            return f"{minutes}m {seconds}s"
        return f"{seconds}s"


@dataclass(slots=True)
class OchaTask:
    task_id: str
    title: str
    user_task: str
    branch: str
    workers: list[WorkerSession] = field(default_factory=list)

    @property
    def status(self) -> WorkerStatus:
        return min((worker.status for worker in self.workers), key=STATUS_PRIORITY.__getitem__)

    @property
    def started_at(self) -> datetime:
        return min(worker.started_at for worker in self.workers)

    @property
    def finished_at(self) -> datetime | None:
        if any(worker.finished_at is None for worker in self.workers):
            return None
        return max(worker.finished_at for worker in self.workers if worker.finished_at is not None)

    @property
    def elapsed(self) -> str:
        end = self.finished_at or datetime.now()
        duration = end - self.started_at
        total_seconds = max(0, int(duration.total_seconds()))
        minutes, seconds = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}h {minutes}m"
        if minutes:
            return f"{minutes}m {seconds}s"
        return f"{seconds}s"

    @property
    def latest_event(self) -> str:
        for worker in reversed(self.workers):
            if worker.latest_event:
                return worker.latest_event
        return ""

    @property
    def summary(self) -> str:
        active = self.primary_worker
        return active.summary if active else "No worker summary yet."

    @property
    def primary_worker(self) -> WorkerSession:
        return min(self.workers, key=lambda worker: (STATUS_PRIORITY[worker.status], worker.role.value))

    @property
    def pipeline_summary(self) -> str:
        return "   ".join(
            f"{worker.role} {worker.status.value}"
            for worker in sorted(self.workers, key=lambda worker: worker.role.value)
        )

    def output_lines(self, mode: OutputMode) -> list[str]:
        lines: list[str] = []
        for worker in self.workers:
            source_lines = worker.workflow_log if mode == OutputMode.WORKFLOW else worker.raw_log
            for line in source_lines:
                lines.append(f"[{worker.role}] {line}")
        return lines


@dataclass(slots=True)
class AppState:
    tasks: list[OchaTask]
    selected_index: int = 0
    output_mode: OutputMode = OutputMode.WORKFLOW

    @property
    def workers(self) -> list[WorkerSession]:
        return [worker for task in self.tasks for worker in task.workers]

    @property
    def has_tasks(self) -> bool:
        return bool(self.tasks)

    @property
    def selected_task(self) -> OchaTask | None:
        if not self.tasks:
            return None
        return self.tasks[self.selected_index]

    @property
    def selected_worker(self) -> WorkerSession | None:
        task = self.selected_task
        return task.primary_worker if task else None

    @property
    def status_counts(self) -> dict[WorkerStatus, int]:
        return {status: sum(task.status == status for task in self.tasks) for status in WorkerStatus}

    @property
    def next_task_number(self) -> int:
        task_numbers = [int(task.task_id.split("-")[-1]) for task in self.tasks if task.task_id.startswith("T-")]
        return (max(task_numbers) + 1) if task_numbers else 1


TERMINAL_TASK_STATUSES = {
    WorkerStatus.COMPLETED,
    WorkerStatus.FAILED,
    WorkerStatus.STOPPED,
}


def clear_finished_tasks(state: AppState) -> AppState:
    remaining_tasks = [task for task in state.tasks if task.status not in TERMINAL_TASK_STATUSES]
    if len(remaining_tasks) == len(state.tasks):
        return state
    next_index = min(state.selected_index, len(remaining_tasks) - 1) if remaining_tasks else 0
    return replace(state, tasks=remaining_tasks, selected_index=next_index)


def sample_state() -> AppState:
    """Return an empty initial state — no mock tasks."""
    return AppState(tasks=[], selected_index=0)
