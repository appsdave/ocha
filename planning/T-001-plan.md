# T-001 Execution Plan — Wire the Coordinator → Lead → Builder → Reviewer Relay

**Lead:** S-001-02
**Branch:** agent
**Date:** 2026-03-19

---

## Overview

The coordinator brief identified five gaps that prevent the 4-phase pipeline
from acting as a relay.  This plan breaks the fix into **four builder tasks**
and **one reviewer pass**, ordered to minimize merge pain and keep file
ownership clear.

All work stays on the shared `agent` branch.  Each task targets a distinct
set of files so parallelism is safe where noted.

---

## Task breakdown

### Task 1 — Enrich role prompts with input/output contracts

**Worker:** builder
**Owned files:** `app/roles/coordinator.md`, `app/roles/lead.md`, `app/roles/builder.md`, `app/roles/reviewer.md`
**Depends on:** nothing (can start immediately)
**Parallel safe:** yes — no other task touches `app/roles/`

Rewrite each role `.md` to specify:

1. **Input:** what artifact it receives from the prior phase (or from the operator for coordinator).
2. **Output:** the exact heading it must produce at the end of its response (contract name).
3. **Format:** one mandatory section per role:
   - `coordinator.md` → must end with `## Execution Brief`
   - `lead.md` → must end with `## Task Plan`
   - `builder.md` → must end with `## Change Summary`
   - `reviewer.md` → must end with `## Review Verdict`

Keep the existing guidance paragraphs; append the contract section.

---

### Task 2 — Add `upstream_output` to `build_role_prompt()`

**Worker:** builder
**Owned files:** `app/orchestrator.py`
**Depends on:** nothing (can run in parallel with Task 1)
**Parallel safe:** yes — no other task edits `orchestrator.py`

Changes:

1. Add parameter `upstream_output: str = ""` to `build_role_prompt()`.
2. When `upstream_output` is non-empty, inject a `## Prior phase output` section
   into the assembled prompt, placed between the runtime context block and the
   operator task block.
3. Thread the new parameter through `build_launch_specs()` — add
   `upstream_output` to `JunieLaunchSpec` (default `""`).
4. For the first role (coordinator), `upstream_output` stays empty.
   For subsequent roles it will be populated at advancement time (Task 3).

---

### Task 3 — Wire handoff in `_advance_pipeline()`

**Worker:** builder
**Owned files:** `app/app.py`, `app/state.py`
**Depends on:** Task 2 (needs `upstream_output` parameter to exist)
**Parallel safe:** no — must run after Task 2

Changes in `app/state.py`:

1. Add field `upstream_summary: str = ""` to `WorkerSession`.

Changes in `app/app.py` `_advance_pipeline()`:

1. After finding `next_worker`, locate the most recently completed worker
   in the same task (the one whose completion triggered advancement).
2. Capture that worker's `summary` field as `upstream_summary`.
3. Store it on `next_worker.upstream_summary`.
4. Rebuild `next_worker.task_prompt` by calling `build_role_prompt()` with
   the captured `upstream_output=upstream_summary`.
   - This requires importing `build_role_prompt` and `load_role_definitions`
     in `app.py`, or storing enough metadata on `WorkerSession` to regenerate
     the prompt.  Simplest approach: store the original role definition data
     on `WorkerSession` at launch time (add `role_definition_role: str` field
     or reuse `role_prompt_path`), then call `build_role_prompt()` at
     advancement time.

Also clean up the misleading comment in `_post_pipeline_git_flow` (line 601
says "Create a task-specific branch" but it actually uses `agent`).

---

### Task 4 — Fix branch model and git flow

**Worker:** builder
**Owned files:** `app/app.py` (only `_post_pipeline_git_flow` method)
**Depends on:** Task 3 (same file, sequential)
**Parallel safe:** no — same file as Task 3, must be sequenced

Changes:

1. Remove the redundant `checkout -b` / `checkout` dance at the top of
   `_post_pipeline_git_flow` — the app already ensures we're on `agent`.
2. Before push, add `git fetch origin agent && git rebase origin/agent`
   to avoid push conflicts.
3. Keep the PR creation (`agent` → `main`) as-is.
4. Update the comment to accurately describe what the method does.

> **Note:** Tasks 3 and 4 both touch `app/app.py`.  They MUST run
> sequentially in a single builder session or be carefully merged.
> Recommended: combine Tasks 3 + 4 into one builder session.

---

### Task 5 — Review and test coverage

**Worker:** reviewer
**Owned files:** `tests/test_orchestrator.py`, `tests/test_app.py`
**Depends on:** Tasks 1–4 (all builder work must be complete)
**Parallel safe:** yes — reviewer only reads `app/` and writes `tests/`

Review checklist:

1. Verify each `app/roles/*.md` contains the required contract headings.
2. Verify `build_role_prompt()` injects `## Prior phase output` when
   `upstream_output` is non-empty and omits it when empty.
3. Verify `_advance_pipeline()` captures the completed worker's summary
   and stores it on the next worker.
4. Verify `_post_pipeline_git_flow` no longer does redundant branch creation.

Test additions:

- `test_orchestrator.py`: test `build_role_prompt()` with and without
  `upstream_output`; assert the section appears/doesn't appear.
- `test_app.py`: test that `_advance_pipeline` sets `upstream_summary`
  on the next worker (mock or unit-level).
- Add a simple test that each role `.md` contains its expected output
  heading (`## Execution Brief`, `## Task Plan`, etc.).

---

## Execution order

```
          ┌──────────┐     ┌──────────┐
          │ Task 1   │     │ Task 2   │   ← parallel safe
          │ roles/   │     │ orch.py  │
          └────┬─────┘     └────┬─────┘
               │                │
               │           ┌────▼─────┐
               │           │ Task 3   │   ← depends on Task 2
               │           │ app.py + │
               │           │ state.py │
               │           └────┬─────┘
               │                │
               │           ┌────▼─────┐
               │           │ Task 4   │   ← depends on Task 3 (same file)
               │           │ app.py   │
               │           └────┬─────┘
               │                │
               └───────┬───────┘
                  ┌────▼─────┐
                  │ Task 5   │   ← reviewer, after all builder tasks
                  │ tests/   │
                  └──────────┘
```

**Recommended session grouping:**

| Session | Tasks | Role | Why |
|---------|-------|------|-----|
| Builder A | Task 1 | builder | Isolated to `app/roles/` |
| Builder B | Tasks 2 + 3 + 4 | builder | All touch `app/` — single session avoids merge conflicts |
| Reviewer | Task 5 | reviewer | Reads everything, writes only `tests/` |

Builder A and Builder B can run in parallel.
Reviewer runs after both builders complete.

---

## Lead summary (for TUI event)

> Produced execution plan with 5 tasks across 3 sessions.  Two parallel
> builder sessions (role prompts + orchestrator/app wiring) followed by
> one reviewer session for test coverage.  All work stays on `agent` branch
> with no file overlap between parallel sessions.
