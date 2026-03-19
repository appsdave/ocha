# T-001 — Ship prompt-based task creation

**Coordinator:** S-001-01
**Branch:** agent
**Date:** 2026-03-19

---

## Goal (refined)

Make the prompt-based task creation flow production-ready.  The end-to-end
plumbing already works: `NewTaskOverlay` → `launch_task()` → role prompts →
Junie spawn → pipeline advance with upstream handoff → git push / PR.  What
remains is upgrading the input UX from a single-line `Input` to a multi-line
`TextArea` (the README already documents `Ctrl+S` to submit and `Enter` for
newline, but the code still uses a single-line widget), adding lightweight
disk persistence so prompts survive a TUI restart, hardening edge cases, and
covering the new behaviour with tests.

---

## Current state (what already works)

| Layer | Status | Location |
|---|---|---|
| `NewTaskOverlay` modal | Single-line `Input`, submits on Enter, dismisses on Esc | `app/app.py:190-226` |
| `launch_task()` | Builds 4 role-backed `WorkerSession` objects, first worker starts as RUNNING | `app/orchestrator.py:179-226` |
| `build_role_prompt()` | Injects role markdown + runtime context + operator task; supports `upstream_output` | `app/orchestrator.py:80-133` |
| `_spawn_junie_workers` / `_advance_pipeline` | Spawns `junie` CLI, streams output, advances pipeline sequentially with upstream handoff | `app/app.py:481-622` |
| `_rebuild_prompt_with_upstream` | Rebuilds next worker's prompt with prior phase output | `app/app.py:624-645` |
| `_post_pipeline_git_flow` | Commits on `agent`, rebases, pushes, opens PR via `gh` | `app/app.py:647-728` |
| `ocha launch <task>` CLI | Dry-run preview of role launches without TUI | `app/cli.py:97-103` |
| Upstream handoff tests | `test_build_role_prompt_with_upstream_output_injects_section` | `tests/test_orchestrator.py:68-88` |
| Role contract tests | Verify each role `.md` has input/output contracts | `tests/test_orchestrator.py:91-119` |
| TUI app tests | New-task flow, clear-finished, sidebar selection | `tests/test_app.py` |

---

## Relevant files

| File | Role | Action |
|------|------|--------|
| `app/app.py` | Builder | Edit — replace `Input` with `TextArea` in `NewTaskOverlay`, update bindings |
| `app/orchestrator.py` | Builder | Edit — add `persist_task_prompt()` to write prompt to disk before launch |
| `app/state.py` | Builder | Read — understand `AppState` / `OchaTask` shape; minor edit if persistence needs a field |
| `app/cli.py` | Builder | Read — verify `ocha launch` still works after changes |
| `app/roles/coordinator.md` | Read-only | Already has input/output contract |
| `app/roles/lead.md` | Read-only | Already has input/output contract |
| `app/roles/builder.md` | Read-only | Already has input/output contract |
| `app/roles/reviewer.md` | Read-only | Already has input/output contract |
| `tests/test_orchestrator.py` | Builder | Edit — add multi-line prompt and `summarize_task` edge-case tests |
| `tests/test_app.py` | Builder | Edit — update `test_new_task_uses_prompt_input` for `TextArea` + `Ctrl+S` |
| `README.md` | Coordinator | Edit — update keybinding table if bindings change |
| `docs/T-001-execution-brief.md` | Coordinator | This brief (done) |

---

## Gaps to close

### Gap 1 — Multi-line prompt input (builder → `app/app.py`)

The README (lines 136-139) documents `Ctrl+S` to submit and `Enter` for
newline, but the current `NewTaskOverlay` uses Textual's single-line `Input`
widget with `on_input_submitted`.  Replace `Input` with `TextArea`:

- Bind `Ctrl+S` (or a submit button) → submit.
- Keep `Esc` → cancel.
- `Enter` becomes a normal newline inside `TextArea`.
- Update the hint bar text to match the actual bindings.
- Ensure the overlay cannot be stacked (pressing `n` twice should not open two).

### Gap 2 — Persist task prompt to disk (builder → `app/orchestrator.py`)

Write the user prompt to `.ocha/tasks/T-NNN/prompt.md` before spawning
workers.  This gives:

- Crash recovery — the prompt is not lost if the TUI exits.
- An audit trail per task.
- A file the coordinator/lead roles can reference from their worktree.

Implementation: add a `persist_task_prompt(task_id, user_task, project_path)`
function in `orchestrator.py` and call it from `launch_task()`.

### Gap 3 — Input validation hardening (builder → `app/app.py`)

- Trim whitespace; reject blank prompts (already done for `Input`, must be
  re-verified after switching to `TextArea`).
