# T-001 Execution Brief — Ship Prompt-Based Task Creation

**Coordinator:** S-001-01
**Branch:** agent
**Date:** 2026-03-19

---

## Goal (refined)

Ship prompt-based task creation as a complete, usable feature. The TUI
pipeline is already wired end-to-end (`NewTaskOverlay` → `launch_task()` →
`_spawn_junie_workers` → pipeline advancement with upstream handoff →
post-pipeline git flow). However, task creation is **only reachable through
the TUI** — there is no CLI command that creates *and executes* a task from a
prompt. The `ocha launch` subcommand prints specs but does not run them.

To ship this feature, two gaps must be closed:

1. **Add `ocha run "<prompt>"`** — a non-interactive CLI subcommand that
   creates an `OchaTask`, persists the prompt, spawns the Junie headless
   pipeline sequentially (coordinator → lead → builder → reviewer), streams
   output to stdout, and exits with a meaningful return code. This makes
   prompt-based task creation usable from scripts, CI, and ocha's own
   headless sessions.

2. **Wire real git worktrees** — `_run_junie_for_worker` currently passes
   `Path.cwd()` as `--project` to Junie instead of the per-role worktree
   path already computed in the launch spec. Workers edit the main checkout
   directly, defeating the isolation model.

---

## Current state — what already works

| Layer | Status | Location |
|---|---|---|
| `NewTaskOverlay` modal | ✅ Multi-line `TextArea`, `Ctrl+S` submit, `Esc` cancel, double-open guard | `app/app.py:191-237` |
| Input validation | ✅ Blank rejection, 100 KB length guard | `app/app.py:226-237` |
| `launch_task()` | ✅ Builds 4 role-backed `WorkerSession` objects, first RUNNING | `app/orchestrator.py:192-241` |
| `persist_task_prompt()` | ✅ Writes prompt to `.ocha/tasks/T-NNN/prompt.md` | `app/orchestrator.py:179-189` |
| `build_role_prompt()` | ✅ Injects role markdown + runtime context + operator task; supports `upstream_output` | `app/orchestrator.py:80-133` |
| Role definitions | ✅ Four `.md` files with input/output contracts | `app/roles/{coordinator,lead,builder,reviewer}.md` |
| `_spawn_junie_workers` / `_advance_pipeline` | ✅ Spawns `junie` CLI, streams output, advances pipeline with upstream handoff | `app/app.py:495-636` |
| `_post_pipeline_git_flow` | ✅ Commits on `agent`, rebases, pushes, opens PR via `gh` | `app/app.py:661-742` |
| `ocha launch <task>` CLI | ✅ Dry-run preview of role launches | `app/cli.py:97-103` |
| Tests — orchestrator | ✅ Role loading, launch specs, prompts, persistence, upstream handoff, role contracts | `tests/test_orchestrator.py` |

---

## Relevant files

| File | Role | Action |
|---|---|---|
| `app/orchestrator.py` | Builder | **Edit** — add `run_task_pipeline()` function |
| `app/cli.py` | Builder | **Edit** — add `run` subcommand |
| `app/app.py` | Builder | **Edit** — wire worktree create/remove around Junie spawn and kill |
| `app/state.py` | Read-only | `OchaTask`, `WorkerSession` — no changes needed |
| `app/roles/*.md` | Read-only | Role prompts — no changes needed |
| `app/widgets.py` | Read-only | TUI widgets — no changes needed |
| `tests/test_cli.py` | Builder | **Edit** — add `run` subcommand parser tests |
| `tests/test_orchestrator.py` | Builder | **Edit** — add `run_task_pipeline` tests |
| `tests/test_app.py` | Builder | **Edit** — add worktree lifecycle tests |
| `docs/` | Coordinator | **Edit** — this brief |

---

## Recommended changes

### Phase 1 — Extract headless pipeline runner (`app/orchestrator.py`)

1. **Add `run_task_pipeline(user_task, *, project_path, on_event=None) -> OchaTask`**
   — a function (sync or async) that:
   - Calls `launch_task()` to create the task + workers.
   - Iterates workers in pipeline order (coordinator → lead → builder → reviewer).
   - For each worker: spawns `junie` via `subprocess.run`, captures
     stdout/stderr into `worker.raw_log` / `worker.workflow_log`, marks
     status `COMPLETED` or `FAILED`, and passes upstream summary to the next
     worker via `build_role_prompt(..., upstream_output=...)`.
   - Calls the optional `on_event` callback per log line for streaming output.
   - Returns the fully-populated `OchaTask`.

