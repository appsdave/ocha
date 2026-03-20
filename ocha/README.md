# ocha

A Python/Textual TUI for orchestrating multiple Junie coding agents against one git repository.

## Quick start

### One-line install

```bash
curl -fsSL https://raw.githubusercontent.com/appsdave/ocha/main/install.sh | bash
```

The installer will:

- install missing system prerequisites with `apt` when available (`git`, `python3`, `python3-pip`, `python3-venv`)
- clone this repo into `~/.ocha`
- create `~/.ocha/.venv`
- install the Python app from the repo's `ocha/` project directory
- symlink `~/.local/bin/ocha` to the managed launcher

After that:

```bash
ocha          # launch the TUI dashboard
ocha update   # pull latest changes and refresh the runtime
```

If `~/.local/bin` is not on `PATH`, add it to your shell profile:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

## Command surface

| Command | Description |
|---------|-------------|
| `ocha` | Launch the Textual dashboard |
| `ocha download [target]` | Clone the canonical repo into `~/.ocha` and install its runtime |
| `ocha update [target]` | Fast-forward an existing `~/.ocha` install from `origin/main` and refresh dependencies |
| `ocha task <prompt>` | Create a new task from a prompt (also accepts stdin) |
| `ocha launch <task>` | Preview generated role-based headless Junie launches without opening the TUI |

If no target is provided for `download` or `update`, ocha defaults to `~/.ocha`.

### Task creation examples

```bash
# Direct prompt
ocha task "Ship prompt based task creation"

# Pipe via stdin
echo "Fix the login bug" | ocha task

# Specify project root
ocha task "Add dark mode" --project ~/src/myapp

# JSON output
ocha task "Refactor auth module" --json
```

This will:

1. Persist the prompt to `.ocha/tasks/T-NNN/prompt.md`
2. Write a `status.json` marker (initially `pending`)
3. Build launch specs for all four roles (coordinator, lead, builder, reviewer)
4. Write per-session prompt files for each worker
5. Print a summary with the task ID, title, and worker session targets

## What ocha does

At a high level:

1. You enter one high-level task (via the TUI or `ocha task`).
2. A **coordinator** enhances that task with project context.
3. A **lead agent** breaks the task into smaller builder tasks.
4. Each builder task runs in its own **isolated git worktree** while sharing a single `agent` branch.
5. A **reviewer agent** checks each builder result.
6. Results are committed per-worktree, cherry-picked onto the shared branch, rebased, and pushed.

That makes ocha two things at once:

- a **workflow engine** for multi-agent coding
- a **terminal dashboard** for watching and controlling that workflow

## Runtime stack

