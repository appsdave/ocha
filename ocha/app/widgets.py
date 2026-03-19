from __future__ import annotations

from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import ListItem, ListView, Static

from .state import AppState, OchaTask, OutputMode, WorkerStatus


# ── Gruvbox Dark Green palette ────────────────────────────────────────
STATUS_ICON = {
    WorkerStatus.RUNNING: "[#b8bb26]●[/]",
    WorkerStatus.COMPLETED: "[#83a598]✓[/]",
    WorkerStatus.FAILED: "[#fb4934]✕[/]",
    WorkerStatus.STOPPED: "[#928374]■[/]",
    WorkerStatus.QUEUED: "[#fabd2f]…[/]",
}

STATUS_LABEL_COLOR = {
    WorkerStatus.RUNNING: "#b8bb26",
    WorkerStatus.COMPLETED: "#83a598",
    WorkerStatus.FAILED: "#fb4934",
    WorkerStatus.STOPPED: "#928374",
    WorkerStatus.QUEUED: "#fabd2f",
}


class WorkerListItem(ListItem):
    def __init__(self, task: OchaTask, selected: bool = False) -> None:
        self.ocha_task = task
        label = Static(self._format_task(task), classes="worker-row")
        super().__init__(label)

    @staticmethod
    def _format_task(task: OchaTask) -> str:
        icon = STATUS_ICON[task.status]
        color = STATUS_LABEL_COLOR[task.status]
        elapsed = task.elapsed
        title = task.title if len(task.title) <= 40 else task.title[:37] + "..."
        return (
            f"{icon} [{color}]{task.task_id}[/]  {title}\n"
            f"  [#928374]{task.branch}[/] · [{color}]{task.status.value}[/] · [#928374]{elapsed}[/]"
        )


class AgentsPane(Widget):
    _last_snapshot: list[tuple[str, str, str]] = []

    def compose(self):
        yield Static("[b][#b8bb26]Tasks[/][/b]", classes="pane-title")
        yield ListView(id="workers-list")

    def _snapshot(self, state: AppState) -> list[tuple[str, str, str]]:
        """Return a lightweight fingerprint of the task list for change detection."""
        return [
            (t.task_id, t.status.value, t.elapsed)
            for t in state.tasks
        ]

    def load(self, state: AppState) -> None:
        snap = self._snapshot(state)
        list_view = self.query_one(ListView)
        if snap == self._last_snapshot and list_view.index == state.selected_index:
            return  # nothing changed — skip rebuild to avoid flicker
        self._last_snapshot = snap
        list_view.clear()
        for i, task in enumerate(state.tasks):
            list_view.append(WorkerListItem(task, selected=(i == state.selected_index)))
        list_view.index = state.selected_index if state.tasks else None


class TaskHeader(Static):
    def update_task(self, task: OchaTask | None) -> None:
        if task is None:
            self.update(
                "[b][#b8bb26]Task Detail[/][/b]\n\n"
                "[#928374]No active tasks. Press [/][#fabd2f]n[/][#928374] to create a new task.[/]"
            )
            return
        worker = task.primary_worker
        color = STATUS_LABEL_COLOR[task.status]
        icon = STATUS_ICON[task.status]
        pipeline_parts = []
        for w in sorted(task.workers, key=lambda w: w.role.value):
            wc = STATUS_LABEL_COLOR[w.status]
            pipeline_parts.append(f"[{wc}]{w.role}[/] [{wc}]{w.status.value}[/]")
        pipeline = "  [#504945]│[/]  ".join(pipeline_parts)

        self.update(
            f"[b][#b8bb26]Task Detail[/][/b]\n\n"
            f"  {icon} [b]{task.title}[/b]\n"
            f"  [#928374]id[/] [#ebdbb2]{task.task_id}[/]  "
            f"[#928374]state[/] [{color}]{task.status.value}[/]  "
            f"[#928374]branch[/] [#d3869b]{task.branch}[/]  "
            f"[#928374]elapsed[/] [#ebdbb2]{task.elapsed}[/]\n"
            f"  [#928374]role[/] [#ebdbb2]{worker.role}[/]  "
            f"[#928374]worktree[/] [#928374]{worker.worktree_path}[/]  "
            f"[#928374]retries[/] [#ebdbb2]{worker.retry_count}[/]\n"
            f"  [#928374]pipeline[/]  {pipeline}\n"
            f"  [#928374]summary[/]  [#ebdbb2]{task.summary}[/]"
        )


