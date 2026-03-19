# T-001 Execution Brief — Line one Line two Line three

**Coordinator:** S-001-01  
**Branch:** agent  
**Date:** 2026-03-19

---

## Goal (refined)

The operator submitted a three-line prompt ("Line one / Line two / Line three")
that exercises the multi-line task-creation path end-to-end.  This is a
lightweight smoke-test task: the prompt itself carries no implementation
instructions.  The coordinator's job is to confirm that the multi-line prompt
was accepted, persisted, and injected into the role prompts without corruption,
and to produce this execution brief so downstream roles have a clear (if
minimal) brief to act on.  No code changes are expected from this task.

---

## Current state

| Layer | Status | Notes |
|-------|--------|-------|
| Multi-line prompt acceptance | ✓ Working | `summarize_task()` collapses newlines → title "Line one Line two Line three" |
| Prompt persistence | ✓ Working | `persist_task_prompt()` writes to `.ocha/tasks/T-001/prompt.md` |
| Role prompt injection | ✓ Working | `build_role_prompt()` embeds the full multi-line `user_task` in the `## Operator task` section |
| Pipeline sequencing | ✓ Working | Coordinator starts as RUNNING; lead, builder, reviewer are QUEUED |

---

## Relevant files

| File | Role | Action |
|------|------|--------|
| `app/orchestrator.py` | All | Read — `summarize_task()` (line 244), `build_role_prompt()` (line 80), `launch_task()` (line 192) |
| `app/state.py` | All | Read — `AppState`, `OchaTask`, `WorkerSession` data model |
| `app/app.py` | Lead / Builder | Read — TUI task-launch flow, `NewTaskOverlay` |
| `tests/test_orchestrator.py` | Reviewer | Read — existing multi-line and edge-case tests |
| `tests/test_app.py` | Reviewer | Read — TUI smoke tests |
| `docs/T-001-workflow-smoke-test-brief.md` | Coordinator | This brief (done) |

---

## Recommended changes

### Phase 1 — Verification only (no code changes expected)

1. **Lead**: Confirm the operator prompt reached all four role prompts intact
   (newlines preserved in the `## Operator task` section).
2. **Builder**: No implementation work — the prompt is a placeholder.  If any
   downstream role detects a real defect (e.g., newline mangling), file it as
   a follow-up task.
3. **Reviewer**: Run the existing test suite (`pytest tests/`) and verify all
   tests pass.  Confirm `summarize_task("Line one\nLine two\nLine three")`
   produces `"Line one Line two Line three"` (whitespace-collapsed, ≤72 chars).

---

## Safe partitioning

| Role | Owned directory | Scope |
|------|----------------|-------|
| **Coordinator** | `docs/` | This brief; no other changes |
| **Lead** | `planning/` | Confirm scope is verification-only; no subtask breakdown needed |
| **Builder** | `app/`, `tests/` | No changes expected for this task |
| **Reviewer** | `tests/` (read) | Run test suite, verify multi-line prompt round-trip |

All workers stay on the shared `agent` branch.  Worktree isolation
(`.worktrees/t-001-{role}`) provides the safety boundary.

---

## Branch rule

All workers stay on the shared `agent` branch.  No branch-per-agent.

---

## Success criteria

- The multi-line operator prompt is persisted to `.ocha/tasks/T-001/prompt.md`
  with newlines intact.
- `summarize_task()` produces a sensible single-line title from the multi-line
  input.
- All four role prompts contain the full operator text in `## Operator task`.
- All existing tests pass (`pytest tests/`).
- No code changes are required or introduced.

---

## Coordinator summary (for TUI event)

> Produced execution brief for smoke-test task "Line one Line two Line three".
> The multi-line prompt was accepted, persisted, and injected into role prompts
> correctly.  No code changes needed — this is a verification-only task.
> Downstream roles should confirm the test suite passes and the prompt
> round-trips without corruption.
