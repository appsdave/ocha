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
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Sequence


OCHA_BRANCH = "agent"


def ensure_worktree(
    worktree_path: str | Path,
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

    # Attempt 1: attach to branch
    result = subprocess.run(
        ["git", "worktree", "add", str(wt), branch],
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


def remove_worktree(
    worktree_path: str | Path,
    *,
    force: bool = True,
    timeout: int = 15,
) -> tuple[bool, str]:
    """Remove a single git worktree.

    Returns ``(success, message)``.
    """
    wt = Path(worktree_path)
    if not wt.exists():
        return True, f"Worktree {wt} already gone."

    cmd = ["git", "worktree", "remove"]
    if force:
        cmd.append("--force")
    cmd.append(str(wt))

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
