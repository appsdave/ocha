# ocha Documentation Notes

This folder is a concept-focused explanation of what `ocha` does today and how its terminal UI works.

## Python rebuild command surface

The current Python/Textual rebuild now ships a small command surface behind `ocha`:

- `ocha` or `ocha tui` — launch the Textual dashboard
- `ocha download [target]` — clone the canonical repo checkout from `git@github.com:appsdave/ocha.git`
- `ocha update [target]` — fast-forward an existing checkout from `origin/main`

If no target is provided for `download` or `update`, `ocha` uses `~/.local/share/ocha/checkout`.

## What ocha is

`ocha` is a Node.js CLI/TUI for orchestrating multiple Junie coding agents against one git repository.

At a high level, it does this:

1. You enter one high-level task in the TUI.
2. A **coordinator** enhances that task with project context.
3. A **lead agent** breaks the task into smaller builder tasks.
4. Each builder task runs in its own **isolated git worktree** while sharing the same repo branch model.
5. A **reviewer agent** checks each builder result.
6. The result is synchronized carefully so parallel worktrees do not step on each other.

That means `ocha` is really two things at once:

- a **workflow engine** for multi-agent coding
- a **terminal dashboard** for watching and controlling that workflow

## Current runtime stack

- CLI parsing: `commander`
- TUI rendering: `blessed`
- styling/output: `chalk`
- spinners: `ora`
- language/runtime: Node.js

Main entrypoint:

- `bin/ocha.js`

Main implementation areas:

- `src/lib/tui.js` — TUI shell behavior
- `src/lib/tui-layout.js` — TUI widget layout
- `src/lib/tui-agents.js` — agent spawning and persisted state
- `src/lib/coordinator.js` — orchestration pipeline
- `src/lib/lead.js` — task planning and work allocation
- `src/lib/worktree.js` — isolated worktree lifecycle

## The concept of how the TUI works

The current TUI is not a text editor. It is closer to a lightweight operations console.

Its job is to let you:

- submit a new high-level task
- see all spawned agent sessions in one place
- inspect the selected task's state and output
- switch between a simplified workflow summary and raw logs
- kill or clear finished agents

### Layout model

The screen is split into 4 functional areas:

1. **Left sidebar: Agents list**
   - shows all known agent sessions
   - shows status badges like running, completed, failed, stopped
   - keeps the selected agent highlighted

2. **Top-right: Task header**
   - shows the selected task title
   - shows branch/state context
   - shows pipeline progress in a compact form

3. **Bottom-right: Output pane**
   - shows either a workflow-style summary or raw logs
   - includes completion summaries with branch, duration, and PR link
   - is intentionally wrapped/structured so long lines do not bleed across the UI

4. **Bottom bars**
   - hint bar for keybindings
   - status bar for task counts and selected branch/session info

### Interaction model

The TUI is keyboard-first.

Current keybindings in the code:

- `n` — open new task dialog
- `↑` / `↓` — move through agents
- `k` — kill selected agent
- `c` — clear completed / failed / stopped agents
- `v` — toggle workflow view vs raw log view
- `h` / `←` — focus left pane
- `l` / `→` — focus right pane
- `q` / `Ctrl+C` — quit

Inside the task prompt:

- `Enter` — insert newline
- `Ctrl+S` — submit
- `Esc` — cancel

If you later rebuild this in Python/Textual, you could keep the same bindings and optionally add a `Shift+C` alias for clearing completed items, but the current shipped implementation uses lowercase `c`.

### Why the interface feels structured

The TUI works because it deliberately separates three ideas:

- **task selection** on the left
- **task metadata** on the top-right
- **task output** on the bottom-right

That separation keeps the right side readable instead of mixing title, state, and logs into one scrolling wall.

The code also explicitly wraps text and strips ANSI noise before rendering summaries, which is why the interface aims to avoid text bleeding and messy overflow.

## The concept of the orchestration pipeline

Internally, each task moves through a fixed mental model:

1. **Coordinator**
   - accepts the original user task
   - gathers repo context
   - enhances the prompt

2. **Lead**
   - reads the enhanced task
   - plans subtasks
   - assigns subtasks to separate worktrees and preferably separate repo areas
   - assigns subtasks to separate worktrees and preferably separate repo areas

3. **Builder**
   - runs in an isolated worktree
   - makes code/doc/test changes

4. **Reviewer**
   - runs after the builder in the same isolated worktree
   - checks the builder output

5. **Sync / push**
   - each task still works from its own isolated worktree
   - all worktrees are intended to share the same branch line rather than splitting into branch-per-agent workflows
   - agents should fetch/rebase against the latest shared branch state before pushing
   - conflict avoidance should come primarily from worktree isolation plus task/directory separation

6. **Cleanup**
   - worktrees are removed after success or stop/cleanup

## Why worktrees matter

The core design choice is isolation.

Every task is supposed to be isolated in its own worktree so that:

- tasks do not overwrite each other
- agents can run in parallel safely
- merge conflicts are reduced
- each result can be reviewed independently

In the branch model described by these notes, the important isolation boundary is the worktree, not a separate branch per agent. The intended idea is one shared branch line with multiple worktrees, while the orchestrator tries to keep agents on different files or directories and rebases before pushing when needed.

So the TUI is really visualizing a queue of isolated worktrees, not just a queue of logs.

## What makes this different from a normal CLI

A normal CLI would run a command, print logs, and exit.

`ocha` instead keeps an always-on session model:

- agent state is persisted
- tasks can be reloaded into the UI
- the operator can watch long-running work as it happens
- the operator can manage multiple agent runs from one screen

That is the main concept: **one operator console for many isolated agent worktrees**.

## Related notes in this folder

- `ocha/python-textual-rebuild.md` — concept for rebuilding the same experience in Python with Textual
- `ocha/junie-headless-sessions.md` — concept for how `ocha` launches and manages headless Junie worker sessions
