from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from pathlib import Path
from textwrap import dedent
from typing import Any

from .state import AppState, OchaTask, TaskStatus, WorkerRole, WorkerSession, WorkerStatus


SHARED_BRANCH = "agent"
DEFAULT_WORKTREE_ROOT = ".worktrees"


@dataclass(slots=True, frozen=True)
class RoleDefinition:
    role: WorkerRole
    prompt_path: str
    prompt_markdown: str


@dataclass(slots=True, frozen=True)
class JunieLaunchSpec:
    role: WorkerRole
    session_id: str
    task_id: str
    project_path: Path
    worktree_path: Path
    owned_directory: str
    prompt_path: str
    prompt: str

    @property
    def command(self) -> list[str]:
        return [
            "junie",
            "--project",
            str(self.worktree_path),
            "--session-id",
            self.session_id,
            "--output-format",
            "text",
            "--task",
            self.prompt,
        ]


ROLE_DIRECTORIES = {
    WorkerRole.COORDINATOR: "docs/",
    WorkerRole.LEAD: "planning/",
    WorkerRole.BUILDER: "app/",
    WorkerRole.REVIEWER: "app/",
}


def _strip_front_matter(text: str) -> str:
    """Remove YAML front matter (``---`` delimited) from the top of *text*."""
    if not text.startswith("---"):
        return text
    end = text.find("---", 3)
    if end == -1:
        return text
    return text[end + 3:].strip()


@lru_cache(maxsize=1)
def load_role_definitions() -> dict[WorkerRole, RoleDefinition]:
    """Load and cache role prompt definitions from package resources.

    Results are cached after the first call since role markdown files
    do not change at runtime.  This avoids redundant disk I/O on every
    task launch and pipeline advance.
    """
    roles_package = resources.files("app.roles")
    definitions: dict[WorkerRole, RoleDefinition] = {}
    for role in WorkerRole:
        resource = roles_package / f"{role}.md"
        raw = resource.read_text(encoding="utf-8").strip()
        definitions[role] = RoleDefinition(
            role=role,
            prompt_path=f"app/roles/{role}.md",
            prompt_markdown=_strip_front_matter(raw),
        )
    return definitions


def build_role_prompt(
    definition: RoleDefinition,
    *,
    task_id: str,
    session_id: str,
    title: str,
    user_task: str,
    project_path: Path,
    worktree_path: Path,
    owned_directory: str,
    branch: str = SHARED_BRANCH,
    upstream_output: str = "",
) -> str:
    upstream_section = ""
    if upstream_output:
        upstream_section = dedent(
            f"""
            ## Prior phase output

            {upstream_output}
            """
        ).strip()

    return dedent(
        f"""
        {definition.prompt_markdown}

        ## Runtime context

        - role: {definition.role}
        - task_id: {task_id}
        - session_id: {session_id}
        - branch: {branch}
        - project_path: {project_path}
        - worktree_path: {worktree_path}
        - owned_directory: {owned_directory}

        ## Operator task

        Title: {title}

        {user_task}

        {upstream_section}

        ## Execution rules

        - Treat this as one headless Junie session started by `ocha`.
        - Stay within the assigned role and worktree boundary.
        - Prefer changes inside the assigned directory unless the task requires more.
        - Keep the shared branch model on `agent`; do not create branch-per-agent complexity.
        - Summarize the result so the TUI can surface a short workflow event.
        """
    ).strip()


def build_launch_specs(
    user_task: str,
    *,
    title: str | None = None,
    project_path: Path | None = None,
    task_number: int = 1,
) -> list[JunieLaunchSpec]:
    repo_root = (project_path or Path.cwd()).resolve()
    resolved_title = title or summarize_task(user_task)
    task_id = f"T-{task_number:03d}"
    role_definitions = load_role_definitions()
    specs: list[JunieLaunchSpec] = []

    for index, role in enumerate(WorkerRole, start=1):
        session_id = f"S-{task_number:03d}-{index:02d}"
        owned_directory = ROLE_DIRECTORIES[role]
        worktree_path = repo_root / DEFAULT_WORKTREE_ROOT / f"{task_id.lower()}-{role}"
        definition = role_definitions[role]
        specs.append(
            JunieLaunchSpec(
                role=role,
                session_id=session_id,
                task_id=task_id,
                project_path=repo_root,
                worktree_path=worktree_path,
                owned_directory=owned_directory,
                prompt_path=definition.prompt_path,
                prompt=build_role_prompt(
                    definition,
                    task_id=task_id,
                    session_id=session_id,
                    title=resolved_title,
                    user_task=user_task,
                    project_path=repo_root,
                    worktree_path=worktree_path,
                    owned_directory=owned_directory,
                ),
            )
        )

    return specs


def persist_task_prompt(task_id: str, user_task: str, project_path: Path) -> Path:
    """Write the operator prompt to ``.ocha/tasks/<task_id>/prompt.md``.

    Provides crash recovery and an audit trail per task.
    Returns the path to the written file.
    """
    task_dir = project_path / ".ocha" / "tasks" / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = task_dir / "prompt.md"
    prompt_path.write_text(user_task, encoding="utf-8")
    return prompt_path


