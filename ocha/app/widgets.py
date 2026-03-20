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
        self._selected = selected
        label = Static(self._format_task(task, selected=selected), classes="worker-row")
        super().__init__(label)
        if selected:
            self.add_class("--selected")

    @staticmethod
    def _format_task(task: OchaTask, selected: bool = False) -> str:
        icon = STATUS_ICON[task.status]
        color = STATUS_LABEL_COLOR[task.status]
        elapsed = task.elapsed
        title = task.title if len(task.title) <= 40 else task.title[:37] + "..."
        pointer = "[#b8bb26]▶[/] " if selected else "  "
        return (
            f"{pointer}{icon} [{color}]{task.task_id}[/]  {title}\n"
            f"    [#928374]{task.branch}[/] · [{color}]{task.status.value}[/] · [#928374]{elapsed}[/]"
        )


class AgentsPane(Widget):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._last_task_ids: list[str] = []
        self._last_status_snap: list[tuple[str, str]] = []
        self._last_selected_index: int | None = None

    def compose(self):
        yield Static("[b][#b8bb26]Tasks[/][/b]", classes="pane-title")
        yield ListView(id="workers-list")

    def _structure_snapshot(self, state: AppState) -> list[str]:
        """Return task IDs only — used to detect when full rebuild is needed."""
        return [t.task_id for t in state.tasks]

    def _status_snapshot(self, state: AppState) -> list[tuple[str, str]]:
        """Return (status, elapsed) per task — used for in-place text updates."""
        return [(t.status.value, t.elapsed) for t in state.tasks]

    def load(self, state: AppState) -> None:
        list_view = self.query_one(ListView)
        task_ids = self._structure_snapshot(state)
        status_snap = self._status_snapshot(state)
        selected_index = state.selected_index if state.tasks else None

        needs_rebuild = task_ids != self._last_task_ids
        selection_changed = selected_index != self._last_selected_index

        if needs_rebuild:
            # Structure changed — full rebuild required
            self._last_task_ids = task_ids
            self._last_status_snap = status_snap
            self._last_selected_index = selected_index
            list_view.clear()
            for i, task in enumerate(state.tasks):
                list_view.append(WorkerListItem(task, selected=(i == selected_index)))
            list_view.index = selected_index
            return

        # Structure same — check if labels or selection changed
        status_changed = status_snap != self._last_status_snap

        if status_changed or selection_changed:
            self._last_status_snap = status_snap
            self._last_selected_index = selected_index
            children = list(list_view.children)
            for i, task in enumerate(state.tasks):
                if i < len(children):
                    item = children[i]
                    is_selected = i == selected_index
                    label_widget = item.query_one(Static)
                    label_widget.update(
                        WorkerListItem._format_task(task, selected=is_selected)
                    )
                    # Toggle the --selected CSS class
                    if is_selected:
                        item.add_class("--selected")
                    else:
                        item.remove_class("--selected")

        if list_view.index != selected_index:
            list_view.index = selected_index


class TaskHeader(Static):
    _last_content: str = ""

    def update_task(self, task: OchaTask | None) -> None:
        if task is None:
            new_text = (
                "[b][#b8bb26]Task Detail[/][/b]\n\n"
                "[#928374]No active tasks. Press [/][#fabd2f]n[/][#928374] to create a new task.[/]"
            )
            if new_text != self._last_content:
                self._last_content = new_text
                self.update(new_text)
            return
        worker = task.primary_worker
        color = STATUS_LABEL_COLOR[task.status]
        icon = STATUS_ICON[task.status]
        pipeline_parts = []
        for w in sorted(task.workers, key=lambda w: w.role.value):
            wc = STATUS_LABEL_COLOR[w.status]
            pipeline_parts.append(f"[{wc}]{w.role}[/] [{wc}]{w.status.value}[/]")
        pipeline = "  [#504945]│[/]  ".join(pipeline_parts)

        new_text = (
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
        if new_text != self._last_content:
            self._last_content = new_text
            self.update(new_text)


class OutputPane(VerticalScroll):
    mode: reactive[OutputMode] = reactive(OutputMode.WORKFLOW)
    _last_content: str = ""

    def compose(self):
        yield Static(id="output-content")

    def _is_at_bottom(self) -> bool:
        """Check if the scroll position is at (or near) the bottom."""
        if self.max_scroll_y == 0:
            return True
        tolerance = max(3, self.size.height // 4)
        return self.scroll_y >= self.max_scroll_y - tolerance

    _last_fingerprint: tuple = ()

    def update_task(self, task: OchaTask | None, mode: OutputMode) -> None:
        self.mode = mode
        title_label = "Workflow" if mode == OutputMode.WORKFLOW else "Raw Logs"
        content = self.query_one("#output-content", Static)
        if task is None:
            new_text = (
                f"[b][#b8bb26]{title_label}[/][/b]\n\n"
                f"[#928374]No task selected.[/]"
            )
            if new_text != self._last_content:
                self._last_content = new_text
                content.update(new_text)
            return

        # Fast fingerprint check — avoid rebuilding markup when nothing changed
        lines = task.output_lines(mode)
        line_count = len(lines)
        fingerprint = (task.task_id, mode, line_count, task.status.value)
        if fingerprint == self._last_fingerprint:
            return
        self._last_fingerprint = fingerprint

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
        new_text = f"[b][#b8bb26]{title_label}[/][/b]\n\n{body}"

        if new_text == self._last_content:
            return  # nothing changed — skip update to avoid scroll glitch

        was_at_bottom = self._is_at_bottom()
        self._last_content = new_text
        content.update(new_text)

        # Only auto-scroll if user was already at the bottom;
        # defer until after Textual commits the new layout height
        if was_at_bottom:
            self.call_after_refresh(self.scroll_end, animate=False)


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
            "[#504945]│[/] [#fabd2f]↑/↓[/] [#ebdbb2]move[/] "
            "[#504945]│[/] [#fabd2f]v[/] [#ebdbb2]view[/] "
            "[#504945]│[/] [#fabd2f]←/→[/] [#ebdbb2]focus[/] "
            "[#504945]│[/] [#fabd2f]tab[/] [#ebdbb2]cycle[/] "
            "[#504945]│[/] [#fabd2f]c[/] [#ebdbb2]clear[/] "
            "[#504945]│[/] [#fabd2f]x[/] [#ebdbb2]kill[/] "
            "[#504945]│[/] [#fabd2f]q[/] [#ebdbb2]quit[/] "
            "[#504945]│[/]",
            id="help-bar",
        )
        yield StatusBar(id="status-bar")
