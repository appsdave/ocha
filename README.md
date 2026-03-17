# ocha

**Junie-only multi-agent orchestration** — spawn AI coding agents in isolated git worktrees, coordinate them via SQLite mail, and merge their work back with conflict resolution.

Ocha turns a single Junie session into a multi-agent team. Each agent runs in its own git worktree and tmux session, communicating through a shared SQLite-based mail system. When agents finish their tasks, ocha merges branches back with tiered conflict resolution.

## Overview

```
┌─────────────────────────────────────────────────┐
│                   ocha CLI                      │
│  init · sling · status · mail · merge · stop    │
└──────────┬──────────┬──────────┬────────────────┘
           │          │          │
     ┌─────▼──┐  ┌────▼───┐  ┌──▼──────┐
     │Worktree│  │  Mail   │  │  Merge  │
     │Manager │  │(SQLite) │  │  Queue  │
     └────────┘  └────────┘  └─────────┘
           │          │          │
     ┌─────▼──────────▼──────────▼────────┐
     │         Git Repository             │
     │  main ← ocha/agent-a               │
     │       ← ocha/agent-b               │
     └───────────────────────────────────-─┘
```

## Project Structure

| Directory      | Description                                              |
| -------------- | -------------------------------------------------------- |
| `junietree/`   | Core CLI package — TypeScript/Bun, all commands and libs |
| `overstory/`   | Reserved for future high-level orchestration tooling     |
| `tmp-ocha-test/` | Test fixture for ocha project initialization           |

## Quick Start

### Prerequisites

- [Bun](https://bun.sh/) (v1.1+)
- [Git](https://git-scm.com/)
- [tmux](https://github.com/tmux/tmux)
- [Junie CLI](https://www.jetbrains.com/junie/) (authenticated)

### Install

```bash
cd junietree
bun install
bun run build

# Link the CLI globally
bun link
```

### Usage

```bash
# 1. Initialize ocha in your project
cd /path/to/your/project
ocha init

# 2. Spawn a builder agent
ocha sling --name auth-builder --capability builder --spec "Implement auth module"

# 3. Check agent status
ocha status

# 4. Send mail between agents
ocha mail send --from coordinator --to auth-builder --subject "Priority change" --body "Focus on OAuth first"
ocha mail check --agent auth-builder

# 5. Merge agent work back
ocha merge --agent auth-builder

# 6. Stop an agent
ocha stop auth-builder
```

## Commands

| Command                  | Description                                        |
| ------------------------ | -------------------------------------------------- |
| `ocha init`              | Initialize `.ocha/` directory and agent definitions |
| `ocha sling [task-id]`   | Spawn a worker agent in an isolated git worktree   |
| `ocha status`            | Show all active agents, their state, and health    |
| `ocha mail send\|check\|list` | Inter-agent messaging via SQLite mail         |
| `ocha merge`             | Merge agent branches with conflict resolution      |
| `ocha stop <agent>`      | Kill tmux session, remove worktree, update manifest |

See [`junietree/README.md`](junietree/README.md) for detailed command reference and architecture documentation.

## Agent Roles

Ocha supports four agent capabilities (roles):

| Role            | Description                                                  |
| --------------- | ------------------------------------------------------------ |
| **coordinator** | Decomposes tasks, spawns sub-agents, and tracks progress     |
| **builder**     | Implements assigned subtasks in a dedicated worktree          |
| **scout**       | Explores the codebase, gathers context, and reports findings |
| **reviewer**    | Reviews code changes and provides feedback                   |

Agent role definitions live in `agents/*.md` and are deployed as `.junie/guidelines.md` overlays into each worktree.

## How It Works

1. **`ocha init`** sets up the `.ocha/` directory with a manifest, database directory, and agent definitions.
2. **`ocha sling`** creates a git worktree on a new branch (`ocha/<agent-name>`), generates a guidelines overlay from the agent's role definition, and launches Junie in a tmux session.
3. Agents communicate through **SQLite mail** — a shared database with `send`, `check`, and `list` operations. Messages have priorities and thread IDs.
4. A **watchdog** monitors agent health by checking tmux session liveness and process status.
5. **`ocha merge`** queues branches for merge, runs `git merge`, and applies conflict resolution strategies when needed.
6. **`ocha stop`** gracefully terminates an agent's tmux session, optionally removes the worktree, and updates the manifest.

## License

MIT
