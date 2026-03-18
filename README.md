# ocha

**Multi-agent orchestration for Junie** — decompose tasks, spawn AI coding agents in isolated git worktrees, and coordinate parallel work automatically.

Ocha turns a single Junie session into a multi-agent team. A high-level task is decomposed into independent subtasks, each agent runs in its own git worktree, and the coordinator manages parallel execution with batched concurrency control.

## Overview

```
┌──────────────────────────────────────────────┐
│                  ocha CLI                    │
│  init · cord start · cord status · cord stop │
│              dev · self-update               │
└──────────┬───────────────┬───────────────────┘
           │               │
     ┌─────▼──────┐  ┌─────▼──────┐
     │  Enhance   │  │    Lead    │
     │  (context) │  │  (planner) │
     └─────┬──────┘  └─────┬──────┘
           │               │
     ┌─────▼───────────────▼────────┐
     │      Agent Spawner           │
     │  (parallel Junie processes)  │
     └─────┬───────────────┬────────┘
           │               │
     ┌─────▼──────┐  ┌────▼───────┐
     │  Builder   │  │  Reviewer  │
     │  (worktree)│  │  (checker) │
     └─────┬──────┘  └────┬───────┘
           │               │
     ┌─────▼───────────────▼────────┐
     │        Git Repository        │
     │   main ← PR: ocha/task-1     │
     │        ← PR: ocha/task-2     │
     └──────────────────────────────┘
```

## Prerequisites

- [Node.js](https://nodejs.org/) (v18+)
- [Git](https://git-scm.com/)
- [Junie CLI](https://www.jetbrains.com/junie/) (installed and authenticated)
- [gh CLI](https://cli.github.com/) (for pull request creation)

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

Add to PATH if needed:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc && source ~/.bashrc
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

Or just run `ocha` with no arguments for an interactive multi-line prompt:

```bash
ocha
```

## Commands

### `ocha init`

Initializes the `.ocha/` directory in the current project with role prompt files for each agent type.

```bash
ocha init [-y]
```

**Options:**

| Flag | Description |
|------|-------------|
| `-y, --yes` | Reinitialize even if `.ocha/` already exists (refreshes prompts after an ocha update) |

**What it creates:**

```
.ocha/
└── roles/
    ├── coordinator.md
    ├── lead.md
    ├── builder.md
    └── reviewer.md
```

### `ocha cord start`

Decomposes a high-level task into subtasks and spawns parallel Junie agents to work on them.

```bash
ocha cord start [-t <task>] [-b <branch>] [--max-agents <n>] [-r <path>] [--no-merge]
```

If `-t` is omitted, an interactive multi-line prompt opens so you can type your task directly.

**Options:**

| Flag | Description | Default |
|------|-------------|---------|
| `-t, --task <task>` | High-level task description (omit for interactive prompt) | — |
| `-b, --base-branch <branch>` | Base branch to create worktrees from | `main` |
| `--max-agents <n>` | Maximum number of parallel agents | `3` |
| `-r, --repo <path>` | Repo path(s) to target — repeat for multiple repos | cwd |
| `--no-merge` | Skip auto-merge after completion | — |

**How it works:**

1. Auto-initializes `.ocha/` if not present
2. Validates the git repository and base branch
3. Checks Junie authentication
4. **Enhances** the prompt with project context (git log, source snippets, Junie guidelines)
5. **Lead agent** analyzes the project and produces a structured task plan
6. Falls back to a single builder task if the lead agent fails
7. Writes `.ocha/status.json` to track all task progress
8. Spawns builder agents in batches (up to `--max-agents` at a time), each in its own git worktree on a new branch (`ocha/<task-slug>`)
9. Each builder is retried up to 2 times on failure
10. A **reviewer agent** runs in the same worktree after each builder completes
11. The branch is pushed to origin and a **pull request** is created via `gh`
12. Prints a session summary with PR links when all agents complete

### `ocha cord status`

Displays the current session status including all tasks and their states.

```bash
ocha cord status [-w]
```

**Options:**

| Flag | Description |
|------|-------------|
| `-w, --watch` | Poll and redraw every 3 seconds until the session ends |

**Output shows:**
- Session task description and state
- Each subtask's ID, role, state (⏳ pending / 🔄 running / ✅ completed / ❌ failed)
- Branch names and PR links

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

Runs a single Junie agent in an isolated worktree. Useful for making changes to the ocha source code itself without the running process being modified mid-execution.

```bash
ocha dev -t <task> [-b <branch>] [--no-merge]
```

**Options:**

| Flag | Description | Default |
|------|-------------|---------|
| `-t, --task <task>` | Task description (required) | — |
| `-b, --base-branch <branch>` | Base branch | `main` |
| `--no-merge` | Skip auto-merge after completion | — |

### `ocha self-update`

Updates ocha to the latest version.

```bash
ocha self-update
```

Runs `git pull origin main && npm install` from the install directory (`~/.ocha`).

## Agent Roles

Ocha supports four agent roles, each with a specialized prompt:

| Role | Description |
|------|-------------|
| **coordinator** | Decomposes tasks, spawns sub-agents, and tracks progress. Does not write code directly. |
| **lead** | Analyzes the project and produces a structured task plan for builders. |
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
│   │   ├── init.js          # ocha init command
│   │   ├── cord-start.js    # ocha cord start command
│   │   ├── cord-status.js   # ocha cord status command
│   │   ├── cord-stop.js     # ocha cord stop command
│   │   └── dev.js           # ocha dev command
│   └── lib/
│       ├── agent.js         # Agent spawning, auth check, git push
│       ├── coordinator.js   # Full pipeline: enhance→lead→build→review
│       ├── decompose.js     # Task decomposition via Junie AI
│       ├── enhance.js       # Prompt enhancement with project context
│       ├── files.js         # Safe file I/O utilities
│       ├── lead.js          # Lead agent: project analysis & task planning
│       ├── paths.js         # Shared path constants
│       ├── prompt.js        # Interactive multi-line task prompt
│       ├── roles.js         # Agent role prompt definitions
│       ├── spinner.js       # CLI spinner wrapper
│       ├── status.js        # Session status read/write/update
│       ├── tree.js          # Live agent-tree display
│       └── worktree.js      # Git worktree create/remove/list
├── install.sh               # One-command installer
├── package.json
└── README.md
```

## How It Works

1. **`ocha init`** creates the `.ocha/` directory with role prompt markdown files for each agent type (coordinator, lead, builder, reviewer). Use `--yes` to refresh prompts after updating ocha.

2. **`ocha cord start`** kicks off a full session:
   - The prompt is **enhanced** with project context (recent commits, source snippets, Junie guidelines)
   - A **lead agent** analyzes the project and decomposes the work into independent, parallelizable subtasks
   - Each subtask gets a dedicated git worktree on a new branch (`ocha/<task-name>`)
   - **Builder** agents are spawned as child Junie processes in batches, with up to 2 automatic retries on failure
   - A **reviewer** agent checks each builder's output for bugs, security issues, and code quality
   - The branch is pushed to origin and a **pull request** is opened via `gh`

3. **Status tracking** is maintained in `.ocha/status.json`, recording each task's state, timing, PID, worktree path, and PR URL.

4. **`ocha cord stop`** gracefully terminates all agents (via SIGTERM), cleans up worktrees and the `.ocha/` directory.

5. After completion, **review and merge the open pull requests** shown in the session summary.

## License

ISC
