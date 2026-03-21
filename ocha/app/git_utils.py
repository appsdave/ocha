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
3. ``format_pr_title(task_id, title)`` — produces a clean, consistent PR
   title from task metadata.
4. ``ensure_pr_title(branch, title)`` — creates or updates the PR title
   so merged PRs always look clean in the git history.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class GitStateCheckResult:
    """Outcome of checking/repairing the repository Git state."""

    ok: bool
    messages: list[str]
    blocking_reason: str | None = None


_UNMERGED_PREFIXES = {"DD", "AU", "UD", "UA", "DU", "AA", "UU"}


def _run_git(
    *args: str,
    cwd: str | Path | None = None,
    timeout: int = 30,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _git_dir(repo_dir: str | Path | None = None, *, timeout: int = 10) -> Path | None:
    result = _run_git("git", "rev-parse", "--git-dir", cwd=repo_dir, timeout=timeout)
    if result.returncode != 0:
        return None
    git_dir = Path(result.stdout.strip())
    if not git_dir.is_absolute():
        base = Path(repo_dir) if repo_dir else Path.cwd()
        git_dir = (base / git_dir).resolve()
    return git_dir


def _porcelain_lines(repo_dir: str | Path | None = None, *, timeout: int = 10) -> list[str]:
    status = _run_git("git", "status", "--porcelain", cwd=repo_dir, timeout=timeout)
    if status.returncode != 0:
        return []
    return [line for line in status.stdout.splitlines() if line.strip()]


def _has_unmerged_entries(repo_dir: str | Path | None = None, *, timeout: int = 10) -> bool:
    for line in _porcelain_lines(repo_dir, timeout=timeout):
        if line[:2] in _UNMERGED_PREFIXES:
            return True
    return False


def _has_cherry_pick_in_progress(repo_dir: str | Path | None = None, *, timeout: int = 10) -> bool:
    git_dir = _git_dir(repo_dir, timeout=timeout)
    return bool(git_dir and (git_dir / "CHERRY_PICK_HEAD").exists())


def ensure_clean_git_state(
    *,
    repo_dir: str | Path | None = None,
    require_clean_worktree: bool = False,
    timeout: int = 30,
) -> GitStateCheckResult:
    """Abort unfinished git operations and verify the repo is safe to use."""
    git_dir = _git_dir(repo_dir, timeout=min(timeout, 10))
    if git_dir is None:
        return GitStateCheckResult(False, [], "Not a git repository.")

    messages: list[str] = []
    operations: list[tuple[str, tuple[str, ...], Path]] = [
        ("rebase", ("git", "rebase", "--abort"), git_dir / "rebase-merge"),
        ("rebase", ("git", "rebase", "--abort"), git_dir / "rebase-apply"),
        ("cherry-pick", ("git", "cherry-pick", "--abort"), git_dir / "CHERRY_PICK_HEAD"),
        ("merge", ("git", "merge", "--abort"), git_dir / "MERGE_HEAD"),
    ]
    aborted: set[str] = set()
    for label, command, marker in operations:
        if not marker.exists() or label in aborted:
            continue
        result = _run_git(*command, cwd=repo_dir, timeout=timeout)
        detail = result.stderr.strip() or result.stdout.strip()
        if result.returncode != 0:
            reason = detail or f"Failed to abort {label}."
            return GitStateCheckResult(False, messages, reason)
        messages.append(f"Aborted unfinished {label} operation.")
        aborted.add(label)

    if _has_unmerged_entries(repo_dir, timeout=min(timeout, 10)):
        return GitStateCheckResult(
            False,
            messages,
            "Git index still has unresolved merge conflicts.",
        )

    if require_clean_worktree:
        status = _run_git("git", "status", "--porcelain", "--untracked-files=no", cwd=repo_dir, timeout=min(timeout, 10))
        if status.returncode != 0:
            detail = status.stderr.strip() or status.stdout.strip() or "Failed to inspect git status."
            return GitStateCheckResult(False, messages, detail)
        dirty = [line for line in status.stdout.splitlines() if line.strip()]
        if dirty:
            return GitStateCheckResult(
                False,
                messages,
                "Tracked local changes are present; commit, stash, or discard them before continuing.",
            )

    return GitStateCheckResult(True, messages)


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
    logs: list[str] = []

    # Filter out None / empty values
    valid_shas = [s for s in shas if s]
    if not valid_shas:
        logs.append("No worktree commits to merge.")
        return logs

    # Ensure we are on the target branch
    checkout = _run_git("git", "checkout", branch, cwd=repo_dir, timeout=timeout)
    if checkout.returncode != 0:
        raise subprocess.SubprocessError(checkout.stderr.strip() or f"Failed to checkout {branch}.")

    for sha in valid_shas:
        # Try cherry-pick first
        cp = _run_git("git", "cherry-pick", sha, "--no-commit", cwd=repo_dir, timeout=timeout)
        if cp.returncode == 0:
            # Stage and commit the cherry-picked changes
            add_result = _run_git("git", "add", "-A", cwd=repo_dir, timeout=timeout)
            if add_result.returncode != 0:
                raise subprocess.SubprocessError(add_result.stderr.strip() or "git add failed after cherry-pick.")
            # Check if there are actual staged changes
            diff_check = _run_git("git", "diff", "--cached", "--quiet", cwd=repo_dir, timeout=timeout)
            if diff_check.returncode != 0:
                commit_result = _run_git(
                    "git", "commit", "-m", f"Cherry-pick worktree {sha[:8]}", cwd=repo_dir, timeout=timeout,
                )
                if commit_result.returncode != 0:
                    raise subprocess.SubprocessError(
                        commit_result.stderr.strip() or f"git commit failed for cherry-pick {sha[:8]}."
                    )
                logs.append(f"Cherry-picked {sha[:8]}.")
            else:
                # Cherry-pick resulted in no effective changes (already applied)
                if _has_cherry_pick_in_progress(repo_dir, timeout=min(timeout, 10)):
                    abort_result = _run_git("git", "cherry-pick", "--abort", cwd=repo_dir, timeout=timeout)
                    if abort_result.returncode != 0:
                        raise subprocess.SubprocessError(
                            abort_result.stderr.strip() or f"Failed to abort empty cherry-pick for {sha[:8]}."
                        )
                logs.append(f"Skipped {sha[:8]} — changes already present.")
            continue

        # Cherry-pick failed — abort and fall back to patch-based apply
        if _has_cherry_pick_in_progress(repo_dir, timeout=min(timeout, 10)):
            abort_result = _run_git("git", "cherry-pick", "--abort", cwd=repo_dir, timeout=timeout)
            if abort_result.returncode != 0:
                raise subprocess.SubprocessError(
                    abort_result.stderr.strip() or f"Failed to abort cherry-pick for {sha[:8]}."
                )
            cleanup_check = ensure_clean_git_state(repo_dir=repo_dir, timeout=timeout)
            if not cleanup_check.ok:
                detail = cleanup_check.blocking_reason or "Repository still dirty after cherry-pick abort."
                raise subprocess.SubprocessError(detail)

        # Generate a patch from the worktree commit
        diff_result = _run_git("git", "diff", f"{sha}~1", sha, cwd=repo_dir, timeout=timeout)
        if diff_result.returncode != 0 or not diff_result.stdout.strip():
            logs.append(f"Skipped {sha[:8]} — could not generate patch.")
            continue

        # Apply the patch with --3way for better conflict resolution
        apply_result = subprocess.run(
            ["git", "apply", "--3way", "--allow-empty"],
            input=diff_result.stdout,
            cwd=str(repo_dir) if repo_dir else None,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if apply_result.returncode == 0:
            add_result = _run_git("git", "add", "-A", cwd=repo_dir, timeout=timeout)
            if add_result.returncode != 0:
                raise subprocess.SubprocessError(add_result.stderr.strip() or "git add failed after patch apply.")
            diff_check = _run_git("git", "diff", "--cached", "--quiet", cwd=repo_dir, timeout=timeout)
            if diff_check.returncode != 0:
                commit_result = _run_git(
                    "git", "commit", "-m", f"Patch-apply worktree {sha[:8]}", cwd=repo_dir, timeout=timeout,
                )
                if commit_result.returncode != 0:
                    raise subprocess.SubprocessError(
                        commit_result.stderr.strip() or f"git commit failed for patch apply {sha[:8]}."
                    )
                logs.append(f"Applied patch for {sha[:8]}.")
            else:
                logs.append(f"Skipped {sha[:8]} — patch produced no changes.")
        else:
            reset_result = _run_git("git", "reset", "--hard", "HEAD", cwd=repo_dir, timeout=timeout)
            if reset_result.returncode != 0:
                detail = reset_result.stderr.strip() or "Failed to reset repository after patch-apply failure."
                raise subprocess.SubprocessError(detail)
            cleanup_check = ensure_clean_git_state(repo_dir=repo_dir, timeout=timeout)
            if not cleanup_check.ok:
                detail = cleanup_check.blocking_reason or "Repository still dirty after patch-apply failure."
                raise subprocess.SubprocessError(detail)
            logs.append(
                f"Failed to apply {sha[:8]}: {apply_result.stderr.strip()}"
            )

    return logs


# ── PR title formatting & renaming ────────────────────────────────────


def format_pr_title(task_id: str, raw_title: str) -> str:
    """Produce a clean, consistent PR title from task metadata.

    Format: ``[T-001] Short capitalised description``

    The function:
    - Strips leading/trailing whitespace and trailing ellipsis (``…``).
    - Collapses internal whitespace runs.
    - Capitalises the first letter of the description.
    - Prepends the task-id tag when not already present.
    - Truncates to 72 characters (GitHub's recommended max).
    """
    desc = raw_title.strip().rstrip("…").rstrip(".").rstrip(".").strip()
    # Also strip trailing ASCII ellipsis (three dots)
    desc = re.sub(r"\.{3,}$", "", desc).strip()
    desc = re.sub(r"\s+", " ", desc)
    if not desc:
        desc = "Automated task"

    tag = f"[{task_id}]"

    # Don't double-tag if the title already contains the task id
    if desc.upper().startswith(tag.upper()):
        desc = desc[len(tag):].strip()

    # Capitalise first letter of description
    if desc and desc[0].islower():
        desc = desc[0].upper() + desc[1:]

    full = f"{tag} {desc}"
    if len(full) > 72:
        full = full[:69].rstrip() + "…"
    return full


def ensure_pr_title(
    branch: str,
    title: str,
    *,
    base: str = "main",
    timeout: int = 30,
) -> str:
    """Create a new PR or update the existing PR's title on *branch*.

    Uses the ``gh`` CLI.  Returns a human-readable status message.
    If ``gh`` is not installed the function returns a skip message
    without raising.
    """
    gh_bin = shutil.which("gh")
    if not gh_bin:
        return "gh CLI not found — skipping PR title update."

    lookup = subprocess.run(
        [
            gh_bin, "pr", "list",
            "--state", "open",
            "--head", branch,
            "--json", "number",
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if lookup.returncode == 0:
        try:
            prs = json.loads(lookup.stdout or "[]")
        except json.JSONDecodeError:
            prs = None
        if prs:
            pr_number = prs[0].get("number")
            if pr_number is not None:
                edit = subprocess.run(
                    [gh_bin, "pr", "edit", str(pr_number), "--title", title],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
                if edit.returncode == 0:
                    return f"Open PR #{pr_number} title updated to: {title}"
                return (
                    f"PR update/create note: failed to update open PR #{pr_number}: "
                    f"{edit.stderr.strip()}"
                )

    create = subprocess.run(
        [
            gh_bin, "pr", "create",
            "--title", title,
            "--body", f"Automated PR for task {title.split(']')[0].strip('[') if ']' in title else 'ocha'}.",
            "--base", base,
            "--head", branch,
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if create.returncode == 0:
        return f"PR created: {create.stdout.strip()}"

    lookup_err = lookup.stderr.strip()
    create_err = create.stderr.strip()
    if lookup.returncode != 0:
        return f"PR update/create note: {lookup_err} / {create_err}"
    if prs is None:
        return f"PR update/create note: failed to parse gh pr list output / {create_err}"
    return f"PR update/create note: no open PR found for {branch} / {create_err}"


# ── Scope-validated merge helpers ─────────────────────────────────────


def get_changed_files(
    sha: str,
    *,
    repo_dir: str | Path | None = None,
    timeout: int = 30,
) -> list[str]:
    """Return the list of files changed in commit *sha*.

    Paths are repo-relative (e.g. ``ocha/app/state.py``).
    """
    cwd = str(repo_dir) if repo_dir else None
    result = subprocess.run(
        ["git", "diff-tree", "--no-commit-id", "-r", "--name-only", sha],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        return []
    return [f for f in result.stdout.strip().splitlines() if f]


def scope_validated_merge(
    shas: list[str],
    branch: str,
    owned_patterns_by_sha: dict[str, Sequence[str]],
    *,
    repo_dir: str | Path | None = None,
    timeout: int = 30,
) -> list[str]:
    """Merge worktree commits with scope validation.

    Before merging each SHA, checks that the changed files fall within the
    worker's declared ``owned_patterns``.  Out-of-scope files are logged
    as warnings but the merge still proceeds (advisory mode).

    Parameters
    ----------
    shas:
        Commit SHAs to merge.
    branch:
        Target branch.
    owned_patterns_by_sha:
        Mapping from SHA → list of owned directory/glob patterns.
    repo_dir:
        Working directory for git commands.
    timeout:
        Per-command timeout in seconds.

    Returns
    -------
    list[str]
        Log messages including any scope violations.
    """
    from .file_lock import validate_commit_scope

    logs: list[str] = []

    # Validate scope for each SHA before merging
    for sha in shas:
        if not sha:
            continue
        patterns = owned_patterns_by_sha.get(sha, [])
        if not patterns:
            continue
        changed = get_changed_files(sha, repo_dir=repo_dir, timeout=timeout)
        violations = validate_commit_scope(changed, patterns)
        if violations:
            violation_list = ", ".join(violations[:5])
            suffix = f" (+{len(violations) - 5} more)" if len(violations) > 5 else ""
            logs.append(
                f"⚠ Scope violation in {sha[:8]}: "
                f"{violation_list}{suffix} outside owned {patterns}"
            )

    # Proceed with the standard merge
    merge_logs = merge_worktree_commits(shas, branch, repo_dir=repo_dir, timeout=timeout)
    logs.extend(merge_logs)
    return logs
