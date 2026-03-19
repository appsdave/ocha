# ocha — Multi-Agent Orchestration

**Multi-agent orchestration for Junie** — decompose tasks, spawn AI coding agents in isolated git worktrees, and coordinate parallel work automatically.

Ocha turns a single Junie session into a multi-agent team. You describe a high-level task in the TUI, ocha decomposes it, spawns agents in isolated git worktrees, and coordinates parallel execution — each agent opens its own PR when done.

## TUI Layout

```
┌─ Agents ──────────────┬─ Task ──────────────────────────────────────┐
│ ocha/myrepo (2)       │  update the docs  ⟳ running                 │
│ ├─ ● #01 update docs  │  [coordinator] → [lead] → [builder] → [PR]  │
│ │    ⎇ ocha/upd-...   │  ⎇ ocha/update-docs-20250618-143022-a3f2    │
│ └─ ✔ #02 fix tests    ├─ Output ───────────────────────────────────  │
│      ✔ done           │  ✔ Prompt enhanced with project context      │
│                       │  👔 Lead planned 2 task(s)                   │
│                       │  ✓ Builder done: update readme               │
│                       │  ✓ Reviewer approved                         │
│                       │  ─────────────────────────────────────────── │
│                       │  ✅ Agent completed successfully              │
│                       │  PR: https://github.com/org/repo/pull/42     │
└───────────────────────┴─────────────────────────────────────────────┘
  n new  ↑↓ navigate  k kill  c clear done  ←→ switch pane  q quit
  ocha  |  2 task(s)  1 running  1 done  | ocha/update-docs-...
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
cd ~/.ocha
npm install --production
mkdir -p ~/.local/bin
ln -sf ~/.ocha/bin/ocha.js ~/.local/bin/ocha
chmod +x ~/.ocha/bin/ocha.js
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

**Update to latest:**

```bash
ocha self-update
```

## Quick Start

```bash
# 1. Go to your project
cd /path/to/your/project

# 2. Initialize ocha (creates .ocha/ with role prompts)
ocha init

# 3. Launch the TUI
ocha
```

Inside the TUI, press **`n`** to enter a task. Ocha will:
1. Enhance your prompt with project context (coordinator)
2. Decompose it into subtasks (lead agent)
3. Spawn builder agents in isolated git worktrees
4. Run a reviewer on each builder's output
5. Push each result to a unique branch and open a PR

## Commands

### `ocha` (default — launches TUI)

Runs the interactive TUI. No arguments needed.

```bash
ocha
```

### `ocha init`

Initializes `.ocha/` in the current project with role prompt files.

```bash
ocha init        # initialize
ocha init --yes  # reinitialize (refresh prompts after update)
```

Creates:
```
.ocha/
└── roles/
    ├── coordinator.md
    ├── lead.md
    ├── builder.md
    └── reviewer.md
```

### `ocha status`

Shows current session status and task states.

```bash
ocha status        # one-time snapshot
ocha status -w     # watch mode (polls every 3s)
```

### `ocha stop`

Stops all running agents and cleans up worktrees.

```bash
ocha stop
```

### `ocha resolve`

Resolves merge conflicts on a PR branch by rebasing onto the base branch. If conflicts are found during the rebase, a Junie agent is automatically spawned to resolve them.

```bash
ocha resolve --pr 42
ocha resolve --branch ocha/my-feature-branch
ocha resolve --pr 42 -b develop
```

| Flag | Description | Default |
|------|-------------|---------|
| `-p, --pr <number>` | PR number to resolve | — |
| `--branch <name>` | Branch name to resolve (alternative to `--pr`) | — |
| `-b, --base-branch <branch>` | Base branch to rebase onto | `main` |

Flow:
1. Identifies the PR branch (from `--pr` via `gh` or `--branch`)
2. Fetches the latest base branch and PR branch refs
3. Creates a temporary worktree and attempts a rebase
4. If conflicts arise, spawns a Junie agent to resolve them automatically
5. Force-pushes the rebased branch so the PR is mergeable
6. Cleans up the temporary worktree

### `ocha dev`

Runs a task in an isolated dev worktree — safe for self-development on ocha itself.

```bash
ocha dev -t "add retry logic to agent spawner"
ocha dev -t "fix spinner tests" -b develop
ocha dev -t "refactor config loader" --no-merge
```

| Flag | Description | Default |
|------|-------------|---------|
| `-t, --task <task>` | Task description | *(required)* |
| `-b, --base-branch <branch>` | Base branch | `main` |
| `--no-merge` | Skip auto-merge after completion | — |

### `ocha self-update`

Updates ocha to the latest version from GitHub, shows what changed, and re-links the global command.

```bash
ocha self-update
```

### Deprecated: `ocha cord *`

The `ocha cord start`, `ocha cord status`, `ocha cord stop`, and `ocha cord resolve` subcommands still work but are deprecated. Use the top-level equivalents (`ocha status`, `ocha stop`, `ocha resolve`) or the TUI instead. There is no top-level `ocha start` — use the TUI (`ocha`) to launch tasks interactively.

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `n` | Open new task prompt |
| `↑` / `↓` | Navigate agent list |
| `k` | Kill selected agent |
| `c` | Clear completed/failed agents |
| `←` / `h` | Focus agent list |
| `→` / `l` | Focus log pane |
| `q` / `Ctrl+C` | Quit (confirms if agents running) |

## Worktree Naming

Each agent task gets a unique branch:

```
ocha/<slug>-<YYYYMMDD>-<HHMMSS>-<rand>
```

Example: `ocha/update-docs-20250618-143022-a3f2`

Worktrees are created under `.ocha-worktrees/` and cleaned up automatically when the agent finishes.

## Agent Pipeline

```
User task
   │
   ▼
