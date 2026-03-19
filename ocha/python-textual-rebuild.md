# Rebuilding ocha in Python with Textual — Concept Only

This document is not a full implementation plan. It is a conceptual map for rebuilding the current `ocha` TUI experience in Python using `Textual`.

## Why Textual makes sense here

`Textual` is a strong fit because `ocha` already behaves like a reactive terminal app, not a one-shot CLI.

It needs:

- multiple panes
- keyboard-driven focus changes
- live-updating task state
- scrollable log areas
- clean styling
- async process monitoring

Those are all things Textual is very good at.

## One-sentence rebuild goal

Build a Python app that preserves the same operator experience:

> enter one task, watch it decompose into isolated worker worktrees, inspect progress in a structured right pane, and manage each task from a single TUI.

## Conceptual architecture in Python

You would split the system into two layers.

### 1. Orchestration layer

This is the backend logic.

Suggested Python modules:

- `app/orchestrator.py`
- `app/agents.py`
- `app/worktrees.py`
- `app/git_ops.py`
- `app/github_ops.py`
- `app/state.py`
- `app/beads.py`

Responsibilities:

- validate repo state
- create isolated worktrees
- assign one dedicated worktree directory per active agent
- keep each agent's worktree aligned with the shared branch state
- launch coordinator / lead / builder / reviewer subprocesses
- stream logs/events
- synchronize/push updates safely from isolated worktrees
- persist status to disk

## Branch-handling concept for multi-agent execution

If you want the Python rebuild to behave safely under many concurrent agents, use a **directory-isolated agent architecture** built around separate worktrees on the same branch line.

The key idea is this:

- agents do **not** push directly to `main`
- agents use separate worktrees even when they are conceptually working on the same shared branch
- conflict reduction comes from task partitioning plus rebasing onto the latest shared branch state before push

That keeps the concurrency model explicit without forcing a separate branch for every agent.

### 1. Worktree-per-agent

Keep one dedicated worktree directory per running agent.

Example layout:

- `/ocha/agent-1/`
- `/ocha/agent-2/`
- `/ocha/agent-3/`

Why this matters:

- avoids local file-lock/contention issues
- prevents accidental cross-task edits
- makes cleanup deterministic
- makes logs/state easier to associate with one agent

In Python terms, `app/worktrees.py` should treat the worktree path as part of the task identity, not as a temporary afterthought.

### 2. Directory ownership rule

The best way to reduce merge conflicts is still structural, not magical git logic.

Give each agent a private part of the repo whenever possible.

Example:

- Agent Alpha owns `src/agents/alpha/`
- Agent Beta owns `src/agents/beta/`
- shared mutable state should go into a database or structured state file rather than repeated edits to the same source file

That means the orchestrator should prefer subtasks that naturally partition by directory or module boundary.

### 3. Shared branch model

The clarified idea is that agents can share one branch line while still running in separate worktrees.

That means:

- the worktree path is the main execution boundary
- the branch itself does not need to be unique per agent
- task ownership should be expressed by agent/task metadata and directory assignment, not by generating lots of agent-specific branches
- the orchestrator should assume conflicts are still possible if two agents edit the same files

### 4. Required pre-push rebase loop

Before any agent pushes, it should prove that its worktree is based on the latest shared branch state.

Conceptual loop:

1. `git fetch origin agent`
2. `git merge-base --is-ancestor origin/agent HEAD`
3. if the answer is stale, run `git rebase origin/agent`
4. resolve local conflicts inside the agent worktree
5. `git push origin agent`

This should be a built-in orchestration rule, not an optional operator habit.

The point is simple: every agent rebases against `agent` before push, so stale starting points are corrected early rather than discovered after multiple worktrees drift apart.

### 5. Safe synchronization on `agent`

If you truly want one branch, then the safety rule is not "make more branches" but "make concurrent edits less likely and rebase before publish."

In practice:

1. each agent works in its own worktree
2. the orchestrator prefers tasks in different directories/modules
3. before push, the agent fetches and rebases onto the latest `agent`
4. if a conflict appears, that agent resolves it locally before pushing
5. operators should treat same-file parallel edits as an exceptional case, not the normal path

This model is simpler, but it depends more heavily on task partitioning discipline.

### 6. TUI implications

If you expose this concept in Textual, each task row should ideally track:

- worktree path
- current branch (`agent`)
- rebase status
- owned directory/module

That makes branch handling visible instead of hidden in logs.

### 7. Recommended orchestration rule set

For the Python rebuild, the branch/worktree rules should be:

1. create a dedicated worktree per agent
2. keep all active worktrees aligned to the shared branch `agent`
3. keep agents assigned to separate directories/modules when possible
4. require `fetch` + rebase validation before push
5. push back to `agent` only after local conflicts are resolved
6. treat same-file parallel edits as a scheduling problem to avoid upstream, not as the default git workflow
### 2. Textual presentation layer

