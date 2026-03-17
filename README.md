# ocha

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
curl -fsSL https://raw.githubusercontent.com/appsdave/ocha/main/install.sh | bash
```

**Or manually:**

```bash
git clone https://github.com/appsdave/ocha.git ~/.ocha
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
ocha cord start -t <task> [-b <branch>] [--max-agents <n>]
```

**Options:**

| Flag | Description | Default |
|------|-------------|---------|
| `-t, --task <task>` | High-level task description (required) | — |
| `-b, --base-branch <branch>` | Base branch to create worktrees from | `main` |
| `--max-agents <n>` | Maximum number of parallel agents | `3` |

**How it works:**

1. Auto-initializes `.ocha/` if not present
2. Uses Junie to decompose the task into independent subtasks (with a 2-minute timeout)
3. Falls back to a single builder task if decomposition fails
4. Creates a `status.json` to track all task progress
5. Spawns agents in batches (up to `--max-agents` at a time)
6. Each agent gets its own git worktree and branch (prefixed with `ocha/`)
7. Prints a summary with merge commands when all agents complete

### `ocha cord status`

Displays the current session status including all tasks and their states.

```bash
ocha cord status
```

**Output shows:**
- Session task description and state
- Each subtask's ID, role, state (⏳ pending / 🔄 running / ✅ completed / ❌ failed)
- Branch names and worktree paths

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

## Agent Roles

Ocha supports four agent roles, each with a specialized prompt:

| Role | Description |
|------|-------------|
| **coordinator** | Decomposes tasks, spawns sub-agents, and tracks progress. Does not write code directly. |
| **lead** | Plans implementation, coordinates with the codebase, implements solutions, and documents changes. |
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
│   │   └── cord-stop.js      # ocha cord stop command
│   └── lib/
│       ├── agent.js          # Agent spawning and lifecycle management
│       ├── coordinator.js    # Batched parallel agent coordination
│       ├── decompose.js      # Task decomposition via Junie AI
│       ├── paths.js          # Shared path constants
│       ├── roles.js          # Agent role prompt definitions
│       ├── status.js         # Session status read/write/update
│       └── worktree.js       # Git worktree create/remove/list
├── package.json
└── README.md
```

## How It Works

1. **`ocha init`** creates the `.ocha/` directory with role prompt markdown files for each agent type (coordinator, lead, builder, reviewer).

2. **`ocha cord start`** kicks off a full session:
   - The task is sent to Junie for AI-powered decomposition into independent, parallelizable subtasks
   - Each subtask gets a dedicated git worktree on a new branch (`ocha/<task-name>`)
   - Agents are spawned as child Junie processes, running in batches for controlled parallelism
   - Agent output is filtered to show only key events (results, errors, commits)

3. **Status tracking** is maintained in `.ocha/status.json`, recording each task's state, timing, PID, worktree path, and results.

4. **`ocha cord stop`** gracefully terminates all agents (via SIGTERM), cleans up worktrees and the `.ocha/` directory.

5. After completion, **merge completed branches** back into your main branch using the git commands shown in the session summary.

## License

ISC