class OutputPane(VerticalScroll):
    mode: reactive[OutputMode] = reactive(OutputMode.WORKFLOW)

    def compose(self):
        yield Static(id="output-content")

    def update_task(self, task: OchaTask | None, mode: OutputMode) -> None:
        self.mode = mode
        title_label = "Workflow" if mode == OutputMode.WORKFLOW else "Raw Logs"
        content = self.query_one("#output-content", Static)
        if task is None:
            content.update(
                f"[b][#b8bb26]{title_label}[/][/b]\n\n"
                f"[#928374]No task selected.[/]"
            )
            return
        lines = task.output_lines(mode)
        body_parts = []
        for line in lines:
            if line.startswith("[coordinator]"):
                body_parts.append(f"  [#d3869b]{line}[/]")
            elif line.startswith("[lead]"):
                body_parts.append(f"  [#83a598]{line}[/]")
            elif line.startswith("[builder]"):
                body_parts.append(f"  [#b8bb26]{line}[/]")
            elif line.startswith("[reviewer]"):
                body_parts.append(f"  [#fabd2f]{line}[/]")
            else:
                body_parts.append(f"  [#ebdbb2]{line}[/]")
        body = "\n".join(body_parts)
        content.update(f"[b][#b8bb26]{title_label}[/][/b]\n\n{body}")
        # Auto-scroll to bottom so latest output is visible
        self.scroll_end(animate=False)


class HelpBar(Static):
    pass


class StatusBar(Static):
    def update_state(self, state: AppState) -> None:
        counts = state.status_counts
        selected = state.selected_task
        sel_id = selected.task_id if selected else "n/a"
        sel_branch = selected.branch if selected else "n/a"
        self.update(
            f"[#b8bb26]● {counts[WorkerStatus.RUNNING]} running[/]  "
            f"[#fabd2f]… {counts[WorkerStatus.QUEUED]} queued[/]  "
            f"[#83a598]✓ {counts[WorkerStatus.COMPLETED]} done[/]  "
            f"[#fb4934]✕ {counts[WorkerStatus.FAILED]} failed[/]  "
            f"[#504945]│[/]  "
            f"[#ebdbb2]{sel_id}[/] [#928374]on[/] [#d3869b]{sel_branch}[/]  "
            f"[#504945]│[/]  "
            f"[#928374]view:[/] [#ebdbb2]{state.output_mode}[/]"
        )


class MainLayout(Widget):
    def compose(self):
        with Horizontal(id="main-row"):
            yield AgentsPane(id="agents-pane")
            with Vertical(id="detail-pane"):
                yield TaskHeader(id="task-header")
                yield OutputPane(id="output-pane")
        yield HelpBar(
            "[#504945]│[/] [#fabd2f]n[/] [#ebdbb2]new[/] "
            "[#504945]│[/] [#fabd2f]j/k[/] [#ebdbb2]move[/] "
            "[#504945]│[/] [#fabd2f]v[/] [#ebdbb2]view[/] "
            "[#504945]│[/] [#fabd2f]h/l[/] [#ebdbb2]focus[/] "
            "[#504945]│[/] [#fabd2f]tab[/] [#ebdbb2]cycle[/] "
            "[#504945]│[/] [#fabd2f]c[/] [#ebdbb2]clear[/] "
            "[#504945]│[/] [#fabd2f]x[/] [#ebdbb2]kill[/] "
            "[#504945]│[/] [#fabd2f]q[/] [#ebdbb2]quit[/] "
            "[#504945]│[/]",
            id="help-bar",
        )
        yield StatusBar(id="status-bar")
