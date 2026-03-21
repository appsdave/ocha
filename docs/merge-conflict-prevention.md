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

The orchestrator can now compute an **execution plan** that groups workers by ownership overlap:

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

### Layer 4: Commit-Scope Validation

Before merging a worktree commit, `scope_validated_merge()` checks whether the actual changed files fall within the worker's declared scope. Out-of-scope changes are logged as warnings.

### Layer 5: Stale Lock Cleanup

`cleanup_stale_locks()` releases locks older than a configurable threshold (default 1 hour), preventing deadlocks from crashed workers.

### Key design decisions

| Decision | Rationale |
|----------|-----------|
| **Advisory, not blocking** | A misbehaving agent shouldn't deadlock the entire pipeline. Warnings are logged; the orchestrator decides policy. |
| **Directory-level granularity** | Matches the existing `ROLE_DIRECTORIES` mapping. Fine-grained file locks would add complexity without proportional benefit. |
| **JSON on disk + fcntl** | Simple, human-readable, works across worktrees. OS-level locking prevents concurrent corruption. No external dependencies. |
| **Graph-colouring for groups** | Greedy colouring is O(n²) but n ≤ 4 workers, so it's instant. Optimal grouping maximises parallelism. |
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
| `scope_validated_merge(shas, branch, patterns_by_sha)` | Merge with pre-merge scope check |

#### orchestrator.py

| Function | Purpose |
|----------|---------|
| `compute_execution_plan(workers, policy)` | Partition workers into sequential execution groups |

#### worktree_manager.py

| Function | Purpose |
|----------|---------|
| `ensure_worktree(path, branch)` | Idempotent worktree creation |
| `remove_worktree(path)` | Safe single worktree removal |
| `cleanup_worktrees(paths)` | Batch removal + prune |
| `list_worktrees()` | Inventory of active worktrees |

#### state.py

| Type | Purpose |
|------|---------|
| `ConcurrencyPolicy` | Enum: `sequential`, `parallel`, `auto` |
| `ExecutionGroup` | Dataclass: `group_index` + `worker_indices` |

### Current role → directory mapping

| Role | Owned directory | Conflicts with |
|------|----------------|----------------|
| coordinator | `docs/` | — |
| lead | `planning/` | — |
| builder | `app/` | reviewer |
| reviewer | `app/` | builder |

The builder ↔ reviewer overlap is the primary conflict vector. Under `AUTO` policy, coordinator + lead + builder run in parallel (group 0), then reviewer runs alone (group 1).

## Files changed

- **`ocha/app/file_lock.py`** — Atomic fcntl locking, `can_run_parallel()` graph-colouring
- **`ocha/app/state.py`** — `ConcurrencyPolicy` enum, `ExecutionGroup` dataclass
- **`ocha/app/orchestrator.py`** — `compute_execution_plan()` function
- **`ocha/app/worktree_manager.py`** — New module: centralised worktree lifecycle
- **`ocha/tests/test_concurrency.py`** — 17 tests covering all new functionality
- **`docs/architecture.md`** — Fixed merge conflicts from prior runs

## Next steps

- **Wire `compute_execution_plan` into `_advance_pipeline`** — the builder should update `app.py` to launch groups in parallel using `asyncio.gather` instead of one-at-a-time sequential advancement.
- **Add `--concurrency` CLI flag** — expose `ConcurrencyPolicy` via `ocha task --concurrency=auto`.
- **Lock release on completion** — wire `release_lock()` into the worker completion callback in `app.py`.
- **Use `worktree_manager`** — replace the inline worktree code in `app.py._ensure_worktree` with calls to `worktree_manager.ensure_worktree`.
- **CLI command**: Add `ocha locks` subcommand to inspect/clear locks manually.
