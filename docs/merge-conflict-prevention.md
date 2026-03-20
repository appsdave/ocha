# Merge Conflict Prevention System

## Problem

ocha runs multiple Junie workers (coordinator, lead, builder, reviewer) on a **single shared `agent` branch** via git worktrees. When two workers edit the same file, the sequential cherry-pick / patch-apply merge in `git_utils.py` can fail or silently produce incorrect results.

## Solution: File-Ownership Lock Registry

A lightweight advisory lock system (`ocha/app/file_lock.py`) that prevents conflicts **before they happen** by enforcing directory-level ownership.

### How it works

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐     ┌──────────────┐
│ coordinator  │     │     lead     │     │   builder    │     │   reviewer   │
│  owns docs/  │     │ owns planning│     │  owns app/   │     │  owns app/   │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       │                    │                    │                    │
       ▼                    ▼                    ▼                    ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │                    .ocha/locks.json                                  │
  │  File-ownership registry — tracks who owns what directories/files   │
  └─────────────────────────────────────────────────────────────────────┘
```

### Three layers of protection

1. **Lock acquisition** — When `launch_task()` prepares workers, each one registers its `owned_directory` in `.ocha/locks.json`. If two workers claim overlapping paths (e.g. builder and reviewer both own `app/`), a warning is logged so the orchestrator can serialise them.

2. **Commit-scope validation** — Before merging a worktree commit, `scope_validated_merge()` in `git_utils.py` checks whether the actual changed files fall within the worker's declared scope. Out-of-scope changes are logged as warnings.

3. **Stale lock cleanup** — `cleanup_stale_locks()` releases locks older than a configurable threshold (default 1 hour), preventing deadlocks from crashed workers.

### Key design decisions

| Decision | Rationale |
|----------|-----------|
| **Advisory, not blocking** | A misbehaving agent shouldn't deadlock the entire pipeline. Warnings are logged; the orchestrator decides policy. |
| **Directory-level granularity** | Matches the existing `ROLE_DIRECTORIES` mapping. Fine-grained file locks would add complexity without proportional benefit. |
| **JSON on disk** | Simple, human-readable, works across worktrees. No external dependencies (no Redis, no SQLite). |
| **Pattern-based matching** | Supports directories (`docs/`), globs (`*.md`), and exact paths for flexibility. |

### API reference

| Function | Purpose |
|----------|---------|
| `acquire_lock(project_path, session_id, task_id, role, patterns)` | Register ownership, returns `(lock, conflicts)` |
| `release_lock(project_path, session_id)` | Release a specific worker's lock |
| `release_all_for_task(project_path, task_id)` | Release all locks for a completed task |
| `detect_conflicts(requester, role, patterns, locks)` | Check for overlapping ownership |
| `validate_commit_scope(changed_files, owned_patterns)` | Verify a commit stayed in scope |
| `cleanup_stale_locks(project_path, max_age)` | Remove expired locks |
| `scope_validated_merge(shas, branch, patterns_by_sha)` | Merge with pre-merge scope check |

### Current role → directory mapping

| Role | Owned directory | Conflicts with |
|------|----------------|----------------|
| coordinator | `docs/` | — |
| lead | `planning/` | — |
| builder | `app/` | reviewer |
| reviewer | `app/` | builder |

The builder ↔ reviewer overlap is the primary conflict vector. The lock system detects this and the orchestrator serialises these workers (builder runs first, reviewer runs after).

## Files changed

- **`ocha/app/file_lock.py`** — New module: lock registry, conflict detection, scope validation
- **`ocha/app/orchestrator.py`** — Lock acquisition integrated into `launch_task()`
- **`ocha/app/git_utils.py`** — Added `get_changed_files()` and `scope_validated_merge()`
- **`ocha/tests/test_file_lock.py`** — 40 tests covering all lock operations

## Next steps

- **Orchestrator policy**: The lead/builder should wire conflict detection into the pipeline advance logic — when conflicts are detected, serialise the workers instead of running them in parallel.
- **Lock release on completion**: Wire `release_lock()` into the worker completion callback.
- **CLI command**: Add `ocha locks` subcommand to inspect/clear locks manually.
