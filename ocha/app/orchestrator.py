from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from textwrap import dedent

from .state import AppState, OchaTask, WorkerRole, WorkerSession, WorkerStatus


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
            str(self.project_path),
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


def load_role_definitions() -> dict[WorkerRole, RoleDefinition]:
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
) -> str:
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


def launch_task(state: AppState, user_task: str, *, project_path: Path | None = None) -> AppState:
    next_number = state.next_task_number
    title = summarize_task(user_task)
    specs = build_launch_specs(user_task, title=title, project_path=project_path, task_number=next_number)
    task_id = f"T-{next_number:03d}"
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
