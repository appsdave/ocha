# T-001 Execution Brief — Improve Coordinator → Lead → Builder → Reviewer Pipeline

**Coordinator:** S-001-01
**Branch:** agent
**Date:** 2026-03-19

---

## Goal (refined)

The operator asks to "update the agent workflow to have better coordinator lead
builder reviewer movement using the ocha agentless flow."

Translated into project terms: the current sequential pipeline
(coordinator → lead → builder → reviewer) exists in skeleton form but each
phase is **disconnected** — no role receives the previous role's output, the
role prompts are thin, and the pipeline advancement in `app.py` treats every
worker as independent.  The fix is to wire explicit **artifact handoff** between
phases so that each downstream role consumes what the upstream role produced.

This is **not** about adding new roles or changing the 4-role model.  It is
about making the existing 4-phase pipeline actually flow like a relay instead
of four isolated jobs.

---

## Current state (problems identified)

| # | Gap | Where |
|---|-----|-------|
| 1 | **No output handoff.** When the coordinator finishes, the lead receives the same raw operator prompt — not the coordinator's refined brief. Same for builder and reviewer. | `app/orchestrator.py` `build_role_prompt()` — prompt is static per role |
| 2 | **Role prompts are too thin.** Each role .md file is ~10 lines with generic guidance. They don't specify what artifact to produce or what artifact to expect from the prior phase. | `app/roles/*.md` |
| 3 | **`_advance_pipeline` doesn't capture prior output.** Pipeline advancement starts the next worker but never injects the completed worker's `summary` or result into the next worker's prompt. | `app/app.py` `_advance_pipeline()` lines 563-594 |
| 4 | **`_post_pipeline_git_flow` creates `ocha/<task-id>` branch** instead of staying on `agent`. | `app/app.py` lines 596-665, uses `OCHA_BRANCH` not `agent` |
| 5 | **Worktree paths are specified but never created.** `_run_junie_for_worker` uses `cwd()` instead of `spec.worktree_path`. | `app/app.py` |

---

## Relevant files (priority order)

### Must-read / must-edit

| File | Reason |
|------|--------|
| `app/orchestrator.py` | `build_role_prompt()` needs a new `upstream_output` parameter so each phase can inject prior results |
| `app/roles/coordinator.md` | Needs to specify: produce an execution brief, output format, what the lead will consume |
| `app/roles/lead.md` | Needs to specify: consume the coordinator brief, produce a task plan, output format for builder |
| `app/roles/builder.md` | Needs to specify: consume the lead plan, produce code changes + summary for reviewer |
| `app/roles/reviewer.md` | Needs to specify: consume builder summary + filesystem state, produce ready/rework verdict |
| `app/app.py` | `_advance_pipeline()` must capture the completed worker's summary and pass it to the next launch |
| `app/state.py` | `WorkerSession` may need an `upstream_summary` or `input_artifact` field |

### Secondary / test

| File | Reason |
|------|--------|
| `tests/test_orchestrator.py` | Must be updated to cover new `upstream_output` parameter in `build_role_prompt` |
| `tests/test_app.py` | Pipeline advancement tests should verify handoff behavior |
| `junie-headless-sessions.md` | Design doc — update to reflect the handoff model |

---

## Recommended changes (for the lead to break into sub-tasks)

### Phase 1 — Role prompt enrichment (builder scope: `app/roles/`)

Rewrite each role `.md` to be explicit about:

- **What input it expects** (operator prompt, coordinator brief, lead plan, builder summary)
- **What output it must produce** (a named artifact section at the end of its response)
- **Format contract** (e.g., coordinator must end with `## Execution Brief`, lead must end with `## Task Plan`, builder must end with `## Change Summary`)

This is the highest-leverage change — even without code changes, better prompts
improve the relay behavior because Junie sessions will produce structured
output the next phase can reference.

### Phase 2 — Orchestrator handoff wiring (builder scope: `app/`)

1. Add an `upstream_output: str = ""` parameter to `build_role_prompt()` in
   `orchestrator.py`.  When non-empty, inject it as a `## Prior phase output`
   section in the assembled prompt.

2. In `app.py` `_advance_pipeline()`, after a worker completes, capture its
   `summary` (or the last N lines of `workflow_log`) and store it on the next
   worker as `upstream_summary`.

3. When spawning the next worker, rebuild or patch its `task_prompt` to include
   the upstream output.  The simplest approach: store the original
   `JunieLaunchSpec`-style data on `WorkerSession` and regenerate the prompt
   at advancement time.

### Phase 3 — Fix branch model (builder scope: `app/`)

Replace `_post_pipeline_git_flow` to use the shared `agent` branch:
- Remove `ocha/<task-id>` branch creation
- Stage + commit on `agent`
- Fetch + rebase before push
- Keep PR creation but base it on `agent` → `main`

### Phase 4 — Tests (reviewer scope: `tests/`)

- Test that `build_role_prompt()` with `upstream_output` injects the section
- Test that `_advance_pipeline` captures and forwards summary
- Test role `.md` files contain the expected contract sections

---

## Safe partitioning for parallel worktrees

| Role | Owned directory | Scope |
|------|----------------|-------|
| **Coordinator** | `docs/` | This brief (done) |
| **Lead** | `planning/` | Break the phases above into discrete builder tasks |
| **Builder** | `app/` | Role prompts, orchestrator handoff, branch fix |
| **Reviewer** | `tests/` + read `app/` | Validate changes, add test coverage |

The builder should not edit `docs/` or `planning/`.
The reviewer should not rewrite `app/` source — only add tests in `tests/`.

---

## Execution rules reminder

- Stay on the `agent` branch — no branch-per-agent.
- Each agent works in its own worktree under `.worktrees/`.
- Prefer changes inside the assigned owned directory.
- Summarize results so the TUI can surface a short workflow event.

---

## Coordinator summary (for TUI event)

> Produced execution brief for workflow refinement.  Core finding: the 4-phase
> pipeline exists but lacks artifact handoff — each role runs in isolation.
> Recommended fix: enrich role prompts with input/output contracts, wire
> `upstream_output` through `build_role_prompt`, and capture completed worker
> summaries in `_advance_pipeline`.  Four phases scoped for lead breakdown.
