# T-001 Execution Brief — Ship Prompt-Based Task Creation

> Produced by: coordinator (S-001-01)
> Branch: `agent`
> Updated: 2026-03-19 22:16

---

## Goal (refined)

The ocha TUI supports interactive task creation via `NewTaskOverlay` (press `n`), and the CLI has an `ocha launch` subcommand that prints specs but neither persists nor executes them.  "Ship prompt based task creation" means delivering a complete `ocha run "<prompt>"` CLI subcommand that (a) accepts a prompt string or `--file prompt.md`, (b) validates the prompt (empty/oversized rejection), (c) persists it to `.ocha/tasks/`, (d) builds the full 4-worker pipeline (coordinator → lead → builder → reviewer) via the existing `launch_task` orchestrator, and (e) spawns the Junie headless sessions to actually execute the pipeline — or prints a dry-run summary with `--dry-run`.  The TUI's `_launch_task_from_prompt` should be refactored to share the same core `create_task` function so both entry points stay validated and in sync.  The Junie spawn command in `app.py` has a wiring bug (positional arg instead of `--task` flag) that must be fixed for the pipeline to actually execute.

---

## Relevant files

| File | Role | Read / Edit | Notes |
|---|---|---|---|
| `app/orchestrator.py` | builder | Edit | Extract `create_task()` wrapping validation + `launch_task` + `persist_task_prompt`; add `run_task_headless()` for CLI pipeline execution |
| `app/cli.py` | builder | Edit | Add `run` subcommand with `--file`, `--dry-run`, `--json` flags |
| `app/app.py` | builder | Edit | Refactor `_launch_task_from_prompt` to use `create_task`; fix `_run_junie_for_worker` command construction (positional arg → `--task` flag); import shared `MAX_PROMPT_LENGTH` |
| `app/state.py` | lead | Read | Data model is sound; no changes expected unless JSON serialisation is needed |
| `app/roles/*.md` | — | Read | Role prompt templates consumed during creation |
| `app/widgets.py` | — | Read | UI widgets; no changes expected |
| `tests/test_orchestrator.py` | builder | Edit | Add `create_task` + `run_task_headless` tests |
| `tests/test_app.py` | builder | Edit | Add test for fixed junie command construction; verify refactored TUI path |
| `tests/test_cli.py` | builder | Edit | Add `ocha run` tests: success, `--file`, empty prompt failure, `--json`, `--dry-run` |
| `pyproject.toml` | — | Read | Verify `[project.scripts]` entry point |

---

## Recommended changes

### Phase 1 — Core `create_task` function (builder, `app/orchestrator.py`)

1. **Move `MAX_PROMPT_LENGTH = 100_000`** from `NewTaskOverlay` into `orchestrator.py` as a module-level constant so both TUI and CLI share it.

2. **Extract `create_task(user_task, *, project_path, state) -> tuple[AppState, OchaTask]`** that validates the prompt (empty/whitespace → `ValueError`, oversized → `ValueError`), then composes `launch_task` + `persist_task_prompt` into a single public entry point.

3. **Add `run_task_headless(user_task, *, project_path) -> AppState`** that calls `create_task`, then iterates the pipeline synchronously (or with `asyncio.run`): spawn coordinator → wait → feed upstream to lead → wait → … → reviewer.  Returns the final `AppState` so the CLI can print a summary.  This avoids duplicating the spawn logic that currently lives in `OchaApp._advance_pipeline`.

4. **Keep `launch_task` and `persist_task_prompt` unchanged** — `create_task` composes them.

### Phase 2 — CLI `run` subcommand (builder, `app/cli.py`)

5. **Register `run` subparser**:
   ```
   ocha run "<prompt>"           # inline prompt
   ocha run --file prompt.md     # read prompt from file
   ocha run --dry-run "..."      # print specs without executing (replaces current `launch`)
   ocha run --json "..."         # structured output
   ocha run --project ~/code "..." # explicit project path
   ```
   Positional `prompt` and `--file` are mutually exclusive.

6. **Handler**: call `create_task` (dry-run) or `run_task_headless` (full run).  Print human-readable summary by default (task-id, title, worker count, pipeline status), or emit JSON when `--json` is passed.  Exit 0 on success, 1 on validation error.

7. **Deprecate `launch`** subcommand: keep it for backwards compat but print a deprecation notice pointing to `ocha run --dry-run`.

### Phase 3 — Fix Junie spawn wiring + TUI alignment (builder, `app/app.py`)

8. **Fix `_run_junie_for_worker`** (around L534-542): the hand-rolled `cmd` list passes `worker.task_prompt` as a bare positional argument.  Replace with `"--task", worker.task_prompt` to match `JunieLaunchSpec.command` contract.

9. **Refactor `_launch_task_from_prompt`** to call `create_task` instead of `launch_task` directly, so the TUI inherits the same validation and persistence logic.

10. **Remove duplicate `MAX_PROMPT_LENGTH`** from `NewTaskOverlay`; import from orchestrator.

### Phase 4 — Tests (builder, `tests/`)

11. **`tests/test_orchestrator.py`** — add tests for `create_task`:
    - Happy path: returns updated state + task with 4 workers
    - Empty prompt: raises `ValueError`
    - Oversized prompt: raises `ValueError`
    - State numbering increments correctly
    - `run_task_headless` with mocked subprocess

12. **`tests/test_cli.py`** — add tests:
    - `ocha run "do something"` succeeds, prints task-id
    - `ocha run --file <path>` reads prompt from file
    - `ocha run ""` exits with code 1
    - `ocha run --dry-run "..."` prints specs without executing
    - `ocha run --json "..."` produces valid JSON

13. **`tests/test_app.py`** — add test:
    - `test_junie_command_uses_task_flag` — assert `--task` is in the argv

14. **Run full existing test suite** to confirm no regressions.

### Phase 5 — Docs (coordinator, `docs/`)

15. This execution brief (produced by coordinator).
16. Update `README.md` usage section with `ocha run` examples.

---

## Safe partitioning

| Owned directory | Role | Scope |
|---|---|---|
| `docs/` | coordinator | Execution brief and README updates |
| `planning/` | lead | Task breakdown from this brief; no code edits |
| `app/` | builder | All production code: orchestrator, cli, app |
| `tests/` | builder (write) / reviewer (verify) | New and existing tests |

All roles stay on the shared `agent` branch.  No worktree conflicts expected because:
- Coordinator only writes to `docs/`
- Lead only writes to `planning/`
- Builder owns all `app/` and `tests/` edits
- Reviewer reads everything; may edit `tests/` only if coverage gaps found

---

## Key risks

- **Junie CLI contract**: The exact flag syntax (`--task` vs positional) must be verified against `junie --help`.  If the contract differs, Phase 3 step 8 needs adjustment.
- **Auth flow**: `_load_junie_api_key` reads `.env` files — the `--auth` flag injection should be optional (skip if no key found, let junie use its own auth).
- **Large prompts**: The TUI caps at 100 KB; the CLI currently has no limit.  Phase 1 step 1-2 unifies this.
- **State persistence**: `AppState` is in-memory only.  `ocha run` will persist the prompt file but the task won't appear in the TUI unless the TUI reloads state from `.ocha/tasks/`.  Acceptable for v1.
- **Headless pipeline**: `run_task_headless` needs careful async handling — `asyncio.run` from CLI context, vs the TUI's existing `run_worker` pattern.  Keep them separate; share only `create_task`.
