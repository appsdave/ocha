"""Git utilities for committing worktree changes and merging them onto the shared branch.

Problem
-------
Each Junie worker runs inside a detached git worktree.  When ``git add -A``
is executed from the **main** repo directory it never sees files that were
modified inside a worktree, so only the first worker's changes appear in the
PR while subsequent workers produce empty commits.

Solution
--------
1. ``commit_worktree_changes(worktree_path, message)`` — runs *inside* the
   worktree so ``git add -A`` captures that worktree's modifications, then
   commits and returns the SHA.
2. ``merge_worktree_commits(shas, branch)`` — cherry-picks each worktree
   SHA onto the shared branch from the main repo directory, falling back to
   ``git diff | git apply`` when cherry-pick fails (e.g. overlapping edits).
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def commit_worktree_changes(
    worktree_path: str | Path,
    message: str,
    *,
    timeout: int = 30,
) -> str | None:
    """Stage and commit all changes inside *worktree_path*.

    Returns the commit SHA on success, or ``None`` when there is nothing to
    commit (clean working tree).

    Raises ``subprocess.SubprocessError`` on unexpected git failures.
    """
    wt = str(worktree_path)

    # Stage everything inside the worktree
    result = subprocess.run(
        ["git", "add", "-A"],
        cwd=wt,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise subprocess.SubprocessError(
            f"git add failed in {wt}: {result.stderr.strip()}"
        )

    # Check if there is anything staged
    diff = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=wt,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if diff.returncode == 0:
        # Nothing staged — working tree is clean
        return None

    # Commit inside the worktree
    commit = subprocess.run(
        ["git", "commit", "-m", message],
        cwd=wt,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if commit.returncode != 0:
        raise subprocess.SubprocessError(
            f"git commit failed in {wt}: {commit.stderr.strip()}"
        )

    # Return the SHA of the new commit
    rev = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=wt,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return rev.stdout.strip()


def merge_worktree_commits(
    shas: list[str],
    branch: str,
    *,
    repo_dir: str | Path | None = None,
    timeout: int = 30,
) -> list[str]:
    """Cherry-pick worktree commit *shas* onto *branch* in the main repo.

    Parameters
    ----------
    shas:
        Commit SHAs produced by ``commit_worktree_changes``.  ``None`` values
        are silently skipped.
    branch:
        The target branch name (e.g. ``"agent"``).
    repo_dir:
        Working directory for git commands.  Defaults to the current directory.
    timeout:
        Per-command timeout in seconds.

    Returns
    -------
    list[str]
        Log messages describing what happened for each SHA.
    """
    cwd = str(repo_dir) if repo_dir else None
    logs: list[str] = []

    # Filter out None / empty values
    valid_shas = [s for s in shas if s]
    if not valid_shas:
        logs.append("No worktree commits to merge.")
        return logs

    # Ensure we are on the target branch
    subprocess.run(
        ["git", "checkout", branch],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    for sha in valid_shas:
        # Try cherry-pick first
        cp = subprocess.run(
            ["git", "cherry-pick", sha, "--no-commit"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if cp.returncode == 0:
            # Stage and commit the cherry-picked changes
            subprocess.run(
                ["git", "add", "-A"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            # Check if there are actual staged changes
            diff_check = subprocess.run(
                ["git", "diff", "--cached", "--quiet"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if diff_check.returncode != 0:
                subprocess.run(
                    ["git", "commit", "-m", f"Cherry-pick worktree {sha[:8]}"],
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
                logs.append(f"Cherry-picked {sha[:8]}.")
            else:
                # Cherry-pick resulted in no effective changes (already applied)
                subprocess.run(
                    ["git", "cherry-pick", "--abort"],
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
                logs.append(f"Skipped {sha[:8]} — changes already present.")
            continue

        # Cherry-pick failed — abort and fall back to patch-based apply
        subprocess.run(
            ["git", "cherry-pick", "--abort"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        # Generate a patch from the worktree commit
        diff_result = subprocess.run(
            ["git", "diff", f"{sha}~1", sha],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if diff_result.returncode != 0 or not diff_result.stdout.strip():
            logs.append(f"Skipped {sha[:8]} — could not generate patch.")
            continue

        # Apply the patch with --3way for better conflict resolution
        apply_result = subprocess.run(
            ["git", "apply", "--3way", "--allow-empty"],
            input=diff_result.stdout,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if apply_result.returncode == 0:
            subprocess.run(
                ["git", "add", "-A"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            diff_check = subprocess.run(
                ["git", "diff", "--cached", "--quiet"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if diff_check.returncode != 0:
                subprocess.run(
                    ["git", "commit", "-m", f"Patch-apply worktree {sha[:8]}"],
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
                logs.append(f"Applied patch for {sha[:8]}.")
            else:
                logs.append(f"Skipped {sha[:8]} — patch produced no changes.")
        else:
            logs.append(
                f"Failed to apply {sha[:8]}: {apply_result.stderr.strip()}"
            )

    return logs
