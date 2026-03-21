"""Centralised git-worktree lifecycle manager for multi-agent execution.

Provides a single point of control for creating, tracking, and cleaning
up git worktrees used by Junie worker sessions.  This replaces the ad-hoc
worktree creation scattered across ``app.py`` and gives the orchestrator
a reliable inventory of active worktrees.

Key features
------------
- **Idempotent creation** — calling ``ensure_worktree`` twice for the same
  worker is safe; the second call is a no-op.
- **Batch cleanup** — ``cleanup_worktrees`` removes all worktrees for a
  completed task in one pass, including ``git worktree prune``.
- **Inventory** — ``list_worktrees`` returns the set of active worktrees
  so the TUI and orchestrator can display and reason about them.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


DEFAULT_BRANCH = "agent"
OCHA_BRANCH = DEFAULT_BRANCH


@dataclass(slots=True, frozen=True)
class WorktreeResult:
    """Outcome of a worktree operation."""

    path: Path
    success: bool
    message: str


def ensure_worktree(
    worktree_path: str | Path,
    *,
    branch: str = DEFAULT_BRANCH,
    timeout: int = 30,
) -> WorktreeResult:
    """Create a git worktree at *worktree_path* if it does not exist.

    Tries ``git worktree add <path> <branch>`` first.  If the branch is
    already checked out elsewhere (common with the shared ``agent`` model),
    falls back to ``--detach``.

    Returns a :class:`WorktreeResult` — never raises on git errors.
    """
    wt = Path(worktree_path)
    if wt.exists():
        return WorktreeResult(wt, True, "Worktree already exists.")

    wt.parent.mkdir(parents=True, exist_ok=True)

    # Attempt 1: attach to branch
    result = subprocess.run(
        ["git", "worktree", "add", str(wt), branch],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode == 0:
        return WorktreeResult(wt, True, f"Created worktree on {branch}.")

    # Attempt 2: detached HEAD (branch already checked out)
    result = subprocess.run(
        ["git", "worktree", "add", "--detach", str(wt)],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode == 0:
        return WorktreeResult(wt, True, "Created worktree (detached).")

    return WorktreeResult(
        wt,
        False,
        f"Failed to create worktree: {result.stderr.strip()}",
    )


def remove_worktree(
    worktree_path: str | Path,
    *,
    force: bool = True,
    timeout: int = 15,
) -> WorktreeResult:
    """Remove a single worktree.  Returns a :class:`WorktreeResult`."""
    wt = Path(worktree_path)
    if not wt.exists():
        return WorktreeResult(wt, True, "Worktree already removed.")

    cmd = ["git", "worktree", "remove"]
    if force:
        cmd.append("--force")
    cmd.append(str(wt))

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode == 0:
        return WorktreeResult(wt, True, "Worktree removed.")
    return WorktreeResult(
        wt,
        False,
        f"Remove failed: {result.stderr.strip()}",
    )


def cleanup_worktrees(
    worktree_paths: Sequence[str | Path],
    *,
    prune: bool = True,
    timeout: int = 15,
) -> list[WorktreeResult]:
    """Remove multiple worktrees and optionally prune stale entries.

    Intended to be called after all workers in a task have finished.
    """
    results: list[WorktreeResult] = []
    for wt in worktree_paths:
        results.append(remove_worktree(wt, timeout=timeout))

    if prune:
        subprocess.run(
            ["git", "worktree", "prune"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    return results


def list_worktrees(*, timeout: int = 10) -> list[dict[str, str]]:
    """Return a list of active git worktrees as dicts with ``path`` and ``branch`` keys."""
    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        return []

    worktrees: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            if current:
                worktrees.append(current)
            current = {"path": line.split(" ", 1)[1]}
        elif line.startswith("branch "):
            current["branch"] = line.split(" ", 1)[1]
        elif line == "detached":
            current["branch"] = "(detached)"
        elif not line.strip() and current:
            worktrees.append(current)
            current = {}
    if current:
        worktrees.append(current)
    return worktrees
