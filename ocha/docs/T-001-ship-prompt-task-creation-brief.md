# T-001 Execution Brief — Ship prompt-based task creation

**Coordinator:** S-001-01  
**Branch:** agent  
**Date:** 2026-03-19  
**Verified:** 43 tests passing, 0 failures

---

## Goal (refined)

Ship a non-interactive CLI path (`ocha task "prompt"`) that creates and runs a
full four-phase Junie pipeline (coordinator → lead → builder → reviewer)
headlessly, without requiring the Textual TUI.  Today the TUI's `NewTaskOverlay`
(press `n`) is the only way to create and execute a task; the existing
`ocha launch` subcommand only prints `JunieLaunchSpec` objects without spawning
any processes.  The new subcommand must accept a prompt as a positional argument
or from a file (`--file`), call the existing `launch_task` orchestrator to build
the pipeline, persist the prompt to `.ocha/tasks/`, and sequentially execute each
worker's Junie session with upstream output hand-off — reusing the spawn and
pipeline-advance logic currently embedded in `OchaApp`.  This is the minimum
viable headless execution path needed before ocha can be driven by automation
or CI.

---

## Current state

| Component | Status | Location |
|-----------|--------|----------|
| `NewTaskOverlay` modal | ✅ Shipped | `app/app.py:191-237` — TextArea, Ctrl+S / Esc, blank/length guards |
| `launch_task()` | ✅ Shipped | `app/orchestrator.py:192-241` — builds 4 WorkerSession objects |
| `persist_task_prompt()` | ✅ Shipped | `app/orchestrator.py:179-189` — writes `.ocha/tasks/T-NNN/prompt.md` |
| `build_role_prompt()` | ✅ Shipped | `app/orchestrator.py:80-133` — runtime context + upstream injection |
| Worker spawn + pipeline | ✅ Shipped (TUI only) | `app/app.py:495-636` — spawns junie, streams output, advances pipeline |
| Upstream handoff | ✅ Shipped (TUI only) | `app/app.py:638-659` — rebuilds next prompt with prior output |
| Post-pipeline git flow | ✅ Shipped (TUI only) | `app/app.py:661-741` — commit → rebase → push → PR |
| `ocha launch` CLI | ✅ Shipped (dry-run only) | `app/cli.py:97-103` — prints specs, does not execute |
| Test coverage | ✅ 43 passing | `tests/test_app.py`, `tests/test_orchestrator.py`, `tests/test_cli.py` |

**Key gap:** The async worker-spawn loop, pipeline advancement, upstream handoff,
and post-pipeline git flow are all private methods on `OchaApp` — they cannot be
called without a running Textual app.  There is no CLI subcommand that actually
*runs* a task.

---

## Relevant files

| File | Read / Edit | Purpose |
|------|-------------|---------|
| `app/cli.py` | **Edit** | Add `task` subcommand with positional prompt, `--file`, `--project`, `--dry-run` |
| `app/orchestrator.py` | **Edit** | Extract `run_task_headless()` — async function that drives the sequential spawn loop |
| `app/app.py` | **Edit** | Refactor `_run_junie_for_worker` / `_advance_pipeline` / `_rebuild_prompt_with_upstream` to delegate to shared `run_task_headless` |
| `app/state.py` | Read | Data model — no changes expected |
| `app/__main__.py` | Read | Entry point — no changes expected |
| `app/roles/*.md` | Read | Role prompt templates — no changes |
| `tests/test_cli.py` | **Edit** | Add tests for `ocha task` arg parsing and dry-run |
| `tests/test_orchestrator.py` | **Edit** | Add tests for `run_task_headless` (mock subprocess, verify ordering + handoff) |
| `pyproject.toml` | Read | Confirm entry point `ocha = "app.__main__:main"` still covers new path |
| `docs/` | **Edit** | This brief |

---

## Recommended changes

### Phase 1 — Extract headless runner from TUI (builder: `app/`)

