# T-001 Execution Brief — Smoke-test: "Line one Line two Line three"

**Coordinator:** S-001-01
**Branch:** agent
**Date:** 2026-03-19

---

## Goal (refined)

The operator submitted a three-line plain-text prompt ("Line one / Line two /
Line three") with no actionable coding request.  This is a **pipeline
smoke-test**: the goal is to verify that the ocha orchestration pipeline
(coordinator → lead → builder → reviewer) can accept a multi-line prompt,
persist it to disk, generate role-specific headless Junie commands, and advance
through each phase without error.  No source-code changes to the project are
required.

---

## Relevant files

| File | Role | Action |
|------|------|--------|
| `app/orchestrator.py` | Lead / Builder | Read — verify `launch_task` handles multi-line input correctly |
| `app/state.py` | Lead | Read — confirm `OchaTask` / `WorkerSession` shape stores full prompt |
| `app/roles/coordinator.md` | Coordinator | Read — this role template was used to generate the current brief |
| `app/roles/lead.md` | Lead | Read — downstream role will receive this brief |
| `app/roles/builder.md` | Builder | Read — no code changes expected |
| `app/roles/reviewer.md` | Reviewer | Read — verify pipeline completes cleanly |
| `.ocha/tasks/T-001/prompt.md` | All | Read — confirm the operator prompt was persisted |
| `tests/test_orchestrator.py` | Reviewer | Run — ensure existing multi-line prompt tests still pass |
| `tests/test_app.py` | Reviewer | Run — ensure pipeline handoff tests still pass |
| `docs/T-001-line-one-two-three-smoke-brief.md` | Coordinator | Write — this brief |

---

## Recommended changes

### Phase 1 — Validation only (no code changes)

1. **Lead**: Confirm no subtasks are needed — the prompt contains no coding
   instructions.  Produce a short acknowledgement that the pipeline is being
   exercised as a smoke test.
2. **Builder**: No-op.  No files to create or modify.  If the pipeline still
   spawns a builder session, it should complete immediately with a summary
   stating no changes were made.
3. **Reviewer**: Run `pytest` to confirm the existing 43+ tests still pass.
   Verify the prompt was persisted to `.ocha/tasks/T-001/prompt.md` with the
   correct multi-line content.

### Phase 2 — (none)

No follow-up phase required.  This task is complete once the pipeline has run
end-to-end without error.

---

## Safe partitioning

| Role | Owned directory | Notes |
|------|----------------|-------|
| **Coordinator** | `docs/` | This brief (done) |
| **Lead** | — | Read-only; no subtask breakdown needed |
| **Builder** | — | No-op; no files to touch |
| **Reviewer** | `tests/` (read) | Run existing test suite; no new tests needed |

No overlapping edits are possible because no code changes are being made.

---

## Branch rule

All workers stay on the shared `agent` branch.  No branch-per-agent.

---

## Success criteria

- The multi-line prompt was accepted and persisted to disk.
- The coordinator produced this execution brief.
- The pipeline advanced through all four phases without error.
- All existing tests pass.

---

## Coordinator summary (for TUI event)

> Smoke-test task: operator submitted "Line one / Line two / Line three" with
> no coding intent.  Coordinator produced execution brief confirming this is a
> pipeline validation run.  No code changes required.  Downstream roles should
> complete as no-ops; reviewer should run existing tests to confirm stability.
