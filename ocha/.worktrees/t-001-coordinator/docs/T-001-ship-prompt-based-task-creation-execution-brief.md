# T-001 Execution Brief — Ship prompt based task creation

## Goal (refined)

The `ocha launch` CLI subcommand currently builds role-based `JunieLaunchSpec` objects and prints them to stdout, but it does **not** actually execute the pipeline (create worktrees, spawn Junie headless processes, advance through coordinator→lead→builder→reviewer, or run post-pipeline git flow). The TUI path (`n` key → `NewTaskOverlay`) does execute end-to-end via `_launch_task_from_prompt` → `_spawn_junie_workers` → `_advance_pipeline` → `_post_pipeline_git_flow`, but this logic is tightly coupled to the `OchaApp` Textual widget tree. **Ship prompt based task creation** means: extract the execution engine from the TUI into a reusable `run_pipeline()` function so that `ocha launch "my task"` runs the full pipeline headlessly (worktree setup, sequential Junie spawning with upstream handoff, git commit/push/PR) and exits with a proper status code—without requiring the Textual UI.

## Relevant files

| File | Role | Action |
|------|------|--------|
| `app/orchestrator.py` | lead, builder | **Edit** — add a headless `run_pipeline()` async function that drives the full coordinator→lead→builder→reviewer pipeline without a TUI |
| `app/cli.py` | builder | **Edit** — wire `ocha launch` to call `run_pipeline()` instead of just printing specs |
| `app/app.py` | builder | **Refactor** — extract `_ensure_worktree`, `_write_prompt_file`, `_run_junie_for_worker`, `_advance_pipeline`, `_rebuild_prompt_with_upstream`, `_post_pipeline_git_flow`, `_load_junie_api_key` out of `OchaApp` into shared helpers (or into orchestrator) so both TUI and CLI can use them |
| `app/state.py` | lead | **Read** — no changes expected; data model is sufficient |
| `app/roles/*.md` | coordinator | **Read-only** — role prompts are already correct |
| `tests/test_orchestrator.py` | builder | **Edit** — add tests for the new `run_pipeline()` function and extracted helpers |
| `tests/test_cli.py` | builder | **Edit** — add tests verifying `ocha launch` invokes the pipeline |
| `docs/` | coordinator | **Write** — this brief |

## Recommended changes

### Phase 1 — Extract execution engine from TUI

1. Move `_load_junie_api_key()` from `OchaApp` to a standalone function in `app/orchestrator.py` (or a new `app/engine.py`).
2. Move `_ensure_worktree(worker)` to a standalone function.
3. Move `_write_prompt_file(worker)` to a standalone function.
4. Move `_run_junie_for_worker(worker, task_obj, api_key)` to a standalone async function that accepts an `OchaTask` + callback for log updates.
5. Move `_advance_pipeline(task_obj)` to a standalone async function.
6. Move `_rebuild_prompt_with_upstream(worker, task_obj, upstream_output)` to a standalone function.
7. Move `_post_pipeline_git_flow(task_obj)` to a standalone async function.
8. Update `OchaApp` methods to delegate to the new standalone functions so the TUI still works.

### Phase 2 — Build headless `run_pipeline()`

9. Create `async def run_pipeline(user_task: str, *, project_path: Path, title: str | None = None) -> int` in `app/orchestrator.py` (or `app/engine.py`) that:
   - calls `launch_task()` to create the `AppState` + `OchaTask`
   - iterates through workers sequentially: create worktree → spawn Junie → capture output → advance pipeline
   - runs post-pipeline git flow (commit, rebase, push, PR)
   - returns exit code 0 on success, 1 on failure
   - prints structured progress to stdout (role, status, summary) so the TUI can later consume it as workflow events

### Phase 3 — Wire CLI

10. In `app/cli.py`, change the `launch` command handler to call `asyncio.run(run_pipeline(...))` and return its exit code.
11. Add `--dry-run` flag that preserves the current print-specs-only behavior.

### Phase 4 — Tests

12. Add unit tests for each extracted helper function.
13. Add an integration-style test for `run_pipeline()` that mocks `junie` subprocess calls and verifies the full sequencing (worktree create → 4 Junie runs → git flow).
14. Add a CLI test verifying `main(["launch", "..."])` calls `run_pipeline`.

## Safe partitioning

| Owned directory | Role | Scope |
|-----------------|------|-------|
| `docs/` | coordinator | This brief; no code changes |
| `app/` | builder | Extract engine helpers, create `run_pipeline()`, update `cli.py` and `app.py` |
| `tests/` | builder | New and updated test files |
| `planning/` | lead | Task breakdown from this brief into builder subtasks |

All work stays on the shared `agent` branch. Each role operates in its own worktree under `.worktrees/`. The builder's changes are confined to `app/` and `tests/`, which avoids overlap with the coordinator's `docs/` output.
