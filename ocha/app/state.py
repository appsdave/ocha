from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
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
    now = datetime.now()
    tasks = [
        OchaTask(
            task_id="T-100",
            title="Refine Python/Textual rebuild scope",
            user_task="Gather project notes and refine the Python/Textual rebuild scope.",
            branch="agent",
            workers=[
                WorkerSession(
                    session_id="S-100-01",
                    task_id="T-100",
                    title="Refine Python/Textual rebuild scope",
                    role=WorkerRole.COORDINATOR,
                    status=WorkerStatus.COMPLETED,
                    branch="agent",
                    worktree_path="/repo/.worktrees/t-100-coordinator",
                    owned_directory="docs/",
                    summary="Prompt refined with project notes and TUI layout expectations.",
                    workflow_log=[
                        "Accepted top-level rebuild request.",
                        "Gathered README, Python/Textual, and headless-session concepts.",
                        "Prepared a tighter scope for the first scaffold.",
                    ],
                    raw_log=[
                        "[coordinator] loading project notes",
                        "[coordinator] synthesizing branch/worktree rules",
                        "[coordinator] completed enhanced prompt",
                    ],
                    task_prompt="Gather project notes and refine the Python/Textual rebuild scope.",
                    role_prompt_path="app/roles/coordinator.md",
                    latest_event="prompt_enhanced",
                    started_at=now - timedelta(minutes=12, seconds=12),
                    finished_at=now - timedelta(minutes=10, seconds=45),
                ),
                WorkerSession(
                    session_id="S-100-02",
                    task_id="T-100",
                    title="Refine Python/Textual rebuild scope",
                    role=WorkerRole.LEAD,
                    status=WorkerStatus.COMPLETED,
                    branch="agent",
                    worktree_path="/repo/.worktrees/t-100-lead",
                    owned_directory="planning/",
                    summary="Lead split the work into isolated UI and orchestration follow-ups.",
                    workflow_log=[
                        "Planned the MVP dashboard shape.",
                        "Assigned clean boundaries for state and widgets.",
                    ],
                    raw_log=["[lead] planned follow-up worktrees"],
                    task_prompt="Break the rebuild into UI shell, state model, and orchestration hooks.",
                    role_prompt_path="app/roles/lead.md",
                    latest_event="subtasks_planned",
                    started_at=now - timedelta(minutes=10, seconds=40),
                    finished_at=now - timedelta(minutes=8, seconds=18),
                ),
            ],
        ),
        OchaTask(
            task_id="T-101",
            title="Plan MVP dashboard and state model",
            user_task="Break the rebuild into UI shell, state model, and orchestration hooks.",
            branch="agent",
            workers=[
                WorkerSession(
                    session_id="S-101-01",
                    task_id="T-101",
                    title="Plan MVP dashboard and state model",
                    role=WorkerRole.COORDINATOR,
                    status=WorkerStatus.COMPLETED,
                    branch="agent",
                    worktree_path="/repo/.worktrees/t-101-coordinator",
                    owned_directory="docs/",
                    summary="Coordinator prepared the runtime-aware task prompt.",
                    workflow_log=["Collected current rebuild notes and operator expectations."],
                    raw_log=["[coordinator] prompt ready"],
                    task_prompt="Break the rebuild into UI shell, state model, and orchestration hooks.",
                    role_prompt_path="app/roles/coordinator.md",
                    latest_event="prompt_ready",
                    started_at=now - timedelta(minutes=7, seconds=55),
                    finished_at=now - timedelta(minutes=7, seconds=8),
                ),
                WorkerSession(
                    session_id="S-101-02",
                    task_id="T-101",
                    title="Plan MVP dashboard and state model",
                    role=WorkerRole.LEAD,
                    status=WorkerStatus.RUNNING,
                    branch="agent",
                    worktree_path="/repo/.worktrees/t-101-lead",
                    owned_directory="app/",
                    summary="Breaking the rebuild into UI shell, state models, and future orchestration hooks.",
                    workflow_log=[
                        "Inspecting widget layout for left list, header, output, and status bars.",
                        "Keeping one shared branch line visible across all worker rows.",
                        "Preferring separate directories/modules when future workers are scheduled.",
                    ],
                    raw_log=[
                        "[lead] evaluating task partitioning",
                        "[lead] module targets: app/state.py, app/app.py, app/widgets.py",
                        "[lead] awaiting scaffold completion",
                    ],
                    task_prompt="Break the rebuild into UI shell, state model, and orchestration hooks.",
                    role_prompt_path="app/roles/lead.md",
                    latest_event="lead_started",
                    retry_count=1,
                    started_at=now - timedelta(minutes=5, seconds=8),
                ),
                WorkerSession(
                    session_id="S-101-03",
                    task_id="T-101",
                    title="Plan MVP dashboard and state model",
                    role=WorkerRole.BUILDER,
                    status=WorkerStatus.QUEUED,
                    branch="agent",
                    worktree_path="/repo/.worktrees/t-101-builder",
                    owned_directory="app/widgets/",
                    summary="Waiting for the base app shell before attaching richer output behavior.",
                    workflow_log=[
                        "Reserved worktree for widget implementation.",
                        "Will expose workflow and raw log modes in one pane.",
                    ],
                    raw_log=["[builder] queued until scaffold files exist"],
                    task_prompt="Render the output pane and attach workflow/raw log switching.",
                    role_prompt_path="app/roles/builder.md",
                    latest_event="builder_queued",
                    started_at=now - timedelta(minutes=1, seconds=20),
                ),
                WorkerSession(
                    session_id="S-101-04",
                    task_id="T-101",
                    title="Plan MVP dashboard and state model",
                    role=WorkerRole.REVIEWER,
                    status=WorkerStatus.QUEUED,
                    branch="agent",
                    worktree_path="/repo/.worktrees/t-101-reviewer",
                    owned_directory="app/",
                    summary="Reviewer will validate the builder output after implementation lands.",
                    workflow_log=["Waiting for a builder result to review."],
                    raw_log=["[reviewer] queued behind builder"],
                    task_prompt="Review the completed builder changes and summarize validation.",
                    role_prompt_path="app/roles/reviewer.md",
                    latest_event="reviewer_queued",
                    started_at=now - timedelta(seconds=50),
                ),
            ],
        ),
    ]
    return AppState(tasks=tasks, selected_index=1)
