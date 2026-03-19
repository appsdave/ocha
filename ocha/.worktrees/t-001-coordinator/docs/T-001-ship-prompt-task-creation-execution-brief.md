# T-001 Execution Brief — Ship Prompt-Based Task Creation

> Produced by: coordinator (S-001-01)
> Branch: agent
> Date: 2026-03-19

---

## Goal (refined)

The operator typed "Ship prompt based task creation" — meaning the full pipeline from **user prompt → orchestrated Junie headless sessions** must work end-to-end as a shippable feature. Today the TUI overlay (`n` key) already calls `launch_task()` which builds role-backed `JunieLaunchSpec`s, creates worktrees, spawns Junie headless processes, streams output, advances the pipeline across coordinator → lead → builder → reviewer phases, and runs a post-pipeline git flow (commit, rebase, push, PR). The CLI also has `ocha launch "<prompt>"` but it only **previews** the specs without executing. The task is to verify this pipeline is shippable, close any remaining gaps, and add a CLI path (`ocha task create "<prompt>"`) that runs the same pipeline headlessly so operators can trigger task creation without the TUI.

---

## Relevant files

| File | Role | Action | Notes |
|------|------|--------|-------|
| `app/orchestrator.py` | lead, builder | read + edit | Core pipeline: `launch_task()`, `build_launch_specs()`, `persist_task_prompt()`. Add headless execution entry point. |
| `app/cli.py` | builder | edit | Add `ocha task create "<prompt>"` subcommand that calls the orchestrator and runs workers. |
| `app/app.py` | builder | read + minor edit | TUI task flow reference. `_spawn_junie_workers`, `_advance_pipeline`, `_run_junie_for_worker` contain the async execution logic that needs a non-TUI equivalent. |
| `app/state.py` | lead, builder | read | `AppState`, `OchaTask`, `WorkerSession`, `WorkerRole`, `WorkerStatus` — data model is stable. |
| `app/roles/coordinator.md` | read-only | — | Role prompt contract (input/output). |
| `app/roles/lead.md` | read-only | — | Role prompt contract. |
| `app/roles/builder.md` | read-only | — | Role prompt contract. |
| `app/roles/reviewer.md` | read-only | — | Role prompt contract. |
| `tests/test_orchestrator.py` | builder | edit | Add tests for the new CLI entry point and headless execution path. |
| `tests/test_cli.py` | builder | edit | Add tests for `ocha task create` argument parsing. |
| `README.md` | coordinator | edit | Document the new `ocha task create` command. |
| `.ocha/tasks/T-NNN/prompt.md` | — | generated | Persisted prompt file per task (already implemented). |

---

## Recommended changes

### Phase 1 — Extract headless execution from TUI (builder, `app/`)

1. **Extract `run_pipeline()` from `OchaApp`** — The async worker execution logic (`_run_junie_for_worker`, `_advance_pipeline`, `_ensure_worktree`, `_write_prompt_file`, `_load_junie_api_key`, `_post_pipeline_git_flow`) currently lives on the `OchaApp` class. Extract it into a standalone async function in `app/orchestrator.py` (or a new `app/runner.py`) so it can be called without a Textual app instance. The TUI methods can then delegate to this shared implementation.

2. **Add `run_task_headless(user_task, project_path)` to orchestrator** — A single async entry point that:
   - Calls `launch_task()` to build state
   - Creates worktrees
   - Spawns Junie for each worker sequentially (coordinator → lead → builder → reviewer)
   - Passes upstream output between phases
   - Runs post-pipeline git flow
   - Returns final `AppState` or a summary dict

3. **Wire `ocha task create "<prompt>"`** in `cli.py` — Add a `task` subcommand group with a `create` action that calls `asyncio.run(run_task_headless(...))` and prints progress to stdout.

### Phase 2 — Harden the pipeline (builder, `app/`)

4. **Validate Junie CLI availability early** — Move `shutil.which("junie")` and API key check to the start of execution rather than mid-pipeline, so failures are immediate.

5. **Handle worktree branch conflicts** — The current `_ensure_worktree` falls back to `--detach` if the branch is already checked out. Verify this works for parallel tasks and document the behavior.

6. **Add timeout/retry for Junie sessions** — Workers can hang indefinitely. Consider adding a configurable timeout per worker role.

### Phase 3 — Tests (builder, `tests/`)

7. **Test `ocha task create` CLI parsing** — Verify argparse accepts `ocha task create "my prompt"` and `ocha task create --project /path "my prompt"`.

8. **Test headless pipeline without Junie** — Mock `asyncio.create_subprocess_exec` to verify the pipeline advances correctly through all four phases, passes upstream output, and handles failures.

9. **Test prompt persistence** — Already covered; ensure new paths also persist.

### Phase 4 — Documentation (coordinator, `docs/`)

10. **Update README.md** — Add `ocha task create` to the command surface section.

11. **Write brief** — This document (done).

---

## Safe partitioning

| Owned directory | Role | Scope |
|----------------|------|-------|
| `docs/` | coordinator | This execution brief, README updates |
| `app/` | builder | `orchestrator.py` (or new `runner.py`), `cli.py`, `app.py` refactor |
| `tests/` | builder | `test_orchestrator.py`, `test_cli.py` |
| `planning/` | lead | Task breakdown and subtask assignment |

**Conflict avoidance:** The coordinator only writes to `docs/`. The builder owns `app/` and `tests/`. The lead produces planning artifacts. No overlap expected. All work stays on the shared `agent` branch with worktree isolation.

---

## Key observations for downstream roles

- **The TUI pipeline already works.** The `OchaApp._launch_task_from_prompt` → `_spawn_junie_workers` → `_run_junie_for_worker` → `_advance_pipeline` chain is functional. The main gap is that this logic is coupled to the Textual app and cannot be invoked from CLI.
- **`ocha launch` is preview-only.** It prints specs but doesn't execute. The new `ocha task create` command should actually execute.
- **Upstream handoff exists.** `_advance_pipeline` already collects the last completed worker's output and rebuilds the next worker's prompt with `upstream_output`. This must be preserved in the extracted version.
- **Post-pipeline git flow exists.** Commit → fetch → rebase → push → PR creation via `gh` CLI is implemented in `_post_pipeline_git_flow`.
- **State is in-memory only.** `AppState` is not persisted to disk between runs. For headless CLI usage, the runner should print progress events to stdout and optionally write a final summary to `.ocha/tasks/T-NNN/result.json`.
