# ocha — Implementation Overview

## What is ocha?

`ocha` is a multi-agent orchestration CLI that spawns Junie AI agents across isolated git worktrees to complete tasks in parallel. Each agent works on its own branch; results are reviewed by a reviewer agent, then the branch is pushed and a PR is opened for human review.

---

## Architecture

```
ocha cord start -t 'your task'
        │
        ├─ 🔐 Auth check (junie --version)
        ├─ 🧠 Enhance prompt with project context
        ├─ 👔 Lead agent → JSON task plan
        └─ 🎯 Coordinator loop (per task, up to N parallel)
              ├─ git worktree add  (isolated branch per task)
              ├─ Builder agent     (Junie --brave, up to 2 retries)
              ├─ Reviewer agent    (Junie --brave in same worktree)
              └─ git push → gh pr create → cleanup worktree
```

### Agent Hierarchy

| Role        | Responsibility |
|-------------|----------------|
| Coordinator | Decomposes tasks, manages the session loop |
| Lead        | Analyzes the project, outputs a JSON task plan — does not write code |
| Builder     | Implements the actual code changes in a worktree |
| Reviewer    | Checks builder output for bugs, security, quality |

Role prompts live in `.ocha/roles/` and are injected into each agent's task.

---

## Commands

### `ocha init [--yes]`
Creates `.ocha/` in the current project with role prompt files:
- `.ocha/roles/coordinator.md`
- `.ocha/roles/lead.md`
- `.ocha/roles/builder.md`
- `.ocha/roles/reviewer.md`

Use `--yes` to reinitialize if `.ocha/` already exists (refreshes prompts after an ocha update).

---

### `ocha cord start -t '<task>' [-b <branch>] [--max-agents <n>] [-r <repo>]`
Main orchestration command. Full flow:

1. Initializes `.ocha/` if not present
2. Validates git repo and base branch
3. Checks Junie authentication
4. **Enhances** the prompt with project context (file tree, git log, guidelines, source snippets)
5. **Lead agent** analyzes the project and outputs a JSON task plan; falls back to a single builder task on failure
6. For each subtask (up to `--max-agents` in parallel, default 3):
   - Creates a git worktree on a new branch (`ocha/<task-slug>`)
   - Spawns a **builder agent** (`junie --brave --project <worktree>`), with up to **2 automatic retries** on failure (3 total attempts)
   - Spawns a **reviewer agent** in the same worktree to check for bugs, security issues, and quality
   - Pushes the branch to origin and **opens a PR** via `gh` (always — regardless of `--no-merge`)
7. Prints a session summary with PR links

If `-t` is omitted, an interactive multi-line prompt opens.

Supports multiple repos: `-r ~/projects/api -r ~/projects/frontend` (tasks distributed round-robin).

---

### `ocha cord status`
Reads `.ocha/status.json` and displays current session progress — running, completed, and failed tasks.

---

### `ocha cord stop`
Kills all running agent processes (by PID from status file), removes all active worktrees, and cleans up `.ocha/`.

---

### `ocha dev -t '<task>' [--base <branch>] [--no-merge]`
Runs a single Junie agent in an isolated worktree specifically for making changes to the ocha source code itself. Prevents the running ocha process from being modified mid-execution.

Flow: auth check → create worktree on `ocha-dev-session` branch → spawn Junie `--brave` → push branch → merge back into base branch (unless `--no-merge`) → cleanup worktree.

---

### `ocha self-update`
Runs `git pull --rebase` from the install directory (`~/.ocha`), then `npm install --production` and re-links the global `ocha` command. Prints a summary of commits added since the previous version.

---

## File Structure

```
ocha/
├── bin/
│   └── ocha.js              # CLI entry point (Commander.js); launches TUI when run bare
├── src/
│   ├── commands/
│   │   ├── init.js          # ocha init
│   │   ├── cord-start.js    # ocha cord start
│   │   ├── cord-status.js   # ocha cord status
│   │   ├── cord-stop.js     # ocha cord stop
│   │   └── dev.js           # ocha dev
│   └── lib/
│       ├── agent.js         # Spawn Junie agents, auth check, git push
│       ├── beads.js         # beads (bd) issue tracker integration
│       ├── coordinator.js   # Task loop, batched agent concurrency
│       ├── decompose.js     # Task decomposition via Junie
│       ├── enhance.js       # Prompt enhancement with project context
│       ├── files.js         # Safe file I/O utilities
│       ├── issues.js        # Agent issue feed (problems, warnings, notes)
│       ├── lead.js          # Lead agent runner (produces task plan JSON)
│       ├── paths.js         # Shared path constants
│       ├── prompt.js        # Interactive multi-line task prompt
│       ├── roles.js         # Role prompt templates
│       ├── spinner.js       # CLI spinner wrapper
│       ├── status.js        # Read/write .ocha/status.json
│       ├── test-reporter.js # Custom Node.js test reporter
│       ├── tree.js          # Live agent progress tree renderer
│       ├── tui.js           # OchaTUI class — main TUI controller
│       ├── tui-agents.js    # TUI agent spawn/kill/persist helpers
│       ├── tui-layout.js    # blessed screen layout and prompt dialog
│       ├── tui-utils.js     # TUI display utilities (elapsed, badges, truncation)
│       ├── ui.js            # Shared UI helper utilities
│       └── worktree.js      # git worktree create/remove/list/lookup/clean
├── install.sh               # One-command installer
└── .ocha/                   # Per-project config (gitignored)
    ├── status.json
    └── roles/
        ├── coordinator.md
        ├── lead.md
        ├── builder.md
        └── reviewer.md
```

