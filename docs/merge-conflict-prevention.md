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

ConcurrencyPolicy.PARALLEL:
  Group 0: [coordinator, lead, builder, reviewer]  ← all at once (risky)
```

The `can_run_parallel()` function uses graph-colouring to find the optimal grouping: it builds a conflict adjacency graph from ownership patterns and greedily assigns workers to the earliest non-conflicting group.

At runtime, `app.py` uses `concurrency.compute_execution_plan()` to select the
next launchable group from queued workers, starts that group in parallel, then
waits for it to finish before launching the next group. The helper is a greedy
first-fit scheduler: it walks queued workers in pipeline order and adds each one
to the earliest group whose ownership patterns do not overlap.

Legacy index-based scheduling helpers still exist in `orchestrator.py` and
`state.py`, but the active TUI pipeline now goes through `concurrency.py`.

### Layer 4: Commit-Scope Validation

Before merging worktree commits, `git_utils.merge_worktree_commits()` calls
`validate_commit_scope()` for each commit to detect files that fall outside the
worker's declared ownership patterns. Out-of-scope changes are logged as
warnings before the merge continues.

### Layer 5: Stale Lock Cleanup

`cleanup_stale_locks()` releases locks older than a configurable threshold (default 1 hour), preventing deadlocks from crashed workers.

### Key design decisions

| Decision | Rationale |
|----------|-----------|
| **Advisory, not blocking** | A misbehaving agent shouldn't deadlock the entire pipeline. Warnings are logged; the orchestrator decides policy. |
| **Directory-level granularity** | Matches the existing `ROLE_DIRECTORIES` mapping. Fine-grained file locks would add complexity without proportional benefit. |
| **JSON on disk + fcntl** | Simple, human-readable, works across worktrees. OS-level locking prevents concurrent corruption. No external dependencies. |
| **Greedy grouping for groups** | The runtime scheduler uses a simple first-fit grouping pass over at most four workers, which is easy to reason about and fast enough in practice. |
| **Advisory scope validation** | Scope checks surface warnings during merge instead of blocking the pipeline outright, matching the non-blocking lock design. |

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

#### orchestrator.py

| Function | Purpose |
|----------|---------|
| `compute_execution_plan(workers, policy)` | Legacy index-based planner retained for older callers/tests |

#### state.py

| Type | Purpose |
|------|---------|
| `ConcurrencyPolicy` | Enum: `sequential`, `parallel`, `auto` |
| `ExecutionGroup` | Legacy dataclass carrying `group_index` + `worker_indices` |

### Current role → directory mapping

| Role | Owned directory | Conflicts with |
|------|----------------|----------------|
| coordinator | `docs/` | — |
| lead | `planning/` | — |
| builder | `app/` | reviewer |
| reviewer | `app/` | builder |

The builder ↔ reviewer overlap is the primary conflict vector. Under `AUTO` policy, coordinator + lead + builder run in parallel (group 0), then reviewer runs alone (group 1).

## Files changed

- **`ocha/app/file_lock.py`** — Lock persistence, atomic updates, conflict detection, and commit-scope validation helpers.
- **`ocha/app/concurrency.py`** — Runtime execution-group planner used by the TUI pipeline.
- **`ocha/app/app.py`** — Launches the next parallel-safe worker group and releases task locks during cleanup.
- **`ocha/app/state.py` / `ocha/app/orchestrator.py`** — Retain older scheduling types/helpers that some tests and non-runtime paths still reference.
- **`docs/architecture.md`** — Companion architecture reference for the current runtime wiring.