coordinator  — enhances prompt with project context
   │
   ▼
lead agent   — analyzes project, produces subtask plan
   │
   ├──▶ builder #1 (worktree) ──▶ reviewer #1 ──▶ PR
   ├──▶ builder #2 (worktree) ──▶ reviewer #2 ──▶ PR
   └──▶ builder #N (worktree) ──▶ reviewer #N ──▶ PR
```

Each builder runs in its own git worktree on a unique branch. Reviewers check the diff and approve or flag issues. Every task ends with its own pull request.

## Project Structure

```
ocha/
├── bin/
│   └── ocha.js              # CLI entry point
├── src/
│   ├── commands/
│   │   ├── init.js          # ocha init
│   │   ├── dev.js           # ocha dev (safe self-dev mode)
│   │   ├── cord-start.js    # ocha cord start
│   │   ├── cord-status.js   # ocha cord status
│   │   ├── cord-stop.js     # ocha cord stop
│   │   └── cord-resolve.js  # ocha cord resolve
│   └── lib/
│       ├── tui.js           # TUI orchestrator
│       ├── tui-layout.js    # blessed widget construction
│       ├── tui-agents.js    # agent spawn/kill/persist
│       ├── tui-utils.js     # slugify, elapsed, badges
│       ├── coordinator.js   # full pipeline runner
│       ├── lead.js          # lead agent (task planner)
│       ├── decompose.js     # task decomposition logic
│       ├── enhance.js       # prompt enhancer
│       ├── agent.js         # Junie process spawner
│       ├── beads.js         # beads (bd) issue tracker integration
│       ├── worktree.js      # git worktree management
│       ├── issues.js        # agent issue feed
│       ├── files.js         # filesystem helpers
│       ├── status.js        # .ocha/status.json r/w
│       ├── paths.js         # shared path constants
│       ├── prompt.js        # prompt utilities
│       ├── roles.js         # role prompt installer
│       ├── tree.js          # directory tree builder
│       ├── ui.js            # terminal box/progress utilities
│       ├── spinner.js       # ora spinner helpers
│       ├── exec.js          # safe command execution utilities
│       ├── validate.js      # input validation helpers
│       └── test-reporter.js # custom test reporter
└── install.sh               # one-liner installer
```

## Development

### Running Tests

```bash
npm test
```

Tests use Node.js built-in test runner with a custom reporter (`src/lib/test-reporter.js`).

### Linting & Formatting

```bash
npm run lint          # check for lint errors
npm run lint:fix      # auto-fix lint errors
npm run format:check  # check formatting
npm run format        # auto-format
```

### Issue Tracking

This project uses [beads (bd)](https://github.com/appsdave/beads) for issue tracking. See `AGENTS.md` for the full workflow.

```bash
bd ready              # find available work
bd show <id>          # view issue details
bd update <id> --claim  # claim work
bd close <id>         # complete work
```