---

## Installation

```bash
git clone git@github.com:appsdave/ocha.git ~/.ocha \
  && cd ~/.ocha \
  && npm install \
  && ln -sf ~/.ocha/bin/ocha.js ~/.local/bin/ocha
```

Add to PATH if needed:
```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc && source ~/.bashrc
```

### Prerequisites
- Node.js v18+
- Git
- Junie CLI (installed and authenticated)
- `gh` CLI (required for PR creation)

---

## Worktree Management

Each agent runs inside an isolated `git worktree` created under `<project>/.ocha-worktrees/`.
The `src/lib/worktree.js` module is the single source of truth for all worktree operations.

### API

| Function | Description |
|---|---|
| `createWorktree(branch, baseBranch?, repoDir?)` | Creates a worktree for `branch` off `baseBranch`. Returns the path. Idempotent — safe to call if the directory already exists. |
| `removeWorktree(worktreePath, repoDir?)` | Force-removes a worktree. Returns `true` on success or if the path never existed, `false` on git error. |
| `listWorktrees(repoDir?)` | Returns all registered worktrees as `{ path, branch?, bare? }` objects. |
| `getWorktreeForBranch(branch, repoDir?)` | Looks up the worktree path for a given branch name. Returns `null` if not found. |
| `cleanOchaWorktrees(repoDir?, branchPrefix?)` | Bulk-removes all worktrees whose branch starts with `refs/heads/ocha/` (or a custom prefix). Returns `{ removed, failed }` path lists. |

### Lifecycle

```
createWorktree('ocha/task-1', 'main')
  → .ocha-worktrees/ocha-task-1/   ← agent works here

getWorktreeForBranch('ocha/task-1')
  → '/abs/path/.ocha-worktrees/ocha-task-1'

removeWorktree(path)               ← called after agent finishes / on cord stop

cleanOchaWorktrees()               ← session-level cleanup, removes all ocha/* trees
```

### Naming convention

Branch names follow the pattern `ocha/<task-slug>`. The slash is replaced with a dash
when constructing the directory name, so `ocha/task-1` maps to `.ocha-worktrees/ocha-task-1`.

### Error handling

- `createWorktree` retries branch creation: if the branch already exists it is deleted and
  re-created from `baseBranch`; as a last resort the existing branch is reused as-is.
- `removeWorktree` catches git errors and returns `false` instead of throwing, so callers
  can log warnings without crashing the session loop.
- `cleanOchaWorktrees` prunes stale git registrations before and after bulk removal.

---

## TUI (Interactive Dashboard)

Running `ocha` with no arguments launches the interactive TUI — a persistent, btop/lazygit-style terminal dashboard.

### Layout

```
┌─ Agents ──────┬─ Log ──────────────────────────────┐
│ [agent list]  │ [selected agent live log]           │
└───────────────┴─────────────────────────────────────┘
[ hint bar                                            ]
[ status bar                                          ]
```

### Keyboard shortcuts

| Key | Action |
|-----|--------|
| `n` | Open new-task prompt |
| `↑` / `↓` | Navigate agent list |
| `K` | Kill selected agent |
| `l` / `→` | Focus log pane |
| `h` / `←` | Focus agent list |
| `C` / `Shift+C` / `x` | Clear completed agents |
| `q` / `Ctrl+C` | Quit (confirms if agents running) |

### TUI modules

| Module | Responsibility |
|--------|----------------|
| `tui.js` | `OchaTUI` class — screen lifecycle, key bindings, render loop |
| `tui-layout.js` | Builds the blessed screen, panels, and new-task prompt dialog |
| `tui-agents.js` | Spawns agents via `--tui-agent` mode, kills them, persists state across restarts |
| `tui-utils.js` | Display helpers: elapsed time, status badges, task truncation |

### `--tui-agent` internal mode

When the TUI spawns a task it re-invokes `ocha --tui-agent --task <task> --branch <branch>`, which runs a single `cord start` with `maxAgents=1` and streams output back to the TUI log pane.

---

## Issue Tracking

Ocha integrates with [beads (bd)](https://github.com/appsdave/beads) for issue tracking across multi-agent sessions. The `src/lib/beads.js` module handles:

- Creating and claiming issues before agent work begins
- Closing issues when work completes
- Linking discovered sub-issues back to parent tasks via `discovered-from` dependencies

See `AGENTS.md` for the full bd workflow.

---

## Key Design Decisions

- **Worktree isolation** — every agent gets its own `git worktree` so agents never conflict with each other or the running ocha process
- **Brave mode** — all agents run with `--brave` so they don't pause for confirmations
- **Coordinator doesn't code** — the decompose step runs in a temp directory; only builder/reviewer agents touch project files
- **Push + PR always** — after each builder/reviewer pair completes, the branch is pushed to origin and a PR is opened via `gh`; no auto-merge occurs
- **Builder retries** — each builder is retried up to 2 times (3 total attempts) before being marked failed
- **Git validation** — `cord start` checks for a valid git repo and base branch before doing anything, with clear fix instructions if not set up
- **npm link symlink** — the global `ocha` command is a symlink to the source directory, so all changes are live immediately without reinstalling
- **Issue tracking** — beads (bd) provides dependency-aware, Dolt-powered issue tracking that prevents conflicts in multi-agent workflows
