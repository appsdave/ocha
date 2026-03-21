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

The runtime computes an **execution plan** that groups queued workers by ownership overlap before launching the next pipeline batch:

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

`compute_execution_plan()` in `ocha/app/concurrency.py` uses a greedy first-fit grouping strategy: workers stay in pipeline order, and each queued worker joins the earliest group whose ownership patterns do not overlap.

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
| **Greedy first-fit grouping** | O(n²) is effectively free for four workers, preserves pipeline order, and still exploits safe parallelism. |
| **Conflict-aware pipeline advancement** | `app.py` launches only the first safe execution group, then advances again when that group completes. |

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
| `can_run_parallel(workers)` | Fast boolean overlap check for a candidate worker set |
| `scope_validated_merge(shas, branch, patterns_by_sha)` | Merge with pre-merge scope check |

#### Scheduler implementations

| Function | Purpose |
|----------|---------|
| `app/concurrency.py:compute_execution_plan(workers, policy)` | Runtime scheduler used by `app.py` to build conflict-free execution batches |
| `app/orchestrator.py:compute_execution_plan(workers, policy)` | Legacy/alternate grouping helper that still mirrors the same policy concepts |

#### Shared scheduler types

| Type | Purpose |
|------|---------|
| `app/concurrency.py:ConcurrencyPolicy` | Runtime enum: `sequential`, `auto`, `parallel` |
| `app/concurrency.py:ExecutionGroup` | Runtime batch wrapper containing `workers` |
| `app/state.py:ConcurrencyPolicy` | Duplicate policy enum still referenced by older orchestration helpers |
| `app/state.py:ExecutionGroup` | Duplicate index-based execution-group type still referenced by older orchestration helpers |

### Current role → directory mapping

| Role | Owned directory | Conflicts with |
|------|----------------|----------------|
| coordinator | `docs/` | — |
| lead | `planning/` | — |
| builder | `app/` | reviewer |
| reviewer | `app/` | builder |

The builder ↔ reviewer overlap is the primary conflict vector. Under `AUTO` policy, coordinator + lead + builder run in parallel (group 0), then reviewer runs alone (group 1).

## Current status

- `app.py` already calls `compute_execution_plan(..., ConcurrencyPolicy.AUTO)` inside `_advance_pipeline()`.
- The scheduler launches the first conflict-free batch, waits for it to finish, then advances to the next batch.
- Upstream output from the most recently completed worker is injected into every worker in the next batch before launch.

## Open follow-ups

- Add a user-facing `--concurrency` control if operators need to override the default `AUTO` scheduler.
- Tighten the type ownership story: the runtime scheduler lives in `app/concurrency.py`, while related names are still duplicated in `app/state.py`.
- Consider documenting or exposing lock-inspection workflows for operators who need to debug stuck pipelines.
