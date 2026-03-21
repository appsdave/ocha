<<<<<<< HEAD
"""Idempotent git-worktree lifecycle management.

Provides two main entry points used by the TUI app:

* :func:`ensure_worktree` — create a worktree for a worker session,
  handling the common failure modes (branch already checked out,
  directory already exists, etc.) gracefully.
* :func:`cleanup_worktrees` — remove worktrees for all finished workers
  in a task and prune the git worktree list.

All subprocess calls use ``capture_output=True`` and bounded timeouts
so they never block the Textual event loop when called via
``asyncio.to_thread``.
=======
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
- **Error isolation** — worktree failures are captured and returned as
  structured results, never raised, so one worker's bad state cannot
  crash the pipeline.
>>>>>>> b2d8e34 (ocha: coordinator S-003-01)
"""

from __future__ import annotations

import subprocess
<<<<<<< HEAD
=======
from dataclasses import dataclass
>>>>>>> b2d8e34 (ocha: coordinator S-003-01)
from pathlib import Path
from typing import Sequence


<<<<<<< HEAD
OCHA_BRANCH = "agent"
=======
DEFAULT_BRANCH = "agent"


@dataclass(slots=True, frozen=True)
class WorktreeResult:
    """Outcome of a worktree operation."""

    path: Path
    success: bool
    message: str
>>>>>>> b2d8e34 (ocha: coordinator S-003-01)


def ensure_worktree(
    worktree_path: str | Path,
<<<<<<< HEAD
    branch: str = OCHA_BRANCH,
    *,
    timeout: int = 30,
) -> tuple[bool, str]:
    """Create a git worktree at *worktree_path* if it doesn't already exist.

    Returns ``(success, message)``.

    The function is **idempotent**: if the directory already exists and
    looks like a valid worktree it returns success immediately.

    Failure modes handled:
    - Branch already checked out → falls back to ``--detach``.
    - Parent directory missing → created automatically.
    - Git not available or repo corrupt → returns ``(False, reason)``.
    """
    wt = Path(worktree_path)

    if wt.exists():
        # Quick sanity check: does it look like a worktree?
        if (wt / ".git").exists():
            return True, f"Worktree already exists at {wt}."
        # Directory exists but isn't a worktree — remove and recreate
        # to avoid confusing git.
        try:
            import shutil
            shutil.rmtree(wt)
        except OSError as exc:
            return False, f"Cannot clean stale directory {wt}: {exc}"

    try:
        wt.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return False, f"Cannot create parent directory: {exc}"
=======
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
>>>>>>> b2d8e34 (ocha: coordinator S-003-01)

    # Attempt 1: attach to branch
    result = subprocess.run(
        ["git", "worktree", "add", str(wt), branch],
<<<<<<< HEAD
        capture_output=True, text=True, timeout=timeout,
    )
    if result.returncode == 0:
        return True, f"Created worktree at {wt} on branch {branch}."

    # Attempt 2: detached HEAD (branch may already be checked out)
    result = subprocess.run(
        ["git", "worktree", "add", "--detach", str(wt)],
        capture_output=True, text=True, timeout=timeout,
    )
    if result.returncode == 0:
        return True, f"Created detached worktree at {wt}."

    return False, f"Worktree creation failed: {result.stderr.strip()}"
=======
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
>>>>>>> b2d8e34 (ocha: coordinator S-003-01)


def remove_worktree(
    worktree_path: str | Path,
    *,
    force: bool = True,
    timeout: int = 15,
<<<<<<< HEAD
) -> tuple[bool, str]:
    """Remove a single git worktree.

    Returns ``(success, message)``.
    """
    wt = Path(worktree_path)
    if not wt.exists():
        return True, f"Worktree {wt} already gone."
=======
) -> WorktreeResult:
    """Remove a single worktree.  Returns a :class:`WorktreeResult`."""
    wt = Path(worktree_path)
    if not wt.exists():
        return WorktreeResult(wt, True, "Worktree already removed.")
>>>>>>> b2d8e34 (ocha: coordinator S-003-01)

    cmd = ["git", "worktree", "remove"]
    if force:
        cmd.append("--force")
    cmd.append(str(wt))

<<<<<<< HEAD
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode == 0:
            return True, f"Removed worktree {wt}."
        return False, f"Failed to remove {wt}: {result.stderr.strip()}"
    except Exception as exc:
        return False, f"Error removing {wt}: {exc}"


def cleanup_worktrees(
    workers: Sequence,
    *,
    timeout: int = 15,
) -> list[str]:
    """Remove worktrees for all workers and prune the git worktree list.

    Parameters
    ----------
    workers:
        Sequence of worker objects with a ``worktree_path`` attribute.
    timeout:
        Per-command timeout in seconds.

    Returns
    -------
    list[str]
        Log messages describing what was cleaned up.
    """
    messages: list[str] = []

    for worker in workers:
        wt = Path(worker.worktree_path)
        if wt.exists():
            ok, msg = remove_worktree(wt, timeout=timeout)
            messages.append(msg)

    # Prune any dangling worktree references
    try:
        subprocess.run(
            ["git", "worktree", "prune"],
            capture_output=True, text=True, timeout=timeout,
        )
        messages.append("Pruned worktree list.")
    except Exception as exc:
        messages.append(f"Worktree prune error: {exc}")

    return messages
=======
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
>>>>>>> b2d8e34 (ocha: coordinator S-003-01)
