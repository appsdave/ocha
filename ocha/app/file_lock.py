"""File-ownership registry and lock manager for multi-agent conflict prevention.

Problem
-------
Multiple Junie workers share a single ``agent`` branch via git worktrees.
When two workers edit the same file, cherry-pick / patch-apply merges can
fail or silently produce incorrect results.

Solution
--------
A lightweight **file-lock registry** that:

1. **Declares ownership** — each worker registers the directory (or file
   glob patterns) it intends to modify *before* it starts working.
2. **Detects collisions** — before a worker begins, the registry checks
   whether any running worker already owns overlapping paths.
3. **Validates commits** — after a worker finishes, the registry can
   verify that its actual changes stayed within its declared scope.
4. **Persists state** — the lock file lives at ``.ocha/locks.json`` so
   it survives process restarts and is visible to all worktrees.

The system is *advisory* — it logs warnings rather than hard-blocking —
so a single misbehaving agent cannot deadlock the pipeline.  But the
orchestrator uses the information to serialise workers whose scopes
overlap, preventing the merge conflicts at their source.
"""

from __future__ import annotations

import json
import fnmatch
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Sequence


# ── Data structures ───────────────────────────────────────────────────

@dataclass(slots=True)
class FileLockEntry:
    """A single lock claim by one worker."""

    session_id: str
    task_id: str
    role: str
    owned_patterns: list[str]
    acquired_at: float = field(default_factory=time.time)
    released: bool = False

    def owns(self, path: str) -> bool:
        """Return *True* if *path* falls within any of this lock's patterns."""
        return any(_pattern_matches(pat, path) for pat in self.owned_patterns)


@dataclass(slots=True)
class LockConflict:
    """Describes a detected overlap between two workers."""

    path_or_pattern: str
    holder_session_id: str
    holder_role: str
    requester_session_id: str
    requester_role: str


# ── Pattern matching helpers ──────────────────────────────────────────

def _normalise(path: str) -> str:
    """Strip leading ``./`` or ``/`` so comparisons are repo-relative."""
    return path.lstrip("./").lstrip("/")


def _pattern_matches(pattern: str, path: str) -> bool:
    """Check whether *path* falls under *pattern*.

    Supports:
    - Directory ownership: ``docs/`` matches ``docs/foo.md``, ``docs/sub/bar.py``
    - Glob patterns: ``*.md``, ``app/**/*.py``
    - Exact file paths: ``ocha/app/state.py``
    """
    pattern = _normalise(pattern)
    path = _normalise(path)

    # Directory prefix match: "docs/" owns everything under docs/
    if pattern.endswith("/"):
        return path.startswith(pattern) or path == pattern.rstrip("/")

    # Exact match
    if pattern == path:
        return True

    # Glob / fnmatch
    return fnmatch.fnmatch(path, pattern)


# ── Registry operations ──────────────────────────────────────────────

_DEFAULT_LOCK_PATH = ".ocha/locks.json"


def _lock_file(project_path: Path) -> Path:
    return project_path / _DEFAULT_LOCK_PATH


def load_locks(project_path: Path) -> list[FileLockEntry]:
    """Load the current lock registry from disk."""
    lf = _lock_file(project_path)
    if not lf.exists():
        return []
    try:
        raw = json.loads(lf.read_text(encoding="utf-8"))
        return [FileLockEntry(**entry) for entry in raw]
    except (json.JSONDecodeError, TypeError, KeyError):
        return []


def save_locks(project_path: Path, locks: list[FileLockEntry]) -> Path:
    """Persist the lock registry to disk.  Returns the path written."""
    lf = _lock_file(project_path)
    lf.parent.mkdir(parents=True, exist_ok=True)
    payload = [asdict(lock) for lock in locks]
    lf.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return lf


def active_locks(locks: list[FileLockEntry]) -> list[FileLockEntry]:
    """Return only locks that have not been released."""
    return [lock for lock in locks if not lock.released]


