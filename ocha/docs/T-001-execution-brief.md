# T-001 Execution Brief — Ship prompt based task creation

**Coordinator:** S-001-01  
**Branch:** agent  
**Date:** 2026-03-19

---

## Goal (refined)

The operator task "Ship prompt based task creation" means: ensure the full
prompt-driven task creation pipeline works end-to-end — from the TUI modal
where the user types a task, through the orchestrator that builds role-scoped
Junie launch specs, to the actual headless Junie process spawning and pipeline
advancement.

As of this review the core flow **already exists and is wired**:

1. `n` key → `NewTaskOverlay` modal (single-line `Input` widget)
2. User submits text → `_launch_task_from_prompt` callback
3. `launch_task()` in `app/orchestrator.py` builds four `JunieLaunchSpec` objects
   (coordinator → lead → builder → reviewer), each with a composed prompt
4. `_spawn_junie_workers` starts the first worker; `_advance_pipeline` chains
   the rest sequentially
5. `ocha launch "<task>"` CLI sub-command previews specs without the TUI

### What remains to ship

| Gap | Priority | Notes |
|-----|----------|-------|
| The `Input` widget is single-line; multi-line task prompts need `TextArea` or `Ctrl+Enter` handling | High | README keybindings mention `Enter` = newline, `Ctrl+S` = submit — that UX isn't implemented yet |
| No persistence of task state across restarts (`AppState` is in-memory only) | Medium | `.ocha/status.json` exists but isn't loaded on startup |
| Worktree creation is specified in specs but never actually `git worktree add`-ed before spawn | Medium | `_run_junie_for_worker` uses `Path.cwd()` instead of `spec.worktree_path` |
| Post-pipeline git flow creates `ocha/<task-id>` branches instead of using the shared `agent` branch model | Medium | Contradicts the design doc; should rebase onto `agent` |
| No input validation or character limit on the task prompt | Low | Edge case: empty after strip is handled; very long prompts are not |

---

## Relevant files

### Must-read for every downstream agent

| File | Why |
|------|-----|
| `app/orchestrator.py` | Builds role prompts and launch specs; central to task creation |
| `app/app.py` | `NewTaskOverlay`, `_launch_task_from_prompt`, `_spawn_junie_workers`, `_advance_pipeline` |
| `app/state.py` | `AppState`, `OchaTask`, `WorkerSession` data model |
| `app/roles/*.md` | Role prompt templates injected into each Junie session |

### Secondary context

| File | Why |
|------|-----|
| `app/cli.py` | `ocha launch` sub-command — alternative entry point |
| `app/widgets.py` | TUI widget definitions used by the main layout |
| `README.md` | Design intent, keybindings, orchestration pipeline docs |
| `tests/test_orchestrator.py` | Existing orchestrator tests to maintain/extend |
| `tests/test_app.py` | Existing app-level tests |

---

## Safe partitioning for parallel worktrees

All agents share the `agent` branch. To avoid conflicts, respect these boundaries:

| Role | Owned directory | Scope |
|------|----------------|-------|
| **Coordinator** | `docs/` | This brief; context gathering only |
| **Lead** | `planning/` | Break the "what remains" table into builder sub-tasks |
| **Builder** | `app/` | Implement code changes (modal upgrade, worktree creation, state persistence, branch model fix) |
| **Reviewer** | `app/` | Post-builder review; read-only except for test additions in `tests/` |

The builder should avoid editing `docs/` or `planning/`. The reviewer should
avoid editing `app/` source — only `tests/` if new coverage is needed.

---

## Recommended sub-task breakdown (for the lead)

1. **Upgrade NewTaskOverlay to multi-line input**
   - Replace `Input` with `TextArea` (Textual ships one)
   - Wire `Ctrl+S` to submit and `Esc` to cancel (match README spec)
   - Keep `Enter` as newline inside the text area
   - Files: `app/app.py` (overlay class + CSS)

2. **Wire real git worktree lifecycle**
   - Before spawning a worker, run `git worktree add <worktree_path> agent`
   - Pass `worktree_path` (not `cwd()`) as the `--project` arg to Junie
   - On cleanup/kill, run `git worktree remove`
   - Files: `app/app.py` (`_spawn_junie_workers`, `_handle_kill`)

3. **Fix post-pipeline branch model**
   - Remove the `ocha/<task-id>` branch creation in `_post_pipeline_git_flow`
   - Instead: stage + commit on `agent`, rebase, push `agent`
   - Files: `app/app.py` (`_post_pipeline_git_flow`)

4. **Load/save task state to `.ocha/status.json`**
   - On launch and state change, write `AppState` to disk
   - On startup (`on_mount`), reload persisted state
   - Files: `app/state.py` (serialization), `app/app.py` (load/save hooks)

5. **Tests**
   - Extend `tests/test_orchestrator.py` for multi-line prompts, edge cases
   - Add integration-level test for worktree lifecycle (mock subprocess)
   - Files: `tests/`

---

## Execution rules reminder

- Stay on the `agent` branch — no branch-per-agent.
- Each agent works in its own worktree under `.worktrees/`.
- Prefer changes inside the assigned owned directory.
- Summarize results so the TUI can surface a short workflow event.