def launch_task(state: AppState, user_task: str, *, project_path: Path | None = None) -> AppState:
    next_number = state.next_task_number
    title = summarize_task(user_task)
    specs = build_launch_specs(user_task, title=title, project_path=project_path, task_number=next_number)
    task_id = f"T-{next_number:03d}"
    repo_root = (project_path or Path.cwd()).resolve()
    persist_task_prompt(task_id, user_task, repo_root)
    tasks = list(state.tasks)
    task_workers: list[WorkerSession] = []

    for position, spec in enumerate(specs):
        status = WorkerStatus.RUNNING if position == 0 else WorkerStatus.QUEUED
        task_workers.append(
            WorkerSession(
                session_id=spec.session_id,
                task_id=spec.task_id,
                title=title,
                role=spec.role,
                status=status,
                branch=SHARED_BRANCH,
                worktree_path=str(spec.worktree_path),
                owned_directory=spec.owned_directory,
                summary=f"Prepared {spec.role} headless Junie launch from {spec.prompt_path}.",
                workflow_log=[
                    f"Loaded role prompt from {spec.prompt_path}.",
                    f"Prepared headless Junie session for {spec.role} in {spec.worktree_path}.",
                    "Waiting for orchestrator execution and streamed events.",
                ],
                raw_log=[
                    f"prompt_file={spec.prompt_path}",
                    f"junie_command={' '.join(spec.command[:-1])} <prompt>",
                    spec.prompt,
                ],
                task_prompt=spec.prompt,
                role_prompt_path=spec.prompt_path,
                latest_event="launch_prepared",
            )
        )

    tasks.append(
        OchaTask(
            task_id=task_id,
            title=title,
            user_task=user_task,
            branch=SHARED_BRANCH,
            workers=task_workers,
        )
    )

    return AppState(tasks=tasks, selected_index=len(tasks) - 1, output_mode=state.output_mode)


def summarize_task(user_task: str) -> str:
    normalized = " ".join(user_task.split())
    if not normalized:
        return "Untitled task"
    return normalized[:72] + ("…" if len(normalized) > 72 else "")


@dataclass(slots=True, frozen=True)
class TaskCreationResult:
    """Returned by :func:`create_task_from_prompt` to summarize what was created."""

    task_id: str
    title: str
    prompt_path: Path
    specs: list[JunieLaunchSpec]
    status: TaskStatus

    @property
    def workers(self) -> list[dict[str, str]]:
        return [
            {
                "role": spec.role.value,
                "session_id": spec.session_id,
                "worktree_path": str(spec.worktree_path),
                "owned_directory": spec.owned_directory,
            }
            for spec in self.specs
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "prompt_path": str(self.prompt_path),
            "status": self.status.value,
            "workers": self.workers,
        }

    def to_json(self, **kwargs: Any) -> str:
        return json.dumps(self.to_dict(), **kwargs)


def _next_task_number(repo_root: Path) -> int:
    """Determine the next task number from existing ``.ocha/tasks`` dirs."""
    tasks_root = repo_root / ".ocha" / "tasks"
    existing: list[int] = []
    if tasks_root.exists():
        for child in tasks_root.iterdir():
            if child.is_dir() and child.name.startswith("T-"):
                try:
                    existing.append(int(child.name.split("-", 1)[1]))
                except (ValueError, IndexError):
                    pass
    return (max(existing) + 1) if existing else 1


def create_task_from_prompt(
    prompt: str,
    *,
    project_path: Path | None = None,
    task_number: int | None = None,
) -> TaskCreationResult:
    """Create a persisted task from a user prompt.

    This is the primary entry-point for prompt-based task creation from the
    CLI.  It persists the prompt to disk, builds launch specs for every
    worker role, writes per-session prompt files, and writes a status marker
    so the TUI (or a later ``launch_task`` call) can pick the task up.

    When *task_number* is ``None`` the next available number is determined
    automatically from existing ``.ocha/tasks/`` directories.

    Returns a :class:`TaskCreationResult` with everything a caller needs to
    display confirmation or continue orchestration.
    """
    repo_root = (project_path or Path.cwd()).resolve()

    if task_number is None:
        task_number = _next_task_number(repo_root)

    title = summarize_task(prompt)
    task_id = f"T-{task_number:03d}"
    prompt_path = persist_task_prompt(task_id, prompt, repo_root)
    specs = build_launch_specs(prompt, title=title, project_path=repo_root, task_number=task_number)

    # Persist per-worker session prompts so each Junie invocation has its file
    task_dir = repo_root / ".ocha" / "tasks" / task_id
    for spec in specs:
        session_file = task_dir / f"{spec.session_id}-prompt.md"
        session_file.write_text(spec.prompt, encoding="utf-8")

    status_path = task_dir / "status.json"
    _write_task_status(status_path, task_id, title, TaskStatus.PENDING)
    return TaskCreationResult(
        task_id=task_id,
        title=title,
        prompt_path=prompt_path,
        specs=specs,
        status=TaskStatus.PENDING,
    )


def _write_task_status(path: Path, task_id: str, title: str, status: TaskStatus) -> None:
    """Write a minimal JSON status marker for a task."""
    from datetime import datetime, timezone

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "task_id": task_id,
        "title": title,
        "status": status.value,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


