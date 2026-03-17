# ocha — Implementation Overview

## What is ocha?

`ocha` is a multi-agent orchestration CLI that spawns Junie AI agents across isolated git worktrees to complete tasks in parallel. Each agent works on its own branch, and results are automatically reviewed, merged, and pushed.

---

## Architecture

```
ocha cord start -t 'your task'
        │
        ├─ 🔐 Auth check (junie --version)
        ├─ 📋 Decompose task → subtasks (Junie in temp dir)
        ├─ 👔 Lead review → refines each subtask prompt
        └─ 🎯 Coordinator loop
              ├─ git worktree add  (isolated branch per task)
              ├─ Builder agent     (Junie --brave in worktree)
              ├─ Reviewer agent    (Junie --brave in same worktree)
              └─ Auto-merge → push → cleanup worktree
```

### Agent Hierarchy

| Role        | Responsibility |
|-------------|----------------|
| Coordinator | Decomposes tasks, manages the session loop |
| Lead        | Refines subtask prompts before passing to builders |
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

### `ocha cord start -t '<task>' [--base <branch>] [--no-merge]`
Main orchestration command. Full flow:

1. Initializes `.ocha/` if not present
2. Checks Junie authentication
3. Decomposes the task into subtasks (Junie runs in a temp dir — no project changes)
4. Lead agent reviews and refines each subtask prompt
5. For each subtask (up to 3 in parallel):
   - Creates a git worktree on a new branch (`ocha/<task-slug>`)
   - Spawns a builder agent (`junie --brave --project <worktree>`)
   - Spawns a reviewer agent in the same worktree
   - On pass: auto-merges branch into base, pushes to origin, removes worktree
   - On conflict: falls back to `git merge -X theirs`, then creates a PR via `gh`
6. Prints a session summary

Supports comma-separated tasks: `-t 'task one, task two, task three'`

---

### `ocha cord status`
Reads `.ocha/status.json` and displays current session progress — running, completed, and failed tasks.

---

### `ocha cord stop`
Kills all running agent processes (by PID from status file), removes all active worktrees, and cleans up `.ocha/`.

---

### `ocha dev -t '<task>' [--base <branch>] [--no-merge]`
Runs a single Junie agent in an isolated worktree specifically for making changes to the ocha source code itself. Prevents the running ocha process from being modified mid-execution.

Flow: auth check → create worktree on `ocha-dev-session` branch → spawn Junie `--brave` → auto-merge back into base → cleanup.

---

### `ocha self-update`
Runs `git pull origin main && npm install` from the install directory (`~/.ocha`) to update ocha to the latest version.

---

## File Structure

```
ocha/
├── bin/
│   └── ocha.js              # CLI entry point (Commander.js)
├── src/
│   ├── commands/
│   │   ├── init.js          # ocha init
│   │   ├── cord-start.js    # ocha cord start
│   │   ├── cord-status.js   # ocha cord status
│   │   ├── cord-stop.js     # ocha cord stop
│   │   └── dev.js           # ocha dev
│   └── lib/
│       ├── agent.js         # Spawn Junie agents, auth check, git push
│       ├── coordinator.js   # Task loop, lead review, merge/cleanup
│       ├── decompose.js     # Task decomposition via Junie
│       ├── worktree.js      # git worktree create/remove
│       ├── status.js        # Read/write .ocha/status.json
│       ├── roles.js         # Role prompt templates
│       ├── paths.js         # Shared path constants
│       ├── files.js         # Safe file I/O utilities
│       └── spinner.js       # CLI spinner wrapper
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
- `gh` CLI (for PR creation fallback)

---

## Key Design Decisions

- **Worktree isolation** — every agent gets its own `git worktree` so agents never conflict with each other or the running ocha process
- **Brave mode** — all agents run with `--brave` so they don't pause for confirmations
- **Coordinator doesn't code** — the decompose step runs in a temp directory; only builder/reviewer agents touch project files
- **Auto-merge with fallback** — normal merge first, then `-X theirs` on conflict, then PR creation as last resort
- **Stash before merge** — local uncommitted changes are stashed before merging agent branches to prevent conflicts
- **Git validation** — `cord start` checks for a valid git repo and base branch before doing anything, with clear fix instructions if not set up
- **npm link symlink** — the global `ocha` command is a symlink to the source directory, so all changes are live immediately without reinstalling
