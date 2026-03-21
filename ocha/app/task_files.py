from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


TASKS_ROOT = Path(".ocha") / "tasks"


@dataclass(slots=True, frozen=True)
class SessionArtifacts:
    session_id: str
    directory: Path
    prompt_path: Path
    manifest_path: Path


@dataclass(slots=True, frozen=True)
class TaskArtifacts:
    task_id: str
    directory: Path
    prompt_path: Path
    status_path: Path
    sessions_dir: Path

    def session(self, session_id: str) -> SessionArtifacts:
        directory = self.sessions_dir / session_id
        return SessionArtifacts(
            session_id=session_id,
            directory=directory,
            prompt_path=directory / "prompt.md",
            manifest_path=directory / "session.json",
        )


def task_artifacts(project_path: Path, task_id: str) -> TaskArtifacts:
    directory = project_path / TASKS_ROOT / task_id
    return TaskArtifacts(
        task_id=task_id,
        directory=directory,
        prompt_path=directory / "prompt.md",
        status_path=directory / "status.json",
        sessions_dir=directory / "sessions",
    )


def ensure_task_artifacts(project_path: Path, task_id: str) -> TaskArtifacts:
    artifacts = task_artifacts(project_path, task_id)
    artifacts.sessions_dir.mkdir(parents=True, exist_ok=True)
    return artifacts


def write_task_prompt(task_id: str, user_task: str, project_path: Path) -> Path:
    artifacts = ensure_task_artifacts(project_path, task_id)
    artifacts.prompt_path.write_text(user_task, encoding="utf-8")
    return artifacts.prompt_path


def write_session_prompt(task_id: str, session_id: str, prompt: str, project_path: Path) -> Path:
    artifacts = ensure_task_artifacts(project_path, task_id)
    session = artifacts.session(session_id)
    session.directory.mkdir(parents=True, exist_ok=True)
    session.prompt_path.write_text(prompt, encoding="utf-8")
    return session.prompt_path


def write_session_manifest(
    task_id: str,
    session_id: str,
    payload: dict[str, Any],
    project_path: Path,
) -> Path:
    artifacts = ensure_task_artifacts(project_path, task_id)
    session = artifacts.session(session_id)
    session.directory.mkdir(parents=True, exist_ok=True)
    session.manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return session.manifest_path