# T-001 — Ship Prompt-Based Task Creation

## Execution Brief

### 1. Goal (refined)

The prompt-based task creation pipeline is functionally complete: the TUI's
`NewTaskOverlay` captures operator text, `launch_task()` builds per-role
`JunieLaunchSpec`s, worktrees are provisioned on the shared `agent` branch,
Junie headless sessions are spawned sequentially with upstream handoff, and
`_post_pipeline_git_flow` commits/pushes/opens a PR.  "Ship" means hardening
edge cases, improving error feedback, adding missing integration-level test
coverage for the end-to-end prompt→launch path, and documenting the feature so
operators and future contributors understand the flow.

### 2. Relevant files

| File | Role | Action |
|---|---|---|
| `app/app.py` | builder | Edit — harden `NewTaskOverlay` validation, `_spawn_junie_workers` error paths |
| `app/orchestrator.py` | builder | Edit — add input sanitisation to `summarize_task`, guard `build_launch_specs` for empty/whitespace prompts |
| `app/state.py` | builder | Read — understand `AppState`, `OchaTask`, `WorkerSession` contracts |
| `app/cli.py` | builder | Edit — add `--title` flag to `launch` subcommand so operators can override the auto-summary |
| `app/roles/coordinator.md` | lead | Read |
| `app/roles/lead.md` | lead | Read |
| `app/roles/builder.md` | lead | Read |
| `app/roles/reviewer.md` | lead | Read |
| `tests/test_orchestrator.py` | builder / reviewer | Edit — add edge-case tests (empty prompt, oversized prompt, unicode, duplicate task IDs) |
| `tests/test_app.py` | builder / reviewer | Edit — add integration tests for `NewTaskOverlay` submit/cancel and `_launch_task_from_prompt` |
| `tests/test_cli.py` | reviewer | Read — verify `launch` subcommand coverage |
| `pyproject.toml` | builder | Read — confirm `app.roles` package-data inclusion |
| `docs/` | coordinator | Write — this brief and any follow-up docs |

### 3. Recommended changes

**Phase 1 — Input validation & edge-case hardening (builder)**

1. In `orchestrator.py:summarize_task`, return `"Untitled task"` for
   whitespace-only input (already handled) and strip leading/trailing
   newlines before truncation.
2. In `orchestrator.py:build_launch_specs`, raise `ValueError` when
   `user_task` is empty after stripping — callers should never silently
   produce specs for a blank prompt.
3. In `app.py:NewTaskOverlay._submit`, add a char-count lower bound
   (e.g., ≥ 3 chars) to prevent near-empty prompts from launching a full
   four-worker pipeline.
4. In `app.py:_spawn_junie_workers`, surface a clear TUI notification
   when `_ensure_worktree` fails for *all* workers (currently only logged).

**Phase 2 — CLI parity (builder)**

5. Add `--title` optional argument to `ocha launch` so the operator can
   supply a human-readable title instead of relying on `summarize_task`.
6. Pass `title` through to `build_launch_specs` (the kwarg already exists).

**Phase 3 — Test coverage (builder + reviewer)**

7. Add `test_orchestrator.py` cases:
   - empty / whitespace-only prompt raises `ValueError`.
   - prompt longer than 100 KB is handled gracefully.
   - `persist_task_prompt` creates the expected directory and file.
   - `launch_task` increments `next_task_number` correctly for sequential
     calls.
8. Add `test_app.py` cases:
   - `NewTaskOverlay` dismisses `None` on cancel.
   - `NewTaskOverlay` rejects empty and over-length prompts.
   - `_launch_task_from_prompt(None)` does not mutate state.
9. Reviewer verifies all existing 43 tests still pass after changes.

**Phase 4 — Documentation (coordinator)**

10. This execution brief (already written).
11. Add a short "Prompt-based task creation" section to `README.md`
    describing the `ocha launch` command and the TUI `n` key workflow.

### 4. Safe partitioning

| Owned directory | Role | Scope |
|---|---|---|
| `docs/` | coordinator | Execution brief, README updates |
| `planning/` | lead | Plan refinement, phase sequencing |
| `app/` | builder | Production code changes (orchestrator, app, cli) |
| `app/`, `tests/` | reviewer | Test verification, code review |

All roles operate on the shared `agent` branch via isolated worktrees.
No branch-per-agent complexity.
