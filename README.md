# ocha — Multi-Agent Orchestration

**Multi-agent orchestration for Junie** — decompose tasks, spawn AI coding agents in isolated git worktrees, and coordinate parallel work automatically.

Ocha turns a single Junie session into a multi-agent team. A high-level task is decomposed into independent subtasks, each agent runs in its own git worktree, and the coordinator manages parallel execution with batched concurrency control.

## Overview

```
┌──────────────────────────────────────────────┐
│                  ocha CLI                    │
│       init · cord start · cord status        │
│                cord stop                     │
└──────────┬───────────────┬───────────────────┘
           │               │
     ┌─────▼──────┐  ┌─────▼──────┐
     │  Decompose  │  │ Coordinator│
     │  (Junie AI) │  │   Loop     │
     └─────┬──────┘  └─────┬──────┘
           │               │
     ┌─────▼───────────────▼────────┐
     │      Agent Spawner           │
     │  (parallel Junie processes)  │
     └─────┬───────────────┬────────┘
           │               │
     ┌─────▼──────┐  ┌────▼───────┐
     │  Worktree   │  │  Status    │
     │  Manager    │  │  Tracker   │
     └─────┬──────┘  └────┬───────┘
           │               │
     ┌─────▼───────────────▼────────┐
     │        Git Repository        │
     │   main ← ocha/task-1         │
     │        ← ocha/task-2         │
     └─────────────────────────────-┘
```

## Prerequisites