2. **Keep `launch_task` and `build_launch_specs` unchanged** — they are pure
   data builders and are correct as-is.

3. **Preserve `persist_task_prompt`** call so the `.ocha/tasks/<id>/prompt.md`
   audit trail continues to work.

### Phase 2 — Wire CLI subcommand (`app/cli.py`)

4. **Add `run` subcommand** to `build_parser()`:
   ```python
   run = subparsers.add_parser("run", help="Create and execute a task from a prompt")
   run.add_argument("task", help="Operator prompt describing the task")
   run.add_argument("--project", default=".", help="Project path")
   ```

5. **Implement `command == "run"` handler** in `main()`:
   - Call `run_task_pipeline(args.task, project_path=...)`.
   - Stream `on_event` lines to stdout.
   - Exit 0 if all workers completed, 1 if any failed.

### Phase 3 — Wire real git worktrees (`app/app.py`)

6. **Before spawning** in `_run_junie_for_worker`: run
   `git worktree add <worker.worktree_path> agent`.

7. **Junie project arg**: pass `worker.worktree_path` (not `cwd()`) as
   `--project` to the Junie CLI.

8. **On kill** in `_handle_kill`: run
   `git worktree remove --force <worktree_path>`.

9. **Post-pipeline cleanup**: remove all worktrees for the completed task
   in `_post_pipeline_git_flow` or a new `_cleanup_worktrees` method.

10. **Error handling**: if `git worktree add` fails, attempt remove + retry
    or mark worker as FAILED with a clear log message.

### Phase 4 — Tests (`tests/`)

11. **`tests/test_cli.py`** — add parser test for `run` subcommand args.

12. **`tests/test_orchestrator.py`** — add tests for `run_task_pipeline`:
    - Mock `subprocess.run` to avoid calling `junie`.
    - Assert workers advance in order.
    - Assert upstream summary is injected into downstream prompts.
    - Assert final `OchaTask.status` reflects success/failure.

13. **`tests/test_app.py`** — add worktree lifecycle tests:
    - Verify Junie command uses `worktree_path` not `cwd()`.
    - Verify worktree cleanup on kill.

---

## Safe partitioning

| Role | Owned directory | Key files to touch |
|---|---|---|
| **Coordinator** | `docs/` | This brief (done) |
| **Lead** | `planning/` | Task plan derived from this brief |
| **Builder** | `app/`, `tests/` | `orchestrator.py` (pipeline runner), `cli.py` (run subcommand), `app.py` (worktree lifecycle), tests |
| **Reviewer** | `app/` (read-only) | Review builder changes, run full test suite |

The builder should not edit `docs/`. The reviewer should not rewrite `app/`
source — only verify and flag issues.

---

## Branch rule

All workers stay on the shared `agent` branch. No branch-per-agent.
Worktree isolation (`{project}/.worktrees/t-001-{role}`) provides the safety
boundary.

---

## Suggested execution order

1. **Coordinator** (this session) — produce this brief ✓
2. **Lead** — confirm gaps and break into builder sub-tasks
3. **Builder** — implement Phase 1-4 above
4. **Reviewer** — verify builder output, run `pytest`, confirm both CLI and TUI flows

---

## Success criteria

- `ocha run "some task"` creates and executes a full pipeline from the CLI.
- Workers are spawned in real git worktrees, not `cwd()`.
- Worktrees are cleaned up on kill and after pipeline completion.
- Pressing `n` in the TUI still works end-to-end (no regression).
- All existing tests pass; new tests cover `run` subcommand and worktree lifecycle.
- `ocha launch "some task"` still works for dry-run preview.

---

## Coordinator summary (for TUI event)

> Execution brief written. Two gaps to ship prompt-based task creation:
> (1) add `ocha run` CLI subcommand with headless pipeline runner extracted
> from TUI logic, (2) wire real git worktree lifecycle around Junie spawn.
> Builder touches `app/orchestrator.py`, `app/cli.py`, `app/app.py`, and tests.