1. **Add `run_task_headless()` to `app/orchestrator.py`** — an async function
   that accepts `user_task`, `project_path`, `title`, and an optional
   `on_event(role, event_type, message)` callback.  It must:
   - Call `build_launch_specs` + `persist_task_prompt`.
   - For each spec in order: spawn `junie --project … --output-format text <prompt>`
     via `asyncio.create_subprocess_exec`, stream stdout, wait for exit.
   - After each worker completes, rebuild the next worker's prompt with upstream
     output (port `_rebuild_prompt_with_upstream` logic).
   - Return a result dataclass with per-worker exit codes and logs.

2. **Refactor `OchaApp`** — make `_run_junie_for_worker`, `_advance_pipeline`,
   and `_rebuild_prompt_with_upstream` delegate to the shared function so
   TUI and CLI behaviour stays consistent.

### Phase 2 — Wire CLI subcommand (builder: `app/`)

3. **Register `task` subparser in `app/cli.py`:**
   ```
   task = subparsers.add_parser("task", help="Create and run a task from a prompt")
   task.add_argument("prompt", nargs="?", help="Inline task prompt")
   task.add_argument("--file", "-f", type=Path, help="Read prompt from file")
   task.add_argument("--project", default=".", help="Project path")
   task.add_argument("--dry-run", action="store_true", help="Print specs without running")
   ```

4. **Handle `command == "task"` in `main()`:**
   - Resolve prompt from positional arg or `--file` (error if neither).
   - If `--dry-run`: print launch specs and exit (reuse existing logic).
   - Otherwise: `asyncio.run(run_task_headless(...))`, stream events to stdout,
     exit 0 on success, 1 on any worker failure.

### Phase 3 — Tests (builder: `tests/`)

5. `tests/test_cli.py` — add `test_task_parser_accepts_prompt`,
   `test_task_parser_file_flag`, `test_task_dry_run_prints_specs`.

6. `tests/test_orchestrator.py` — add `test_run_task_headless_sequential_pipeline`
   (mock `asyncio.create_subprocess_exec` to verify ordering and upstream handoff).

### Phase 4 — Verification

7. Run full test suite — all 43+ existing tests must still pass.
8. Run `ocha task "hello world" --dry-run` and verify output.
9. Run `ocha launch "hello world"` and verify it still works unchanged.

---

## Safe partitioning

| Role | Owned directory | Scope |
|------|----------------|-------|
| **Coordinator** | `docs/` | This brief (done) |
| **Lead** | `planning/` | Break phases into ordered sub-tasks for builder |
| **Builder** | `app/`, `tests/` | Implement `run_task_headless`, `task` subcommand, refactor TUI, add tests (steps 1–6) |
| **Reviewer** | `app/` (read-only), `tests/` | Run tests, verify CLI + TUI behaviour, add coverage if gaps remain (steps 7–9) |

**Conflict avoidance:** Builder owns all edits to `app/` and `tests/`.
Reviewer reads `app/` but only writes to `tests/` if new coverage is needed
(after builder is done).  Coordinator and lead do not touch `app/` or `tests/`.

---

## Branch rule

All workers stay on the shared `agent` branch.  No branch-per-agent.
Per-role worktree isolation (`.worktrees/t-001-{role}`) provides the safety
boundary for parallel execution.

---

## Success criteria

- [x] TUI `NewTaskOverlay` creates and runs tasks (existing)
- [x] `ocha launch` prints specs (existing)
- [x] 43 tests passing (existing)
- [ ] `run_task_headless()` extracted to `orchestrator.py` ← **Phase 1**
- [ ] `OchaApp` refactored to use shared runner ← **Phase 1**
- [ ] `ocha task "prompt"` creates + runs a full pipeline ← **Phase 2**
- [ ] `ocha task --file prompt.md` reads from file ← **Phase 2**
- [ ] `ocha task --dry-run` prints specs without running ← **Phase 2**
- [ ] CLI and orchestrator tests cover new code ← **Phase 3**
- [ ] All existing tests still pass ← **Phase 4**

---

## Coordinator summary (for TUI event)

> Execution brief produced for T-001: Ship prompt-based task creation.
> 43 tests passing.  Key gap: worker spawn/pipeline logic is locked inside
> `OchaApp` — no headless CLI path exists.  Plan: extract `run_task_headless()`
> to `orchestrator.py`, wire `ocha task` subcommand in `cli.py`, add tests.
> Four phases scoped for builder (1–3) and reviewer (4) with 9 concrete steps.
