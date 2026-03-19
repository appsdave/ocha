# T-001 Execution Brief — Line one Line two Line three

**Coordinator:** S-001-01  
**Branch:** agent  
**Date:** 2026-03-19

---

## Goal (refined)

The operator submitted a three-line plaintext task: "Line one / Line two /
Line three." This contains no actionable code request — it is a **smoke-test
prompt** that validates the ocha multi-agent pipeline can accept a trivial
multi-line task, route it through the coordinator role, and produce a
well-formed execution brief without errors. The downstream roles (lead,
builder, reviewer) should recognise this as a no-op task and confirm that the
pipeline completes gracefully with no code changes required.

---

## Relevant files

### Must-read for every downstream agent

| File | Why |
|------|-----|
| `app/orchestrator.py` | `summarize_task()` normalises multi-line input into a single-line title — verify it handles the three-line input correctly |
| `app/app.py` | `_launch_task_from_prompt` and `_advance_pipeline` — confirm the pipeline advances through all four roles even when no code changes are needed |
| `app/state.py` | `OchaTask` / `WorkerSession` — data model carries the task through each phase |
| `app/roles/*.md` | Role prompt templates — each role should gracefully handle a no-op task |

### Secondary context

| File | Why |
|------|-----|
| `tests/test_orchestrator.py` | Existing tests; a multi-line no-op task case could be added here |
| `README.md` | Documents the pipeline and keybindings |
| `docs/T-001-execution-brief.md` | Prior T-001 brief for reference on format |

---

## Recommended changes

### Phase 0 — Validation (no code changes)

1. **Confirm `summarize_task()` handles the input correctly.**
   The three-line input `"Line one\nLine two\nLine three"` should be
   normalised to the title `"Line one Line two Line three"` (under 72 chars,
   no truncation). This already works per the current implementation
   (`" ".join(user_task.split())`).

2. **Confirm `build_launch_specs()` produces four valid specs.**
   Each spec should contain the full multi-line operator task in its prompt
   body, with correct `task_id`, `session_id`, `worktree_path`, and
   `owned_directory` values.

3. **Confirm `persist_task_prompt()` writes the raw multi-line text.**
   The file `.ocha/tasks/T-001/prompt.md` should contain the original
   three-line text verbatim.

### Phase 1 — Pipeline completion (no code changes expected)

4. **Lead should recognise this as a no-op task** and produce an empty or
   minimal sub-task list (e.g., "No builder work required").

5. **Builder should skip** — no files to edit, no tests to write.

6. **Reviewer should confirm** the pipeline completed cleanly and no
   unintended changes were made.

### Phase 2 — Optional hardening

7. *(Optional)* Add a test case in `tests/test_orchestrator.py` that
   exercises `build_launch_specs()` with a multi-line trivial prompt and
   asserts the title, spec count, and prompt contents are correct.

---

## Safe partitioning

| Role | Owned directory | Scope |
|------|----------------|-------|
| **Coordinator** | `docs/` | This brief (context gathering only) |
| **Lead** | `planning/` | Recognise no-op; produce minimal or empty sub-task plan |
| **Builder** | `app/` | No changes expected; skip gracefully |
| **Reviewer** | `tests/` | Optionally add a multi-line smoke-test case |

All agents stay on the shared `agent` branch. No branch-per-agent.

---

## Summary for TUI event

> **T-001 coordinator complete.** Trivial smoke-test task identified. No code
> changes required. Pipeline should advance through lead → builder → reviewer
> as a no-op validation run.
