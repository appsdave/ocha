from __future__ import annotations

from dataclasses import dataclass, field
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
class AppState:
    workers: list[WorkerSession]
    selected_index: int = 0
    output_mode: OutputMode = OutputMode.WORKFLOW

    @property
    def selected_worker(self) -> WorkerSession:
        return self.workers[self.selected_index]

    @property
    def status_counts(self) -> dict[WorkerStatus, int]:
        return {status: sum(worker.status == status for worker in self.workers) for status in WorkerStatus}


def sample_state() -> AppState:
    now = datetime.now()
    workers = [
        WorkerSession(
            session_id="S-101",
            task_id="T-100",
            title="Refine Python/Textual rebuild scope",
            role=WorkerRole.COORDINATOR,
            status=WorkerStatus.COMPLETED,
            branch="agent",
            worktree_path="/repo/.worktrees/agent-1",
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
            started_at=now - timedelta(minutes=9, seconds=12),
            finished_at=now - timedelta(minutes=7, seconds=45),
        ),
        WorkerSession(
            session_id="S-102",
            task_id="T-101",
            title="Plan MVP dashboard and state model",
            role=WorkerRole.LEAD,
            status=WorkerStatus.RUNNING,
            branch="agent",
            worktree_path="/repo/.worktrees/agent-2",
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
            retry_count=1,
            started_at=now - timedelta(minutes=5, seconds=8),
        ),
        WorkerSession(
            session_id="S-103",
            task_id="T-102",
            title="Render Textual output pane scaffold",
            role=WorkerRole.BUILDER,
            status=WorkerStatus.QUEUED,
            branch="agent",
            worktree_path="/repo/.worktrees/agent-3",
            owned_directory="app/widgets/",
            summary="Waiting for the base app shell before attaching richer output behavior.",
            workflow_log=[
                "Reserved worktree for widget implementation.",
                "Will expose workflow and raw log modes in one pane.",
            ],
            raw_log=["[builder] queued until scaffold files exist"],
            started_at=now - timedelta(minutes=1, seconds=20),
        ),
    ]
    return AppState(workers=workers)
