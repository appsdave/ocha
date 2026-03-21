from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .workflow_logger import WorkflowLogger


# Maximum number of log lines retained per worker to bound memory usage.
# Older entries are discarded automatically when the limit is exceeded.
MAX_LOG_LINES = 5_000


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


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ConcurrencyPolicy(StrEnum):
    """Controls how the orchestrator schedules workers within a task.

    - ``SEQUENTIAL`` — one worker at a time (safe, current default).
    - ``PARALLEL`` — all workers at once (fast, risk of conflicts).
    - ``AUTO`` — non-conflicting workers run in parallel; conflicting
      workers are serialised into later execution groups.
    """

    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    AUTO = "auto"


STATUS_PRIORITY = {
    WorkerStatus.RUNNING: 0,
    WorkerStatus.FAILED: 1,
    WorkerStatus.QUEUED: 2,
    WorkerStatus.COMPLETED: 3,
    WorkerStatus.STOPPED: 4,
}


@dataclass(slots=True, frozen=True)
class ExecutionGroup:
    """A batch of worker indices that can execute concurrently.

    Produced by :func:`orchestrator.compute_execution_plan`.  Groups are
    executed in order of ``group_index``; workers within a group run in
    parallel because their owned directories do not overlap.
    """

    group_index: int
    worker_indices: list[int] = field(default_factory=list)


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
    workflow_log: deque[str] = field(default_factory=lambda: deque(maxlen=MAX_LOG_LINES))
    raw_log: deque[str] = field(default_factory=lambda: deque(maxlen=MAX_LOG_LINES))
    wlog: WorkflowLogger | None = field(default=None, repr=False)
    task_prompt: str = ""
    role_prompt_path: str = ""
    upstream_summary: str = ""
    worktree_commit_sha: str | None = None
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
    _output_cache_key: tuple | None = field(default=None, repr=False, compare=False)
    _output_cache_value: list[str] = field(default_factory=list, repr=False, compare=False)

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
        """Build prefixed log output for display.

        Uses a lightweight cache keyed on the total line count per mode
        so repeated calls within the same tick skip the rebuild entirely.

        In WORKFLOW mode, if a worker carries a structured
        :class:`WorkflowLogger` the rich-formatted lines are used so the
        TUI gets timestamps, icons and colour.  Falls back to the legacy
        ``workflow_log`` deque for workers created before the logger was
        wired in.
        """
        total = sum(
            len(w.workflow_log if mode == OutputMode.WORKFLOW else w.raw_log)
            for w in self.workers
        )
        cache_key = (mode, total)
        if self._output_cache_key == cache_key:
            return self._output_cache_value

        lines: list[str] = []
        for worker in self.workers:
            if mode == OutputMode.WORKFLOW and worker.wlog is not None:
                lines.extend(worker.wlog.rich_lines())
            else:
                source_lines = worker.workflow_log if mode == OutputMode.WORKFLOW else worker.raw_log
                role_tag = f"[{worker.role}] "
                lines.extend(role_tag + line for line in source_lines)

        self._output_cache_key = cache_key
        self._output_cache_value = lines
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