def detect_conflicts(
    requester_session_id: str,
    requester_role: str,
    requested_patterns: Sequence[str],
    current_locks: list[FileLockEntry],
) -> list[LockConflict]:
    """Check *requested_patterns* against all active locks.

    Returns a (possibly empty) list of conflicts.  The caller decides
    whether to block, warn, or serialise.
    """
    conflicts: list[LockConflict] = []
    for lock in active_locks(current_locks):
        if lock.session_id == requester_session_id:
            continue  # Don't conflict with yourself
        for req_pat in requested_patterns:
            for held_pat in lock.owned_patterns:
                if _patterns_overlap(req_pat, held_pat):
                    conflicts.append(
                        LockConflict(
                            path_or_pattern=f"{req_pat} ↔ {held_pat}",
                            holder_session_id=lock.session_id,
                            holder_role=lock.role,
                            requester_session_id=requester_session_id,
                            requester_role=requester_role,
                        )
                    )
    return conflicts


def acquire_lock(
    project_path: Path,
    session_id: str,
    task_id: str,
    role: str,
    owned_patterns: Sequence[str],
) -> tuple[FileLockEntry, list[LockConflict]]:
    """Register ownership and return (lock, conflicts).

    The lock is always created — even when conflicts exist — so the
    orchestrator can decide policy (block, warn, or serialise).
    """
    locks = load_locks(project_path)
    conflicts = detect_conflicts(session_id, role, owned_patterns, locks)

    entry = FileLockEntry(
        session_id=session_id,
        task_id=task_id,
        role=role,
        owned_patterns=list(owned_patterns),
    )
    locks.append(entry)
    save_locks(project_path, locks)
    return entry, conflicts


def release_lock(project_path: Path, session_id: str) -> bool:
    """Mark the lock for *session_id* as released.

    Returns *True* if a matching lock was found and released.
    """
    locks = load_locks(project_path)
    found = False
    for lock in locks:
        if lock.session_id == session_id and not lock.released:
            lock.released = True
            found = True
    if found:
        save_locks(project_path, locks)
    return found


def release_all_for_task(project_path: Path, task_id: str) -> int:
    """Release every lock belonging to *task_id*.  Returns count released."""
    locks = load_locks(project_path)
    count = 0
    for lock in locks:
        if lock.task_id == task_id and not lock.released:
            lock.released = True
            count += 1
    if count:
        save_locks(project_path, locks)
    return count


def cleanup_stale_locks(project_path: Path, max_age_seconds: float = 3600) -> int:
    """Release locks older than *max_age_seconds*.  Returns count cleaned."""
    now = time.time()
    locks = load_locks(project_path)
    count = 0
    for lock in locks:
        if not lock.released and (now - lock.acquired_at) > max_age_seconds:
            lock.released = True
            count += 1
    if count:
        save_locks(project_path, locks)
    return count


# ── Commit-scope validation ──────────────────────────────────────────

def validate_commit_scope(
    changed_files: Sequence[str],
    owned_patterns: Sequence[str],
) -> list[str]:
    """Return files in *changed_files* that fall outside *owned_patterns*.

    An empty list means the worker stayed within its declared scope.
    """
    violations: list[str] = []
    for fpath in changed_files:
        if not any(_pattern_matches(pat, fpath) for pat in owned_patterns):
            violations.append(fpath)
    return violations


# ── Internal helpers ─────────────────────────────────────────────────

def _patterns_overlap(a: str, b: str) -> bool:
    """Heuristic check for whether two ownership patterns can conflict.

    This is intentionally conservative — it may report false positives
    but should never miss a true overlap.
    """
    a = _normalise(a)
    b = _normalise(b)

    # Directory containment
    if a.endswith("/") and b.startswith(a):
        return True
    if b.endswith("/") and a.startswith(b):
        return True
    if a.endswith("/") and b.endswith("/"):
        return a.startswith(b) or b.startswith(a)

    # One is a dir, the other a file inside it
    if a.endswith("/") and _pattern_matches(a, b):
        return True
    if b.endswith("/") and _pattern_matches(b, a):
        return True

    # Exact or glob match in either direction
    if _pattern_matches(a, b) or _pattern_matches(b, a):
        return True

    return False
