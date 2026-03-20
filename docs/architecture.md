# ocha Architecture

This document describes the internal architecture of the ocha Python/Textual application as of the current codebase.

## Module dependency graph

```
cli.py
  ├── orchestrator.py  (build_launch_specs, create_task_from_prompt)
  └── install.py       (clone_repo, update_repo, ensure_bootstrap)

app.py (OchaApp)
  ├── orchestrator.py  (build_role_prompt, launch_task, load_role_definitions)
  ├── git_utils.py     (commit_worktree_changes, merge_worktree_commits, ensure_pr_title)
  ├── state.py         (AppState, OchaTask, WorkerSession, enums)
  ├── widgets.py       (AgentsPane, TaskHeader, OutputPane, StatusBar, MainLayout)
  └── workflow_logger.py (WorkflowLogger, make_logger, LogLevel, EventCategory)

orchestrator.py
  ├── state.py         (AppState, OchaTask, TaskStatus, WorkerRole, WorkerSession)
  └── workflow_logger.py (make_logger, LogLevel, EventCategory)

state.py
  └── workflow_logger.py (WorkflowLogger — type hint only)
```

## Data model

### Core types (state.py)

```
AppState
  ├── tasks: list[OchaTask]
  ├── selected_index: int
  └── output_mode: OutputMode (WORKFLOW | RAW)

OchaTask
  ├── task_id: str           # "T-001"
  ├── title: str
  ├── user_task: str
  ├── branch: str            # always "agent"
  └── workers: list[WorkerSession]

WorkerSession
  ├── session_id: str        # "S-001-01"
  ├── task_id: str
  ├── title: str
  ├── role: WorkerRole       # coordinator | lead | builder | reviewer
  ├── status: WorkerStatus   # running | completed | failed | stopped | queued
  ├── branch: str
  ├── worktree_path: str
  ├── owned_directory: str
  ├── summary: str
  ├── workflow_log: deque     # legacy plain-text log (maxlen=5000)
  ├── raw_log: deque          # raw Junie output (maxlen=5000)
  ├── wlog: WorkflowLogger   # structured logger (created lazily)
  ├── task_prompt: str        # full prompt sent to Junie
  ├── role_prompt_path: str   # e.g. "app/roles/coordinator.md"
  ├── upstream_summary: str   # output from prior pipeline phase
  ├── worktree_commit_sha: str | None  # SHA after worktree commit
  ├── latest_event: str       # most recent status line
  ├── retry_count: int
  ├── started_at: datetime
  └── finished_at: datetime | None
```

### Enums

| Enum | Values |
|------|--------|
| `WorkerRole` | `coordinator`, `lead`, `builder`, `reviewer` |
| `WorkerStatus` | `running`, `completed`, `failed`, `stopped`, `queued` |
| `OutputMode` | `workflow`, `raw` |
| `TaskStatus` | `pending`, `running`, `completed`, `failed` |
| `LogLevel` | `debug`, `info`, `success`, `warning`, `error` |
| `EventCategory` | `lifecycle`, `pipeline`, `git`, `junie`, `prompt`, `system` |

## Request flow

### TUI task submission

```
User presses 'n' in TUI
  → NewTaskOverlay shown
  → User types prompt, presses Ctrl+S
  → OchaApp._launch_task_from_prompt(prompt)
    → orchestrator.launch_task(state, prompt)
      → summarize_task(prompt)             # truncate to 72 chars
      → build_launch_specs(prompt)         # generate 4 JunieLaunchSpecs
      → persist_task_prompt(task_id, prompt) # write .ocha/tasks/T-NNN/prompt.md
      → create WorkerSession per role      # first=RUNNING, rest=QUEUED
      → return new AppState with OchaTask appended
    → OchaApp._spawn_junie_workers(task)
      → for each RUNNING worker:
        → _ensure_worktree(worker)         # git worktree add
        → _write_prompt_file(worker)       # write session prompt to disk
        → _run_junie_for_worker(worker)    # async subprocess
```

### CLI task creation

```
ocha task "Fix the bug"
  → cli.main() parses args
  → orchestrator.create_task_from_prompt(prompt)
    → _next_task_number(repo_root)         # scan .ocha/tasks/ dirs
    → persist_task_prompt(task_id, prompt)
    → build_launch_specs(prompt)
    → write per-session prompt files
    → write status.json marker
    → return TaskCreationResult
  → print summary or JSON
```