- Cap prompt length or warn on very long input — the prompt is passed as a
  CLI `--task` argument, so extremely long input can hit OS argument limits.
- Prevent double-open of the overlay.

### Gap 4 — Add test coverage (builder → `tests/`)

- **`test_orchestrator.py`**: Add a test that round-trips a multi-line prompt
  through `build_launch_specs` and verifies it appears in each role prompt
  intact.
- **`test_orchestrator.py`**: Verify `summarize_task()` handles multi-line
  input gracefully (it joins on whitespace, which should be fine — confirm
  with a test).
- **`test_app.py`**: Update `test_new_task_uses_prompt_input` for `TextArea`
  widget and `Ctrl+S` submit binding.  Add a test that `Esc` cancels without
  creating a task.

### Gap 5 — README keybinding update (coordinator → `README.md`)

- Update the keybinding table (lines 126-139) to match the final submit
  binding once Gap 1 is implemented.
- Add a short "Creating a task" workflow section if one doesn't exist.

---

## Recommended changes (grouped by phase)

### Phase 1 — Input UX upgrade (builder)

1. In `app/app.py`, replace `Input` with `TextArea` in `NewTaskOverlay.compose()`.
2. Remove `on_input_submitted` handler; add a `Ctrl+S` binding that calls `_submit()`.
3. Update `_submit()` to read from `TextArea` value instead of `Input`.
4. Update hint bar text: `"ctrl+s submit  esc cancel"`.

### Phase 2 — Disk persistence (builder)

5. Add `persist_task_prompt(task_id: str, user_task: str, project_path: Path)` in `orchestrator.py`.
6. Call it at the start of `launch_task()`, writing to `.ocha/tasks/{task_id}/prompt.md`.
7. Create parent directories with `mkdir(parents=True, exist_ok=True)`.

### Phase 3 — Validation hardening (builder)

8. In the `TextArea`-based `_submit()`, strip and reject blank input.
9. Add a length guard (warn or truncate above ~100 KB).
10. Guard against double-open of `NewTaskOverlay`.

### Phase 4 — Tests (builder)

11. Add `test_multiline_prompt_preserved_in_launch_specs` to `test_orchestrator.py`.
12. Add `test_summarize_task_multiline` to `test_orchestrator.py`.
13. Update `test_new_task_uses_prompt_input` in `test_app.py` for `TextArea` + `Ctrl+S`.
14. Add `test_new_task_cancel` in `test_app.py`.

### Phase 5 — Docs (coordinator or reviewer)

15. Update `README.md` keybinding table.

---

## Safe partitioning

| Role | Owned directory | Key files to touch |
|------|----------------|--------------------|
| **Coordinator** | `docs/` | This brief; `README.md` keybinding docs |
| **Lead** | `planning/` | Subtask breakdown (if needed) |
| **Builder** | `app/`, `tests/` | `app/app.py`, `app/orchestrator.py`, `tests/test_orchestrator.py`, `tests/test_app.py` |
| **Reviewer** | `app/` (read) | Review builder changes, run full test suite, verify TUI flow |

The builder should not edit `docs/`.  The reviewer should not rewrite `app/`
source — only verify and add tests in `tests/` if gaps remain.

---

## Branch rule

All workers stay on the shared `agent` branch.  No branch-per-agent.
Worktree isolation (`{project}/.worktrees/t-001-{role}`) provides the safety
boundary.

---

## Suggested execution order

1. **Coordinator** (this session) — produce this brief ✓
2. **Lead** — confirm or refine the gap list into concrete subtasks
3. **Builder** — implement gaps 1–4 in order; run tests after each
4. **Reviewer** — verify builder output, run `pytest`, confirm the TUI
   `n` → prompt → `Ctrl+S` submit flow works

---

## Success criteria

- Pressing `n` in the TUI opens a multi-line prompt overlay.
- `Enter` inserts a newline; `Ctrl+S` submits; `Esc` cancels.
- Submitting a prompt creates a task with 4 role-backed workers.
- The prompt is persisted to `.ocha/tasks/T-NNN/prompt.md`.
- All existing tests pass; new tests cover multi-line prompts and edge cases.
- `ocha launch "some task"` still works from the CLI.

---

## Coordinator summary (for TUI event)

> Produced execution brief for prompt-based task creation.  The end-to-end
> pipeline and upstream handoff are already wired.  Five gaps remain:
> (1) upgrade `NewTaskOverlay` from single-line `Input` to `TextArea`,
> (2) persist prompts to `.ocha/tasks/`, (3) harden input validation,
> (4) add multi-line and edge-case test coverage, (5) update README
> keybindings.  Five phases scoped for lead breakdown.