| Layer | Technology |
|-------|------------|
| Language | Python ≥ 3.11 |
| TUI framework | [Textual](https://textual.textualize.io/) ≥ 0.58 |
| Build system | setuptools ≥ 68 |
| Entry point | `app.__main__:main` |
| Theme | Gruvbox Dark Green |

## Project layout

```
ocha/
├── pyproject.toml              # Package metadata and dependencies
├── README.md                   # This file
├── app/
│   ├── __init__.py
│   ├── __main__.py             # Entry point (delegates to cli.main)
│   ├── app.py                  # OchaApp — Textual application, CSS, overlays,
│   │                           #   Junie process spawning, pipeline advancement,
│   │                           #   post-pipeline git flow (commit/rebase/push/PR)
│   ├── cli.py                  # CLI argument parser and command dispatch
│   ├── git_utils.py            # Worktree commit, cherry-pick/merge, PR title formatting
│   ├── install.py              # Clone, update, bootstrap, and venv management
│   ├── orchestrator.py         # Role prompt loading, launch spec building, task creation
│   ├── state.py                # Data models: AppState, OchaTask, WorkerSession, enums
│   ├── widgets.py              # TUI widgets: AgentsPane, TaskHeader, OutputPane,
│   │                           #   StatusBar, HelpBar, MainLayout
│   ├── workflow_logger.py      # Structured logging: LogEntry, WorkflowLogger, levels/categories
│   └── roles/
│       ├── coordinator.md      # Coordinator role prompt
│       ├── lead.md             # Lead role prompt
│       ├── builder.md          # Builder role prompt
│       └── reviewer.md         # Reviewer role prompt
├── tests/
│   ├── test_app.py
│   ├── test_cli.py
│   ├── test_git_utils.py
│   ├── test_install.py
│   ├── test_orchestrator.py
│   ├── test_performance.py
│   └── test_workflow_logger.py
├── python-textual-rebuild.md   # Design notes for the Python/Textual rebuild
└── junie-headless-sessions.md  # Design notes for headless Junie session management
```

## TUI layout

The dashboard is a keyboard-first operations console split into four areas:

```
┌──────────────────┬─────────────────────────────────────┐
│  Agents sidebar   │  Task header                        │
│  (task list with  │  (selected task ID, status, branch, │
│   status badges)  │   elapsed, pipeline visualization)  │
│                   ├─────────────────────────────────────┤
│                   │  Output pane                        │
│                   │  (workflow log or raw log view,     │
│                   │   color-coded by role)              │
├───────────────────┴─────────────────────────────────────┤
│  Help bar (keybindings)                                 │
├─────────────────────────────────────────────────────────┤
│  Status bar (counts, selected task, branch, view mode)  │
└─────────────────────────────────────────────────────────┘
```

### Keybindings

| Key | Action |
|-----|--------|
| `n` | Open new task prompt (multi-line editor) |
| `↑` / `↓` | Move through tasks |
| `x` | Kill selected task (with confirmation) |
| `c` | Clear completed / failed / stopped tasks |
| `v` | Toggle workflow view ↔ raw log view |
| `←` | Focus agents sidebar |
| `→` | Focus output pane |
| `Tab` | Cycle focus between panes |
| `q` | Quit |

Inside the new task overlay:

| Key | Action |
|-----|--------|
| `Enter` | Insert newline |
| `Ctrl+S` | Submit task |
| `Esc` | Cancel |

## Orchestration pipeline

Each task moves through a fixed four-phase pipeline:

### 1. Coordinator

- Accepts the original user task
- Gathers repo context
- Enhances the prompt
- Owned directory: `docs/`

### 2. Lead

- Reads the enhanced task
- Plans subtasks
- Assigns subtasks to separate worktrees and preferably separate repo areas
- Owned directory: `planning/`

### 3. Builder

- Runs in an isolated worktree
- Makes code/doc/test changes
- Owned directory: `app/`

### 4. Reviewer

- Runs after the builder in the same isolated worktree
- Checks the builder output
- Owned directory: `app/`

### Pipeline mechanics

- Each phase runs as a headless Junie session with a role-specific markdown prompt
- When a phase completes, the orchestrator captures its output summary and injects it into the next phase's prompt as `upstream_output`
- Upstream output is capped at 20 lines / 4 KB to stay within Junie's parser limits
- Prompts exceeding 32 KB are truncated before being sent to Junie

### Junie invocation

The task prompt is fed via stdin to avoid shell arg-length limits:

```bash
junie --auth=<key> --project <worktree_path> --output-format text < prompt.md
```

Preview what ocha will launch without starting the TUI:

```bash
ocha launch "finish building the app with role markdown prompts"
```

### Headless Junie role prompts

Role markdown files live in `app/roles/`:

- `coordinator.md`
- `lead.md`
- `builder.md`
- `reviewer.md`

When a new task is launched, ocha loads the matching markdown file for each role, appends runtime context (`task_id`, `session_id`, `project_path`, `worktree_path`, `owned_directory`, branch `agent`), and builds the headless Junie invocation.

## Git workflow

### Branch model

All worktrees share a single `agent` branch — there is no branch-per-agent complexity.

### Worktree isolation

Every task worker gets its own git worktree so that:

- tasks do not overwrite each other
- agents can run in parallel safely
- merge conflicts are reduced
- each result can be reviewed independently

The TUI is really visualizing a queue of isolated worktrees, not just a queue of logs.

### Post-pipeline sync

After all workers finish, ocha runs an automated git flow:

1. **Commit** — each worker's changes are committed inside its worktree during execution
2. **Cherry-pick** — worktree commits are cherry-picked onto the `agent` branch (falls back to `git diff | git apply` on conflict)
3. **Rebase** — `agent` is rebased on `origin/agent`
4. **Push** — the branch is pushed to origin
5. **PR** — a pull request is created or updated via `gh` CLI with a formatted title `[T-001] Task description`
6. **Cleanup** — worktrees are removed and pruned

## Structured workflow logging

The `WorkflowLogger` provides timestamped, levelled, categorised log entries for each worker:

**Log levels:** `DEBUG` · `INFO` · `SUCCESS` · `WARNING` · `ERROR`

**Event categories:** `lifecycle` · `pipeline` · `git` · `junie` · `prompt` · `system`

Each entry renders as both plain text (for raw mode) and Rich markup (for the TUI workflow view), with Gruvbox-themed colors and category icons.

## Install model

The intended install model is self-managed:

- The repository checkout lives in `~/.ocha`
- A virtual environment is maintained at `~/.ocha/.venv`
- The Python package is installed in editable mode from `~/.ocha/ocha`
- The launcher at `~/.local/bin/ocha` points into the venv
- `ocha update` pulls latest changes and refreshes the venv
- The `.env` file (containing `JUNIE_API_KEY`) is preserved across updates

## Environment

ocha looks for `JUNIE_API_KEY` in:

1. The `JUNIE_API_KEY` environment variable
2. A `.env` file in the current directory
3. `~/.ocha/.env`

## Related design notes

- `python-textual-rebuild.md` — concept for rebuilding the experience in Python with Textual
- `junie-headless-sessions.md` — concept for how ocha launches and manages headless Junie worker sessions