### Pipeline advancement

```
Worker completes (exit code 0)
  → commit_worktree_changes(worktree_path)  # git add + commit inside worktree
  → OchaApp._advance_pipeline(task)
    → collect upstream output (capped 20 lines / 4 KB)
    → find next QUEUED worker
    → _rebuild_prompt_with_upstream()        # inject prior phase output
    → set worker to RUNNING
    → _run_junie_for_worker(next_worker)

All workers done
  → _post_pipeline_git_flow(task)            # async, runs in background thread
    → merge_worktree_commits(shas, branch)   # cherry-pick or patch-apply
    → git fetch + rebase on origin/agent
    → git push
    → ensure_pr_title(branch, title)         # gh pr create/edit
    → cleanup worktrees
```

## Junie process lifecycle

1. **Worktree creation** — `git worktree add <path> agent` (falls back to `--detach`)
2. **Prompt file** — written to `.ocha/tasks/<task_id>/<session_id>-prompt.md`
3. **Truncation** — prompts > 32 KB are trimmed at a line boundary
4. **Spawn** — `asyncio.create_subprocess_exec` with `start_new_session=True`
5. **Stdin feed** — prompt text piped via stdin (avoids arg-length limits)
6. **Streaming** — stdout read line-by-line into `raw_log` and `workflow_log`
7. **Completion** — exit code checked; changes committed inside worktree
8. **Kill** — `os.killpg(pgid, SIGKILL)` kills entire process tree (including Java)

## Widget hierarchy

```
OchaApp
  └── MainLayout
        ├── Horizontal#main-row
        │     ├── AgentsPane#agents-pane
        │     │     ├── Static.pane-title ("Tasks")
        │     │     └── ListView#workers-list
        │     │           └── WorkerListItem (per task)
        │     │                 └── Static.worker-row
        │     └── Vertical#detail-pane
        │           ├── TaskHeader#task-header (Static)
        │           └── OutputPane#output-pane (VerticalScroll)
        │                 └── Static#output-content
        ├── HelpBar#help-bar (Static)
        └── StatusBar#status-bar (Static)

  Overlays (modal screens):
  ├── NewTaskOverlay → #new-task-box (TextArea + hints)
  └── KillConfirmOverlay → #kill-box (confirmation buttons)
```

## Role directory ownership

| Role | Owned directory | Purpose |
|------|----------------|---------|
| Coordinator | `docs/` | Documentation, execution briefs |
| Lead | `planning/` | Task decomposition, work allocation |
| Builder | `app/` | Code, tests, implementation |
| Reviewer | `app/` | Review, validation |

## Git operations (git_utils.py)

| Function | Purpose |
|----------|---------|
| `commit_worktree_changes(path, msg)` | Stage + commit inside a worktree; returns SHA or None |
| `merge_worktree_commits(shas, branch)` | Cherry-pick SHAs onto branch; falls back to `git apply --3way` |
| `format_pr_title(task_id, title)` | Clean PR title: `[T-001] Capitalised description` (max 72 chars) |
| `ensure_pr_title(branch, title)` | Create or update PR via `gh` CLI |

## Install lifecycle (install.py)

| Function | Purpose |
|----------|---------|
| `clone_repo(target)` | Clone repo + bootstrap venv |
| `update_repo(target)` | Fetch + hard reset + re-bootstrap; preserves `.env` |
| `ensure_bootstrap(target)` | Create venv + `pip install -e` the project |
| `relaunch_from_bootstrap(result)` | `os.execv` into the venv's `ocha` binary |

## Structured logging (workflow_logger.py)

Each `WorkerSession` carries a `WorkflowLogger` that accumulates `LogEntry` items:

```
LogEntry
  ├── timestamp: datetime
  ├── level: LogLevel
  ├── category: EventCategory
  ├── message: str
  ├── role: str
  └── session_id: str
```

Entries render in two formats:
- `plain()` — `HH:MM:SS icon [role] message` (for raw log view)
- `rich()` — Textual Rich markup with Gruvbox colors (for workflow view)

The logger also writes plain-text copies to the legacy `deque[str]` for backward compatibility with older widget code.
