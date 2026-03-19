# T-001 Coordinator Brief — Line one Line two Line three

**Coordinator:** S-001-01
**Branch:** agent
**Date:** 2026-03-19

---

## Context

The operator submitted a three-line prompt:

> Line one
> Line two
> Line three

This is a placeholder / smoke-test task. It contains no actionable feature
request, bug report, or refactoring directive. The coordinator's job is still
to produce a well-formed execution brief so the downstream pipeline
(lead → builder → reviewer) can exercise its full path, even when the input
is trivial.

---

## Execution Brief

### Goal (refined)

Validate the end-to-end ocha task pipeline using a minimal multi-line prompt.
Because the operator prompt carries no concrete implementation intent, the
downstream roles should treat this as a **dry-run / no-op pipeline
exercise**: the lead confirms there are no actionable sub-tasks to generate,
the builder confirms there is nothing to build, and the reviewer confirms the
pipeline completed gracefully with no regressions. This exercises the
multi-line prompt acceptance path (`NewTaskOverlay` → `launch_task` →
sequential pipeline advancement) without requiring any source-code changes.

### Relevant files

| File | Role | Why |
|------|------|-----|
| `app/orchestrator.py` | Lead, Builder | Builds role prompts and launch specs; confirm multi-line prompt flows through unchanged |
| `app/app.py` | Lead | `NewTaskOverlay`, `_launch_task_from_prompt`, `_advance_pipeline` — the live path this task exercises |
| `app/state.py` | Lead | `OchaTask` / `WorkerSession` data model — verify task state transitions |
| `app/roles/*.md` | Lead | Role prompt templates — ensure placeholder input doesn't violate any contract |
| `tests/test_orchestrator.py` | Reviewer | Existing orchestrator tests including multi-line prompt handling |
| `tests/test_app.py` | Reviewer | App-level tests: overlay UX, pipeline advancement |
| `.ocha/tasks/T-001/prompt.md` | Lead | Persisted prompt for this task — should contain the three-line input |

### Recommended changes

#### Phase 1 — Validation only (no source edits expected)

1. **Lead**: Confirm the three-line prompt was persisted correctly in `.ocha/tasks/T-001/prompt.md`.
2. **Lead**: Verify that `launch_task()` in `app/orchestrator.py` produces valid `JunieLaunchSpec` objects for a trivial prompt (no crash, no empty fields).
3. **Lead**: Declare zero builder sub-tasks — the prompt contains no implementation work.

#### Phase 2 — Review pass

1. **Reviewer**: Run the existing test suites (`tests/test_orchestrator.py`, `tests/test_app.py`) to confirm no regressions.
2. **Reviewer**: Verify that the pipeline handles a no-op task gracefully (all workers reach COMPLETED without errors).

### Safe partitioning

All agents share the `agent` branch. No source edits are expected for this
task, but the standard ownership boundaries apply:

| Role | Owned directory | Scope for this task |
|------|----------------|---------------------|
| **Coordinator** | `docs/` | This brief (done) |
| **Lead** | `planning/` | Confirm no sub-tasks needed; produce empty plan |
| **Builder** | `app/` | No changes — nothing to build |
| **Reviewer** | `tests/` | Run existing suites; confirm clean pass |

---

## Coordinator summary (for TUI event)

> Produced execution brief for T-001 "Line one Line two Line three".
> The operator prompt is a placeholder with no implementation intent.
> Downstream roles should treat this as a dry-run pipeline exercise:
> validate multi-line prompt acceptance, confirm no regressions, and
> complete gracefully with zero source changes.
