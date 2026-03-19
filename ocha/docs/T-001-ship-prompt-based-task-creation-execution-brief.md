# T-001 Execution Brief — Ship Prompt-Based Task Creation

> Produced by: coordinator · session S-001-01 · branch `agent`
> Updated: 2026-03-19

---

## Goal (refined)

Ocha's four-phase Junie pipeline (coordinator → lead → builder → reviewer) is
fully wired inside the TUI: press `n`, type a prompt, and `NewTaskOverlay` →
`launch_task()` → `_spawn_junie_workers()` → `_advance_pipeline()` runs it
end-to-end.  However the **CLI path is incomplete** — `ocha launch` only
prints `JunieLaunchSpec` objects to stdout without persisting state or spawning
workers.  To "ship prompt-based task creation" we must:

1. **Extract the pipeline runner** out of `OchaApp` into a reusable module so
   both TUI and CLI share one implementation.
2. **Add `ocha run <prompt>`** as a headless CLI entry-point that persists the
   prompt, spawns workers sequentially, streams progress to stdout, and exits
   with an appropriate code.
3. **Harden prompt input** — support `--file` / stdin, validate length and
   emptiness in one shared `load_prompt()` utility used by both TUI and CLI.
4. **Add tests** covering the new runner, CLI command, and prompt validation
   edge cases.

All work stays on the shared `agent` branch.

---

## Relevant files

| File | Role | Action |
|---|---|---|
| `app/orchestrator.py` | builder | **Edit** — add `load_prompt()` validator; optionally host the extracted runner |
| `app/runner.py` *(new)* | builder | **Create** — async pipeline runner extracted from `OchaApp` |
| `app/cli.py` | builder | **Edit** — add `run` subcommand; add `--file` to `launch` |
| `app/app.py` | builder | **Edit** — refactor `_spawn_junie_workers` / `_advance_pipeline` to delegate to `runner.py` |
| `app/state.py` | — | **Read** — `AppState`, `OchaTask`, `WorkerSession` contracts (no changes expected) |
| `app/widgets.py` | — | **Read** — verify pane refresh after task creation (no changes expected) |
| `app/roles/*.md` | — | **Read** — role prompt templates (no changes) |
| `tests/test_orchestrator.py` | builder | **Edit** — add `load_prompt` edge-case tests |
| `tests/test_cli.py` | builder | **Edit** — add `run` parser + dispatch tests |
| `tests/test_runner.py` *(new)* | builder | **Create** — runner unit tests (mock Junie subprocess) |
| `pyproject.toml` | — | **Read** — entry-point already wired, no change needed |
| `README.md` | lead | **Edit** — add "Creating a task" usage section |

---

## Recommended changes

### Phase 1 — Extract pipeline runner (builder, `app/`)

1. **`app/runner.py`** *(new)*: Move `_spawn_junie_workers`, `_advance_pipeline`,
   `_run_junie_for_worker`, `_rebuild_prompt_with_upstream`, and
   `_load_junie_api_key` out of `OchaApp` into a standalone async runner.
   - Accept an `OchaTask` + an async `spawn_fn` callback (real subprocess in
     production, stub in tests).
   - Run workers sequentially, injecting upstream output via
     `build_role_prompt(..., upstream_output=...)`.
   - Yield structured status events (`worker_started`, `line`, `worker_done`,
     `pipeline_done`) so callers can render progress however they want.
   - Return a result summary (pass/fail per worker, overall exit code).

2. **`app/app.py`**: Refactor `_launch_task_from_prompt` and
   `_spawn_junie_workers` to delegate to the shared runner, keeping only
   TUI-specific refresh/notification logic in the app.

### Phase 2 — CLI `ocha run` command (builder, `app/`)

3. **`app/cli.py`**: Register a new `run` subcommand:
   ```
   ocha run "Ship prompt based task creation"
   ocha run --file prompt.md --project ~/src/myrepo
   ocha run --file -              # read from stdin
   ```
   - Calls `launch_task()` + the new runner with a real Junie subprocess spawner.
   - Streams per-worker progress lines to stdout.
   - Exits 0 on full success, 1 on any worker failure.

4. **`app/orchestrator.py`**: Add `load_prompt(source: str | Path) -> str` that
   normalises the prompt (strip, validate ≤ 100 KB, reject empty). Use it from
   both `cli.py` and `NewTaskOverlay`.

5. Keep existing `ocha launch` as a dry-run/preview alias (no behaviour change).

### Phase 3 — Tests (builder, `tests/`)

6. **`tests/test_runner.py`** *(new)*:
   - `test_runner_executes_workers_sequentially` (mock subprocess)
   - `test_runner_injects_upstream_output`
   - `test_runner_returns_failure_on_worker_exit_code`

7. **`tests/test_orchestrator.py`**: Add `load_prompt` tests — empty, whitespace,
   oversized, valid multiline.

8. **`tests/test_cli.py`**: Add `run` tests — parser accepts prompt + `--project`
   + `--file`; `main(["run", "..."])` calls runner (mocked).

9. Run full suite: `python -m pytest tests/` — all existing tests must still pass.

### Phase 4 — Documentation & review

10. **`README.md`** (lead): Add "Creating a task" section with CLI and TUI examples.
11. **`docs/`** (coordinator): Finalize this brief.
12. **Reviewer**: Verify tests pass, confirm CLI and TUI both persist to
    `.ocha/tasks/`, check upstream output injection works across phases.

---

## Safe partitioning

| Owned directory | Role | Scope |
|---|---|---|
| `docs/` | **Coordinator** | This execution brief; follow-up context docs |
| `planning/` + `README.md` | **Lead** | Task plan, usage documentation |
| `app/` + `tests/` | **Builder** | All production code and test changes |
| `app/` (read-only) | **Reviewer** | Code review; may add assertions in `tests/` only |

All roles stay on the shared `agent` branch. No worktree conflicts because:
- **Coordinator** writes only to `docs/`
- **Lead** writes to `planning/` and `README.md`
- **Builder** owns all `app/` and `tests/` edits
- **Reviewer** reads `app/`, may append to `tests/` (non-overlapping with builder's new files)

---

*Brief produced by coordinator session S-001-01 for task T-001.*
