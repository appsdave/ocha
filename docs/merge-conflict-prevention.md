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

The app now computes an **execution plan** that groups queued workers by ownership overlap before launching the next pipeline batch:

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

Two scheduling helpers currently exist in the codebase:

- `app/concurrency.py` provides the **runtime** `compute_execution_plan()` used by `app.py._advance_pipeline()`. It works on queued `WorkerSession` objects and uses a greedy first-fit grouping strategy while preserving pipeline order.
- `app/file_lock.py` still exposes `can_run_parallel()` for the legacy tuple-based planner used by `orchestrator.py` helpers and tests. It builds a conflict graph from ownership patterns and assigns workers to the earliest non-conflicting group.

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
| **Greedy execution grouping** | Both planner implementations are O(n²) with at most four workers, so they stay simple and effectively instant. |
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
| `release_inactive_locks(project_path, active_session_ids)` | Reconcile persisted locks with currently active sessions |
| `can_run_parallel(workers)` | Compute tuple-based parallel execution groups |

#### concurrency.py

| Function / Type | Purpose |
|-----------------|---------|
| `ConcurrencyPolicy` | Runtime enum: `sequential`, `auto`, `parallel` |
| `ExecutionGroup` | Dataclass containing the grouped `WorkerSession` objects |
| `ExecutionGroup.session_ids` | Convenience view of grouped session IDs for logs/debugging |
| `compute_execution_plan(workers, policy)` | Partition queued `WorkerSession` objects into runtime launch groups |

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

- **Single runtime policy** — `app.py` currently hard-codes `ConcurrencyPolicy.AUTO`; there is still no CLI or TUI control to switch policies.
- **Advisory merge-scope enforcement** — `scope_validated_merge()` logs out-of-scope files but does not block the merge.
- **Duplicate scheduling types** — both `app/concurrency.py` and `app/state.py` still expose scheduling enums/dataclasses, which is functional but easy to confuse when reading the codebase.
- **Lock-registry UX** — there is still no user-facing CLI for inspecting or clearing the advisory lock registry.
