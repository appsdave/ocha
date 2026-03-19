# T-001 — Ship Prompt-Based Task Creation

> Coordinator: S-001-01 · Branch: `agent`

## Execution Brief

### 1. Goal (refined)

The TUI path for prompt-based task creation is functional: `NewTaskOverlay`
captures operator text, `launch_task()` builds per-role `JunieLaunchSpec`s,
worktrees are provisioned on the shared `agent` branch, Junie headless sessions
are spawned sequentially with upstream handoff, and `_post_pipeline_git_flow`
commits/pushes/opens a PR. However, the **CLI path is incomplete**: `ocha launch
"<task>"` only calls `build_launch_specs()` and prints specs to stdout — it does
not persist state, create worktrees, or execute workers. Additionally, the
execution logic (worktree creation, prompt writing, pipeline advancement) lives
exclusively inside the `OchaApp` Textual class and cannot be reused outside
the TUI.

"Ship prompt-based task creation" means:
1. Extract the shared execution logic into a reusable module.
2. Wire `ocha launch` to persist state and run the full pipeline.
3. Add state persistence (JSON serialization) so CLI and TUI share `.ocha/status.json`.
4. Harden edge cases, add tests, and document the feature.

### 2. Relevant files

| File | Role | Action |
|---|---|---|
| `app/cli.py` | builder | **Edit** — wire `launch` subcommand to persist state + execute workers |
| `app/orchestrator.py` | builder | **Edit** — `build_launch_specs`, `launch_task`, `persist_task_prompt`; add input validation |
| `app/state.py` | builder | **Edit** — add `to_dict()` / `from_dict()` for JSON persistence of `AppState` |
| `app/app.py` | builder | **Edit** — extract `_ensure_worktree`, `_write_prompt_file`, `_advance_pipeline` into shared module |
| `app/runner.py` | builder | **Create** — shared execution module (worktree, prompt write, pipeline run) used by both CLI and TUI |
| `app/roles/*.md` | — | Read-only; role prompt templates |
| `app/widgets.py` | reviewer | Read-only; TUI widgets |
| `.ocha/status.json` | builder | Runtime state file; CLI must read/write this |
| `tests/test_orchestrator.py` | builder | **Edit** — add edge-case + persistence round-trip tests |
| `tests/test_cli.py` | builder | **Edit** — add `launch` integration tests |
| `tests/test_app.py` | reviewer | Read — verify TUI still works after extraction |
| `pyproject.toml` | — | Read-only; confirm `app.roles` package-data |
| `docs/` | coordinator | **Write** — this brief |

### 3. Recommended changes

**Phase 1 — State persistence (builder)**

1. Add `AppState.to_dict()` and `AppState.from_dict()` (plus matching
   methods on `OchaTask` and `WorkerSession`) for JSON serialization.
2. Add `save_state(state, project_path)` / `load_state(project_path)` in
   `app/state.py` that read/write `.ocha/status.json`.
3. Have `launch_task()` in `orchestrator.py` call `save_state()` after
   appending the new task so the task is durable before any worker starts.

**Phase 2 — Extract shared execution logic (builder)**

4. Create `app/runner.py` with reusable functions extracted from `app.py`:
   - `ensure_worktree(worker, branch)` — create git worktree
   - `write_prompt_file(worker, project_path)` — write prompt to `.ocha/tasks/`
   - `run_junie_for_worker(worker, task, api_key)` — sync or async Junie execution
   - `advance_pipeline(task, run_fn)` — upstream handoff + next-worker start
5. Refactor `OchaApp` to delegate to `app/runner.py` (TUI wraps with async).

**Phase 3 — CLI launch execution (builder)**

6. In `app/cli.py`, extend `launch` subcommand to:
   - call `launch_task()` (not just `build_launch_specs()`),
   - persist state to `.ocha/status.json`,
   - create worktrees via `ensure_worktree()`,
   - sequentially execute each worker (stdin-piped prompt),
   - update worker status and advance pipeline with upstream handoff.
7. Add `--dry-run` flag (current print-only behavior preserved).
8. Add `--title` optional argument to override `summarize_task`.

**Phase 4 — Input validation & hardening (builder)**

9. In `build_launch_specs`, raise `ValueError` on empty/whitespace-only
   `user_task`.
10. In `NewTaskOverlay._submit`, add a minimum char-count guard (≥ 3).
11. Surface clear error when all worktree creations fail.

**Phase 5 — Tests (builder + reviewer)**

12. `test_orchestrator.py`: state persistence round-trip, empty prompt
    raises ValueError, `next_task_number` increments correctly.
13. `test_cli.py`: `ocha launch --dry-run "task"` prints specs,
    `ocha launch "task"` persists `.ocha/status.json` (mock Junie).
14. Reviewer verifies all existing tests still pass after refactor.

**Phase 6 — Documentation (coordinator)**

15. This execution brief (done).
16. Add "Prompt-based task creation" section to `README.md` covering
    `ocha launch` CLI and TUI `n`-key workflow.

### 4. Safe partitioning

| Owned directory | Role | Scope |
|---|---|---|
| `docs/` | coordinator | Execution brief, README updates |
| `planning/` | lead | Plan refinement, phase sequencing |
| `app/` | builder | All production code: new `runner.py`, edits to `cli.py`, `orchestrator.py`, `state.py`, `app.py` |
| `tests/` | builder | New and updated test files |
| `app/`, `tests/` | reviewer | Code review, test verification — no production writes |

All roles operate on the shared `agent` branch via isolated worktrees.
No branch-per-agent complexity. The builder owns the bulk of changes.
The key risk is the `app.py` refactor — extraction into `runner.py` must
preserve existing TUI behavior exactly.

---

*Generated by coordinator session S-001-01 for task T-001.*
