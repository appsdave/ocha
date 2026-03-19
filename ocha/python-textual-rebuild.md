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

> enter one task, watch it decompose into isolated worker branches, inspect progress in a structured right pane, and manage each task from a single TUI.

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
- generate unique branch names
- launch coordinator / lead / builder / reviewer subprocesses
- stream logs/events
- push branches and open fresh PRs
- persist status to disk

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
- `pr_created`
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
- per-task PR URL
- timestamps

In Python, a simple version could use:

- `dataclasses`
- a central in-memory store
- JSON persistence for reload/resume-like behavior

## Key UX rules to preserve

If you want the Python version to feel like the current app, keep these rules:

1. **One task can produce many agent branches**
2. **Each task/agent gets a unique branch**
3. **Each task/agent opens a fresh PR**
4. **Each task is isolated in its own worktree/branch**
5. **Left pane is for selection; right pane is for understanding**
6. **The output pane should stay readable and not let text bleed everywhere**
7. **Workflow view should be more important than raw logs**

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
4. Port worktree and branch management.
5. Port coordinator/lead/builder/reviewer process launching.
6. Add PR creation and conflict-resolution flows.
7. Only then polish styling and animations.

## Bottom line

The important idea is not just “rewrite the UI in Python.”

The real product concept is:

- a multi-agent orchestration backend
- a clean reactive operator console
- isolated worktree-per-task execution
- one unique branch and one fresh PR per task/agent result

Textual is a good fit because it can express that model naturally with async updates, clean pane layout, strong keyboard UX, and better long-term maintainability for a Python implementation.