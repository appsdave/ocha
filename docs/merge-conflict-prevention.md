# Merge Conflict Prevention System

## Problem

ocha runs multiple Junie workers (coordinator, lead, builder, reviewer) on a **single shared `agent` branch** via git worktrees. When two workers edit the same file, the sequential cherry-pick / patch-apply merge in `git_utils.py` can fail or silently produce incorrect results.

## Solution: Multi-layered Conflict Prevention

### Layer 1: File-Ownership Lock Registry

A lightweight advisory lock system (`ocha/app/file_lock.py`) that prevents conflicts **before they happen** by enforcing directory-level ownership.

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
  │  Protected by OS-level fcntl flock (.ocha/locks.lock sentinel)     │
  └─────────────────────────────────────────────────────────────────────┘
```

### Layer 2: Atomic OS-Level Locking

All lock registry operations (`acquire_lock`, `release_lock`, `release_all_for_task`, `cleanup_stale_locks`) are now protected by `fcntl.flock` via a `.ocha/locks.lock` sentinel file. This prevents race conditions when multiple workers attempt to modify the registry concurrently — critical for parallel execution.

### Layer 3: Smart Execution Groups (ConcurrencyPolicy)

The app computes an **execution plan** that groups queued workers by ownership overlap:

```
ConcurrencyPolicy.AUTO (default):
  Group 0: [coordinator(docs/), lead(planning/), builder(app/)]  ← parallel
  Group 1: [reviewer(app/)]                                       ← waits for group 0

ConcurrencyPolicy.SEQUENTIAL:
  Group 0: [coordinator]
  Group 1: [lead]
  Group 2: [builder]
  Group 3: [reviewer]

ConcurrencyPolicy.FORCE_PARALLEL:
  Group 0: [coordinator, lead, builder, reviewer]  ← all at once (risky)
```

In the live TUI pipeline, `ocha/app/concurrency.py` provides `compute_execution_plan()`, which uses a greedy first-fit grouping strategy over owned-directory overlap and returns ordered `ExecutionGroup` batches. The older `file_lock.can_run_parallel()` / `orchestrator.compute_execution_plan()` path still exists as a compatibility helper, but the active worker-launch path in `app.py` uses the `concurrency.py` scheduler.

At runtime, `app.py` uses `concurrency.compute_execution_plan()` to select the
next launchable group from queued workers, starts that group in parallel, then
waits for it to finish before launching the next group. The helper is a greedy
first-fit scheduler: it walks queued workers in pipeline order and adds each one
to the earliest group whose ownership patterns do not overlap.

Legacy index-based scheduling helpers still exist in `orchestrator.py` and
`state.py`, but the active TUI pipeline now goes through `concurrency.py`.

### Layer 4: Commit-Scope Validation

Before merging worktree commits back onto `agent`, `git_utils.merge_worktree_commits()` delegates to `scope_validated_merge()`, which uses `file_lock.validate_commit_scope()` to compare the actual changed files with each worker's declared ownership scope. Out-of-scope changes are logged as warnings before the merge proceeds.

### Layer 5: Stale Lock Cleanup

`cleanup_stale_locks()` releases locks older than a configurable threshold (default 1 hour), preventing deadlocks from crashed workers.

### Key design decisions

| Decision | Rationale |
|----------|-----------|
| **Advisory, not blocking** | A misbehaving agent shouldn't deadlock the entire pipeline. Warnings are logged; the orchestrator decides policy. |
| **Directory-level granularity** | Matches the existing `ROLE_DIRECTORIES` mapping. Fine-grained file locks would add complexity without proportional benefit. |
| **JSON on disk + fcntl** | Simple, human-readable, works across worktrees. OS-level locking prevents concurrent corruption. No external dependencies. |
| **Greedy grouping for groups** | The active runtime scheduler uses a simple first-fit grouping pass; with only four workers, it stays easy to reason about and effectively instant. |
| **Advisory scope validation** | Scope checks surface warnings during merge instead of blocking the pipeline outright, matching the non-blocking lock design. |
| **Centralised worktree manager** | Single module (`worktree_manager.py`) for create/remove/cleanup/list — replaces ad-hoc worktree code in `app.py`. |

### API reference

#### file_lock.py

| Function | Purpose |
|----------|---------|
| `acquire_lock(project_path, session_id, task_id, role, patterns)` | Register ownership (atomic), returns `(lock, conflicts)` |
| `release_lock(project_path, session_id)` | Release a specific worker's lock (atomic) |
| `release_all_for_task(project_path, task_id)` | Release all locks for a completed task (atomic) |
| `detect_conflicts(requester, role, patterns, locks)` | Check for overlapping ownership |
| `validate_commit_scope(changed_files, owned_patterns)` | Verify a commit stayed in scope |
| `cleanup_stale_locks(project_path, max_age)` | Remove expired locks (atomic) |
| `can_run_parallel(workers)` | Compute parallel execution groups via graph-colouring |

#### concurrency.py

| Function | Purpose |
|----------|---------|
| `compute_execution_plan(workers, policy)` | Partition queued `WorkerSession` objects into runtime launch groups |
| `ExecutionGroup.session_ids` | Convenience view of the group members for logging/debugging |
| `ExecutionGroup.workers` | Tuple of workers that can launch concurrently |

#### git_utils.py

| Function | Purpose |
|----------|---------|
| `scope_validated_merge(shas, branch, patterns_by_sha)` | Merge with pre-merge scope validation |

#### worktree_manager.py

| Function | Purpose |
|----------|---------|
| `ensure_worktree(path, branch)` | Idempotent worktree creation |
| `remove_worktree(path)` | Safe single worktree removal |
| `cleanup_worktrees(paths)` | Batch removal + prune |
| `list_worktrees()` | Inventory of active worktrees |

#### state.py / concurrency.py

| Type | Purpose |
|------|---------|
| `state.ConcurrencyPolicy` | Legacy orchestration enum used by older planning helpers |
| `state.ExecutionGroup` | Legacy dataclass carrying worker indices for compatibility paths |
| `concurrency.ConcurrencyPolicy` | Active runtime policy enum: `sequential`, `auto`, `parallel` |
| `concurrency.ExecutionGroup` | Active runtime dataclass carrying worker tuples |

### Current role → directory mapping

| Role | Owned directory | Conflicts with |
|------|----------------|----------------|
| coordinator | `docs/` | — |
| lead | `planning/` | — |
| builder | `app/` | reviewer |
| reviewer | `app/` | builder |

The builder ↔ reviewer overlap is the primary conflict vector. Under `AUTO` policy, coordinator + lead + builder run in parallel (group 0), then reviewer runs alone (group 1).

## Current gaps

- `state.py` / `orchestrator.py` still carry older concurrency types and wrappers alongside the active `concurrency.py` runtime path; this duplication is now documented but not yet consolidated.
- There is still no user-facing CLI for inspecting or clearing the advisory lock registry.