- [Node.js](https://nodejs.org/) (v18+)
- [Git](https://git-scm.com/)
- [Junie CLI](https://www.jetbrains.com/junie/) (installed and authenticated)

## Installation

**One-liner** (clones to `~/.ocha` and adds `ocha` to your PATH):

```bash
git clone git@github.com:appsdave/ocha.git /tmp/ocha-install && bash /tmp/ocha-install/install.sh && rm -rf /tmp/ocha-install
```

**Or manually:**

```bash
git clone git@github.com:appsdave/ocha.git ~/.ocha
cd ~/.ocha && npm install
ln -sf ~/.ocha/bin/ocha.js ~/.local/bin/ocha
```

**Update to latest:**

```bash
ocha self-update
```

## Quick Start

```bash
# 1. Initialize ocha in your project
cd /path/to/your/project
ocha init

# 2. Start a coordinated multi-agent session
ocha cord start -t "Implement user authentication with OAuth2"

# 3. Check progress while agents are running
ocha cord status

# 4. Stop the session and clean up
ocha cord stop
```

## Commands

### `ocha init`

Initializes the `.ocha/` directory in the current project with role prompt files for each agent type.

```bash
ocha init
```

**What it creates:**

```
.ocha/
└── roles/
    ├── coordinator.md
    ├── lead.md
    ├── builder.md
    └── reviewer.md
```

If `.ocha/` already exists, the command will warn you to remove it first or run `ocha cord stop`.

### `ocha cord start`

Decomposes a high-level task into subtasks and spawns parallel Junie agents to work on them.

```bash
ocha cord start [-t <task>] [-b <branch>] [--max-agents <n>] [-r <repo>]
```

If `-t` is omitted, an interactive multi-line prompt opens so you can type your task directly.

**Options:**

| Flag | Description | Default |
|------|-------------|---------|
| `-t, --task <task>` | High-level task description (omit for interactive prompt) | — |
| `-b, --base-branch <branch>` | Base branch to create worktrees from | `main` |
| `--max-agents <n>` | Maximum number of parallel agents | `3` |
| `--no-merge` | Skip auto-merge after completion (kept for compatibility) | — |
| `-r, --repo <path>` | Repo path(s) to target — repeat for multiple repos | cwd |

**How it works:**

1. Auto-initializes `.ocha/` if not present
2. Validates git repo and base branch exist
3. Enhances the prompt with project context (file tree, git info, guidelines)
4. Runs a **lead agent** to analyze the project and produce a JSON task plan
5. Falls back to a single builder task if the lead agent fails
6. Creates a `status.json` to track all task progress
7. Spawns builder agents in batches (up to `--max-agents` at a time), each with up to 2 retries on failure
8. Each builder gets its own git worktree and branch (prefixed with `ocha/`)
9. After each builder, a **reviewer agent** checks the changes for bugs, security issues, and quality
10. Pushes the branch to origin and opens a PR via `gh`
11. Prints a session summary with PR links when all agents complete

**Multi-repo support:** pass `-r` multiple times to distribute tasks across different repos:

```bash
ocha cord start -t "Sync auth module" -r ~/projects/api -r ~/projects/frontend
```

### `ocha cord status`

Displays the current session status including all tasks and their states.

```bash
ocha cord status
```

**Output shows:**
- Session task description and state
- Each subtask's ID, role, state (⏳ pending / 🔄 running / ✅ completed / ❌ failed)
- Branch names and worktree paths
- PR links for completed tasks

### `ocha cord stop`

Stops all running agents, removes worktrees, and cleans up the `.ocha/` directory.

```bash
ocha cord stop
```

**What it does:**

1. Kills all in-memory agent processes
2. Kills agents by PID from the status file (for cross-process stops)
3. Removes all git worktrees created by the session
4. Removes the `.ocha-worktrees/` and `.ocha/` directories
5. Marks the session as stopped

### `ocha dev`

Runs a single Junie agent in an isolated worktree to make changes to the ocha source code itself, preventing the running ocha process from being modified mid-execution.

```bash
ocha dev -t "<task>"
```

Flow: auth check → create worktree on `ocha-dev-session` branch → spawn Junie `--brave` → push branch + open PR → cleanup.

### `ocha self-update`

Updates ocha to the latest version by pulling from the remote and reinstalling dependencies.

```bash
ocha self-update
```

Runs `git pull origin main && npm install` from the install directory (`~/.ocha`).

## Agent Roles

Ocha supports four agent roles, each with a specialized prompt:

| Role | Description |
|------|-------------|
| **coordinator** | Decomposes tasks, spawns sub-agents, and tracks progress. Does not write code directly. |
| **lead** | Analyzes the project and produces a JSON task plan for builder agents. Does not write code. |
| **builder** | Implements assigned subtasks, writes tests, follows project conventions, and commits work. |
| **reviewer** | Reviews code changes for bugs, security issues, and style violations. Reports findings without making changes. |

Role prompts are stored in `.ocha/roles/` and are automatically prepended to each agent's task description when spawned.

## Project Structure

```
ocha/
├── bin/
│   └── ocha.js              # CLI entry point (commander-based)
├── src/
│   ├── commands/
│   │   ├── init.js           # ocha init command
│   │   ├── cord-start.js     # ocha cord start command
│   │   ├── cord-status.js    # ocha cord status command
│   │   ├── cord-stop.js      # ocha cord stop command
│   │   └── dev.js            # ocha dev command
│   └── lib/
│       ├── agent.js          # Agent spawning and lifecycle management
│       ├── coordinator.js    # Batched parallel agent coordination
│       ├── decompose.js      # Task decomposition via Junie AI
│       ├── enhance.js        # Prompt enhancement with project context
│       ├── files.js          # Safe file I/O utilities
│       ├── lead.js           # Lead agent runner (produces task plan JSON)
│       ├── paths.js          # Shared path constants
│       ├── prompt.js         # Interactive multi-line task prompt
│       ├── roles.js          # Agent role prompt definitions
│       ├── spinner.js        # CLI spinner wrapper
│       ├── status.js         # Session status read/write/update
│       ├── tree.js           # Live agent progress tree renderer
│       └── worktree.js       # Git worktree create/remove/list
├── install.sh               # One-command installer
├── package.json
└── README.md
```

## How It Works

1. **`ocha init`** creates the `.ocha/` directory with role prompt markdown files for each agent type (coordinator, lead, builder, reviewer).

2. **`ocha cord start`** kicks off a full session:
   - The raw task is **enhanced** with project context (file tree, git log, guidelines, source snippets)
   - A **lead agent** analyzes the project and outputs a JSON plan of independent subtasks
   - Each subtask gets a dedicated git worktree on a new branch (`ocha/<task-slug>`)
   - **Builder agents** are spawned as child Junie processes in batches (up to `--max-agents` parallel), with up to 2 automatic retries per task
   - A **reviewer agent** checks each builder's output for bugs, security issues, and quality
   - Each completed branch is pushed to origin and a **PR is opened** via the `gh` CLI

3. **Status tracking** is maintained in `.ocha/status.json`, recording each task's state, timing, PID, worktree path, and PR URL.

4. **`ocha cord stop`** gracefully terminates all agents (via SIGTERM), cleans up worktrees and the `.ocha/` directory.

5. After completion, **review and merge the open PRs** listed in the session summary.

## License

ISC

## Changelog
- v1.0.0: Initial release with cord-start, cord-status, cord-stop, dev, init, and self-update commands