This is the UI.

Suggested Textual widgets/screens:

- `OchaApp(App)`
- `AgentsPane(Widget)`
- `TaskHeader(Widget)`
- `OutputPane(Log or RichLog)`
- `StatusBar(Widget)`
- `NewTaskModal(ModalScreen)`

Responsibilities:

- render live state
- manage focus
- bind keys
- switch selected task
- toggle workflow view vs raw logs
- display clean summaries without overflow

## Best Textual mapping from the current UI

### Left pane: Agents list

Use one of these approaches:

- a `ListView` with custom list items
- a custom `Widget` that renders grouped agents

Each row should show:

- status icon
- short task name
- branch name
- optional repo name
- done/running grouping if desired

### Top-right pane: Task header

Use a compact `Static` or custom widget.

It should show:

- selected task title
- current state
- branch name
- pipeline stage summary
- maybe repo name and elapsed time

### Bottom-right pane: Output pane

Use `RichLog` or a custom scrollable widget.

The pane should support two modes:

- **workflow mode** — milestone summary only
- **raw mode** — full captured logs

This matches the current `v` toggle idea.

### Bottom status/hint bars

Use docked footer widgets.

One bar can show keybindings and the other can show:

- total tasks
- running count
- done count
- selected branch

## Process model in Python

The current Node app spawns subprocesses and streams their output. A Python rebuild should preserve that pattern.

Recommended approach:

- use `asyncio.create_subprocess_exec`
- keep one async task per running agent
- parse stdout/stderr into structured events
- push those events into a shared state store
- refresh the Textual widgets from that store

That gives you a clean event loop model:

1. user submits task
2. orchestrator creates plan
3. builder/reviewer subprocesses emit events
4. state store updates
5. Textual reacts and re-renders

## Event model to preserve the current concept

Instead of treating output as only text, treat it as events.

Examples:

- `task_created`
- `task_selected`
- `prompt_enhanced`
- `lead_started`
- `lead_completed`
- `builder_started`
- `builder_retrying`
- `reviewer_started`
- `task_completed`
- `task_failed`
- `push_completed`
- `worktree_removed`

The UI can still show raw logs, but the primary operator experience should be built from structured events.

That is how you keep the right pane clean and avoid text chaos.

## State model

At minimum, store:

- session info
- tasks list
- selected task id
- per-task status
- per-task branch
- per-task worktree path
- per-task phase
- per-task logs
- per-task sync/push result
- timestamps

In Python, a simple version could use:

- `dataclasses`
- a central in-memory store
- JSON persistence for reload/resume-like behavior

## Key UX rules to preserve

If you want the Python version to feel like the current app, keep these rules:

1. **One task can produce many agent worktrees**
2. **Each task/agent gets a dedicated worktree**
3. **Agents can share one branch line if their work is partitioned cleanly**
4. **Each task is isolated in its own worktree**
5. **Left pane is for selection; right pane is for understanding**
6. **The output pane should stay readable and not let text bleed everywhere**
7. **Workflow view should be more important than raw logs**
8. **Rebase and task partitioning are the main protection against conflicts on `agent`**

## Suggested Textual keybindings

To mirror the current app closely:

- `n` — new task modal
- `up/down` — move selection
- `h` / `left` — focus left pane
- `l` / `right` — focus right pane
- `v` — toggle workflow/raw mode
- `k` — stop selected task
- `c` — clear completed tasks
- optional `Shift+C` — alternate clear-completed shortcut if you want a more explicit binding
- `q` — quit

## Example app skeleton

```python
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Static, Footer, Header, ListView, RichLog


class OchaApp(App):
    BINDINGS = [
        ("n", "new_task", "New"),
        ("v", "toggle_view", "Toggle View"),
        ("c", "clear_done", "Clear Done"),
        ("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield ListView(id="agents")
            with Vertical():
                yield Static(id="task_header")
                yield RichLog(id="output")
        yield Footer()
```

That is enough for the shell, but the real value would be in the async orchestration/event layer behind it.

## Suggested migration path

If this were rebuilt gradually instead of all at once:

1. Keep the existing orchestration logic as the reference behavior.
2. Define the event/state model first.
3. Recreate the TUI shell in Textual.
4. Port worktree management and shared-branch synchronization.
5. Port coordinator/lead/builder/reviewer process launching.
6. Add rebase validation and safe push flows targeting `agent`.
7. Only then polish styling and animations.

## Bottom line

The important idea is not just “rewrite the UI in Python.”

The real product concept is:

- a multi-agent orchestration backend
- a clean reactive operator console
- isolated worktree-per-task execution
- one shared branch line coordinated across multiple isolated worktrees, with rebasing and task partitioning used to avoid conflicts

Textual is a good fit because it can express that model naturally with async updates, clean pane layout, strong keyboard UX, and better long-term maintainability for a Python implementation.