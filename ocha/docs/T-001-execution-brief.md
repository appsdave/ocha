# T-001 — Ship prompt-based task creation

## Goal

Make the existing prompt-based task creation flow production-ready. The
plumbing already works end-to-end (`NewTaskOverlay` → `launch_task()` →
role prompts → Junie spawn → pipeline advance → git push / PR). What
remains is hardening the input UX, adding lightweight persistence so
tasks survive a TUI restart, and confirming the full cycle with tests.

## Current state (what already works)

| Layer | Status |
|---|---|
| `NewTaskOverlay` modal (`app/app.py:190-226`) | Single-line `Input`, submits on Enter, dismisses on Esc |
| `launch_task()` (`app/orchestrator.py:166-213`) | Builds 4 role-backed `WorkerSession` objects, first worker starts as RUNNING |
| `build_role_prompt()` (`app/orchestrator.py:80-120`) | Injects role markdown + runtime context + operator task |
| `_spawn_junie_workers` / `_advance_pipeline` (`app/app.py:481-594`) | Spawns `junie` CLI, streams output, advances pipeline sequentially |
| `_post_pipeline_git_flow` (`app/app.py:596-664`) | Commits, pushes `agent` branch, opens PR via `gh` |
| `ocha launch <task>` CLI (`app/cli.py:97-103`) | Dry-run preview of role launches without TUI |

## Gaps to close

### 1. Multi-line prompt input (builder — `app/app.py`)

The README documents `Ctrl+S` to submit and `Enter` for newline, but the
current overlay uses Textual's single-line `Input` widget with
`on_input_submitted`. Replace `Input` with `TextArea` (or Textual's
multi-line equivalent) so operators can write richer task descriptions.

- Keep `Esc` → cancel, `Ctrl+S` or a submit button → submit.
- Update the hint bar text to match the new bindings.

### 2. Persist task prompt to disk before launch (builder — `app/orchestrator.py` or `app/state.py`)

Write the user prompt to `.ocha/tasks/T-NNN/prompt.md` (or similar)
before spawning workers. This gives:

- crash recovery (the prompt is not lost if the TUI exits)
- an audit trail per task
- a file the coordinator/lead roles can reference from their worktree

Keep it simple: create the directory and write one file. No database.

### 3. Input validation and edge-case handling (builder — `app/app.py`)

- Trim whitespace; reject blank prompts (already done, but verify after
  switching to `TextArea`).
- Cap prompt length or warn on very long input (avoid blowing CLI
  argument limits since the prompt is passed as `--task` arg).
- Ensure the overlay cannot be stacked (pressing `n` twice).

### 4. Test coverage (builder — `tests/`)

- **Unit**: `test_orchestrator.py` — add a test that round-trips a
  multi-line prompt through `build_launch_specs` and verifies it appears
  in each role prompt intact.
- **Unit**: verify `summarize_task()` handles multi-line input gracefully
  (it joins on whitespace, which should be fine — confirm with a test).
- **Integration / app test**: `test_app.py` — if Textual `pilot` tests
  exist or can be added cheaply, test that pressing `n`, typing a prompt,
  and pressing the submit binding results in a new task in `app.state`.

### 5. README / docs update (coordinator — `docs/`)

- Update the keybinding table in `README.md` to reflect the final
  submit binding (`Ctrl+S` vs `Enter`).
- Add a short "Creating a task" section if one doesn't exist.

## File ownership map

| Role | Owned directory | Key files to touch |
|---|---|---|
| **Coordinator** | `docs/` | This brief; `README.md` keybinding docs |
| **Lead** | `planning/` | Subtask breakdown (if needed) |
| **Builder** | `app/` | `app/app.py`, `app/orchestrator.py`, `app/state.py`, `tests/test_orchestrator.py`, `tests/test_app.py` |
| **Reviewer** | `app/` | Review builder changes, run full test suite |

## Branch rule

All workers stay on the shared `agent` branch. No branch-per-agent.
Worktree isolation (`{project}/.worktrees/t-001-{role}`) provides the
safety boundary.

## Suggested execution order

1. **Coordinator** (this session) — produce this brief ✓
2. **Lead** — confirm or refine the gap list above into concrete subtasks
3. **Builder** — implement gaps 1–4 in order; run tests after each
4. **Reviewer** — verify the builder output, run `pytest`, confirm the
   TUI launches and the `n` → prompt → submit flow works

## Success criteria

- Pressing `n` in the TUI opens a multi-line prompt overlay.
- Submitting a prompt creates a task with 4 role-backed workers.
- The prompt is persisted to `.ocha/tasks/T-NNN/prompt.md`.
- All existing tests pass; new tests cover multi-line prompts.
- `ocha launch "some task"` still works from the CLI.
