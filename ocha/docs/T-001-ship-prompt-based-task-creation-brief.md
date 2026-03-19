# T-001 — Ship Prompt-Based Task Creation

> Coordinator brief for downstream lead, builder, and reviewer sessions.
> Updated: 2026-03-19T22:41

---

## Execution Brief

### 1. Goal (refined)

Ocha already has the internal machinery to turn an operator prompt into a
four-phase Junie pipeline (coordinator → lead → builder → reviewer).  The TUI
wires this end-to-end (`n` key → `NewTaskOverlay` → `launch_task()` →
`_spawn_junie_workers`), but the **CLI path is incomplete**: `ocha launch`
prints specs without executing them.  Additionally, several reliability gaps
exist: `status.json` is never updated during the task lifecycle,
`summarize_task()` produces a naive 72-char truncation instead of a meaningful
title, and the CLI `launch` path accepts empty prompts silently.  The task is
to ship a proper **`ocha task <prompt>`** CLI entry-point that persists the
prompt, builds launch specs, spawns the sequential Junie pipeline headlessly,
streams progress to stdout, updates `status.json`, and exits with an
appropriate code — making prompt-based task creation reliable and usable
outside the TUI for CI, scripts, and `ocha` self-calls.

### 2. Relevant files

| File | Role | Read / Edit | Notes |
|------|------|-------------|-------|
| `app/cli.py` | CLI parser & `main()` dispatch | **Edit** | Add `task` subcommand; add empty-prompt validation to `launch` |
| `app/orchestrator.py` | `build_launch_specs`, `launch_task`, `persist_task_prompt`, `summarize_task` | **Edit** | Extract headless runner; improve `summarize_task`; add empty-prompt guard |
| `app/state.py` | `AppState`, `WorkerSession`, `WorkerStatus` | **Edit** | Add `persist_status()` for `.ocha/status.json` updates |
| `app/app.py` | TUI `_spawn_junie_workers`, `_advance_pipeline` | **Edit** | Refactor to delegate to shared runner; call `persist_status` on transitions |
| `app/roles/*.md` | Role prompt templates | **Read** | Verify accuracy; no edits expected |
| `tests/test_cli.py` | CLI tests | **Edit** | Add tests for `ocha task`; add empty-prompt rejection test |
| `tests/test_orchestrator.py` | Orchestrator tests | **Edit** | Add headless runner tests; improved `summarize_task` tests |
| `tests/test_app.py` | TUI/app tests | **Read / Edit** | Verify ghost-task prevention for empty/null prompts |
| `pyproject.toml` | Entry-point / deps | **Read** | Verify `[project.scripts]` |
| `.ocha/status.json` | Runtime state | **Edit** (via code) | Must be updated on every task state transition |
| `docs/` | Briefs & documentation | **Edit** | This brief |

### 3. Recommended changes

**Phase 1 — Validation & title improvements (builder: `app/`)**

1. **`app/orchestrator.py` — `summarize_task()`**: Replace naive 72-char
   truncation with first-sentence extraction: split on `.` or `\n`, take the
   first non-empty segment, then truncate to 72 chars.  This gives
   human-readable titles in the sidebar and CLI output.
2. **`app/orchestrator.py` — `launch_task()`**: Raise `ValueError` when
   `user_task.strip()` is empty so callers get a clear error instead of an
   "Untitled task" ghost row.
3. **`app/cli.py` — `ocha launch`**: Validate that `args.task.strip()` is
   non-empty before calling `build_launch_specs`; exit with a descriptive
   error message.

**Phase 2 — Headless pipeline runner (builder: `app/`)**

4. Extract the pipeline execution logic from `OchaApp._spawn_junie_workers` /
   `_advance_pipeline` / `_run_junie_for_worker` into a standalone async
   function in a new module `app/runner.py` (or as a top-level function in
   `orchestrator.py`).  This function should:
   - Accept an `OchaTask` (or list of `JunieLaunchSpec`).
   - Run each worker sequentially (respecting the existing pipeline order).
   - Inject upstream output into the next worker's prompt via
     `build_role_prompt(..., upstream_output=...)`.
   - Stream status lines to a callback or stdout.
   - Return a result summary (pass/fail per worker, overall exit code).
5. The TUI (`app.py`) should be refactored to delegate to this shared runner
   so there is one pipeline implementation, not two.

**Phase 3 — CLI subcommand & status persistence (builder: `app/`)**

6. Add an `ocha task` subcommand to `cli.py`:
   ```
   ocha task "Ship prompt based task creation"
   ocha task --project ~/src/myrepo "Fix the login bug"
   ```
   - Calls `persist_task_prompt` + `build_launch_specs`.
   - Invokes the headless runner from Phase 2.
   - Prints per-worker progress to stdout.
   - Exits 0 on full success, 1 on any worker failure.
7. Keep the existing `ocha launch` as a dry-run / spec-printer (no behaviour
   change).
8. **`app/state.py` — add `persist_status(state, path)`**: Serialize
   `AppState` (task list, statuses, timestamps) to `.ocha/status.json` so the
   TUI and external tools can read current progress.
9. **`app/app.py` — call `persist_status`**: After `launch_task`, after every
   `_advance_pipeline` transition, and after kill/clear — write the updated
   status to disk.

**Phase 4 — Tests (builder/reviewer: `tests/`)**

10. Add unit tests for the new runner:
    - Mock `junie` subprocess; verify sequential execution order.
    - Verify upstream output injection between phases.
    - Verify exit-code mapping.
11. Add CLI integration tests for `ocha task`:
    - Parser accepts prompt + `--project`.
    - `main(["task", "..."])` calls the runner (mocked).
    - `ocha launch ""` and `ocha task ""` produce non-zero exits.
12. Add tests for improved `summarize_task` and empty-prompt rejection.
13. Verify `_launch_task_from_prompt(None)` and
    `_launch_task_from_prompt("")` do not create ghost tasks.
14. Ensure all existing tests still pass (`python -m pytest tests/`).

**Phase 5 — Documentation (coordinator/reviewer: `docs/`)**

15. Update or create a brief documenting the new `ocha task` subcommand and
    its interaction with the pipeline.

### 4. Safe partitioning

| Owned directory | Role | Scope |
|-----------------|------|-------|
| `docs/` | **Coordinator** | This execution brief; post-ship documentation |
| `planning/` | **Lead** | Task plan derived from this brief |
| `app/` | **Builder** | `runner.py` (new), `cli.py` (edit), `orchestrator.py` (edit), `state.py` (edit), `app.py` (refactor) |
| `tests/` | **Builder** | `test_cli.py` (edit), `test_orchestrator.py` (edit), `test_runner.py` (new) |
| `app/`, `tests/` | **Reviewer** | Code review of builder's changes; no overlapping edits during build phase |

> All workers stay on the shared `agent` branch.  The builder owns all code
> and test changes; the reviewer reads but does not edit the same files
> concurrently.  The coordinator's output (this brief) lands in `docs/` and
> is consumed by the lead before the builder starts.

---

*Generated by ocha coordinator · T-001 · S-001-01*
