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
  n new  ↑↓ navigate  K kill  C clear done  ←→ switch pane  q quit
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

### `ocha cord start`

Decomposes a task and runs it across parallel agents in isolated git worktrees.

```bash
ocha cord start -t "refactor auth flow"
ocha cord start -t "add user settings page" -b develop -n 5
ocha cord start -t "update docs" --no-merge
```

| Flag | Description | Default |
|------|-------------|---------|
| `-t, --task <task>` | High-level task description | *(required)* |
| `-b, --base-branch <branch>` | Base git branch for worktrees | `main` |
| `-n, --max-agents <n>` | Maximum parallel agents | `3` |
| `-r, --repo <path...>` | Repo path(s) to operate on | cwd |
| `--no-merge` | Skip auto-merge after completion | — |

### `ocha cord status`

Shows current session status and task states.

```bash
ocha cord status        # one-time snapshot
ocha cord status -w     # watch mode (polls every 3s)
```

### `ocha cord stop`

Stops all running agents and cleans up worktrees.

```bash
ocha cord stop
```

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

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `n` | Open new task prompt |
| `↑` / `↓` | Navigate agent list |
| `K` | Kill selected agent |
| `C` | Clear completed/failed agents |
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
│   │   └── cord-stop.js     # ocha cord stop
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
│       ├── worktree.js      # git worktree management
│       ├── beads.js         # beads issue-tracking integration
│       ├── issues.js        # agent issue feed
│       ├── files.js         # filesystem helpers
│       ├── status.js        # .ocha/status.json r/w
│       ├── paths.js         # shared path constants
│       ├── prompt.js        # prompt utilities
│       ├── roles.js         # role prompt installer
│       ├── tree.js          # directory tree builder
│       ├── ui.js            # terminal box/progress utilities
│       ├── spinner.js       # ora spinner helpers
│       └── test-reporter.js # custom test reporter
├── install.sh               # one-liner installer
└── .github/
    └── workflows/
        ├── junie-review.yml # Junie AI code review on PRs
        └── junie-tag.yml    # Junie triggered by label
```

## GitHub Actions

### Junie Code Review

Every PR automatically gets an AI code review from Junie. Requires `JUNIE_API_KEY` in repository secrets (Settings → Secrets and variables → Actions).

### Junie Label Trigger

Add the `junie` label to any issue or PR to trigger a Junie run. Also requires `JUNIE_API_KEY` in repository secrets.
