from __future__ import annotations

from dataclasses import dataclass

from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import ListItem, ListView, Static

from .notifications import NotificationEvent, NotificationLevel
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


STATUS_CSS_CLASS = {
    WorkerStatus.RUNNING: "--status-running",
    WorkerStatus.COMPLETED: "--status-completed",
    WorkerStatus.FAILED: "--status-failed",
    WorkerStatus.STOPPED: "--status-stopped",
    WorkerStatus.QUEUED: "--status-queued",
}

TASK_TITLE_MAX_WIDTH = 38
TASK_POSITION_BULLET = "[#665c54]•[/]"
TASK_HEADER_ARROW = "[#504945]→[/]"


def _truncate_task_title(title: str, limit: int = TASK_TITLE_MAX_WIDTH) -> str:
    return title if len(title) <= limit else title[: limit - 3] + "..."


def _task_position(index: int, total: int) -> str:
    return f"{index + 1}/{total}" if total > 0 else ""


@dataclass(frozen=True, slots=True)
class TaskRowHighlight:
    pointer: str
    id_label: str
    position_label: str
    title_label: str
    meta_label: str

    @classmethod
    def build(cls, task: OchaTask, *, selected: bool, position: str) -> TaskRowHighlight:
        color = STATUS_LABEL_COLOR[task.status]
        if selected:
            return cls(
                pointer=f"[{color}]▶[/] ",
                id_label=f"[b][{color}][on #3c3836] {task.task_id} [/][/b]",
                position_label=f" [#bdae93]•[/] [b][#d5c4a1][on #3c3836] {position} [/][/b]" if position else "",
                title_label=f"[b][#fbf1c7]{_truncate_task_title(task.title)}[/][/b]",
                meta_label=(
                    f"[b][#d3869b]{task.branch}[/][/b] {TASK_POSITION_BULLET} "
                    f"[b][#fbf1c7][on #458588] ACTIVE [/][/b] {TASK_POSITION_BULLET} "
                    f"[#d5c4a1]{task.elapsed}[/]"
                ),
            )
        return cls(
            pointer="  ",
            id_label=f"[#928374]{task.task_id}[/]",
            position_label=f" [#665c54]• {position}[/]" if position else "",
            title_label=f"[#bdae93]{_truncate_task_title(task.title)}[/]",
            meta_label=(
                f"[#928374]{task.branch}[/] {TASK_POSITION_BULLET} "
                f"[#7c6f64]{task.status.value}[/] {TASK_POSITION_BULLET} [#7c6f64]{task.elapsed}[/]"
            ),
        )


def _format_pipeline(task: OchaTask) -> str:
    pipeline_parts = []
    for worker in sorted(task.workers, key=lambda item: item.role.value):
        worker_color = STATUS_LABEL_COLOR[worker.status]
        worker_icon = STATUS_ICON[worker.status]
        pipeline_parts.append(
            f"{worker_icon} [{worker_color}]{worker.role}[/] [{worker_color}]{worker.status.value}[/]"
        )
    return f"  {TASK_HEADER_ARROW}  ".join(pipeline_parts)


def _format_active_task_banner(task: OchaTask, *, position: str) -> str:
    color = STATUS_LABEL_COLOR[task.status]
    icon = STATUS_ICON[task.status]
    position_label = f"  [#928374]([/][#b8bb26]{position}[/][#928374])[/]" if position else ""
    status_chip = f"[b][on #3c3836][{color}] {task.status.value.upper()} [/][/b]"
    return (
        f"  [b][on #504945] {icon} {task.task_id} [/][/b]  "
        f"[b][#fbf1c7]{task.title}[/][/b]{position_label}  {status_chip}"
    )

NOTIFICATION_LEVEL_STYLES = {
    NotificationLevel.INFO: ("→", "#83a598", "info"),
    NotificationLevel.SUCCESS: ("✓", "#b8bb26", "success"),
    NotificationLevel.WARNING: ("⚠", "#fabd2f", "warning"),
    NotificationLevel.ERROR: ("✕", "#fb4934", "error"),
}

NOTIFICATION_LEVEL_STYLES = {
    NotificationLevel.INFO: ("→", "#83a598", "info"),
    NotificationLevel.SUCCESS: ("✓", "#b8bb26", "success"),
    NotificationLevel.WARNING: ("⚠", "#fabd2f", "warning"),
    NotificationLevel.ERROR: ("✕", "#fb4934", "error"),
}


class WorkerListItem(ListItem):
    def __init__(self, task: OchaTask, selected: bool = False, index: int = 0, total: int = 0) -> None:
        self.ocha_task = task
        self._selected = selected
        label = Static(self._format_task(task, selected=selected, index=index, total=total), classes="worker-row")
        super().__init__(label)
        if selected:
            self.add_class("--selected")
        self.add_class(STATUS_CSS_CLASS[task.status])

    @staticmethod
    def _format_task(task: OchaTask, selected: bool = False, index: int = 0, total: int = 0) -> str:
        icon = STATUS_ICON[task.status]
        position = _task_position(index, total)
        highlight = TaskRowHighlight.build(task, selected=selected, position=position)
        return (
            f"{highlight.pointer}{icon} {highlight.id_label}{highlight.position_label}\n"
            f"    {highlight.title_label}\n"
            f"    {highlight.meta_label}"
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
        total = len(state.tasks)
        selected_index = state.selected_index if state.tasks else None

        # Update the pane title with task count
        title_widget = self.query_one(".pane-title", Static)
        if total > 0:
            title_widget.update(f"[b][#b8bb26]Tasks[/][/b] [#928374]({total})[/]")
        else:
            title_widget.update("[b][#b8bb26]Tasks[/][/b]")

        needs_rebuild = task_ids != self._last_task_ids
        selection_changed = selected_index != self._last_selected_index

        if needs_rebuild:
            # Structure changed — full rebuild required
            self._last_task_ids = task_ids
            self._last_status_snap = status_snap
            self._last_selected_index = selected_index
            list_view.clear()
            for i, task in enumerate(state.tasks):
                list_view.append(WorkerListItem(task, selected=(i == selected_index), index=i, total=total))
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
                        WorkerListItem._format_task(task, selected=is_selected, index=i, total=total)
                    )
                    # Toggle the --selected CSS class
                    if is_selected:
                        item.add_class("--selected")
                    else:
                        item.remove_class("--selected")
                    # Sync status CSS class for border color
                    for cls in STATUS_CSS_CLASS.values():
                        item.remove_class(cls)
                    item.add_class(STATUS_CSS_CLASS[task.status])

        if list_view.index != selected_index:
            list_view.index = selected_index


class TaskHeader(Static):
    _last_content: str = ""
    _task_position: str = ""

    def update_task(self, task: OchaTask | None, position: str = "") -> None:
        self._task_position = position
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
        pipeline = _format_pipeline(task)
        banner_line = _format_active_task_banner(task, position=position)

        new_text = (
            f"[b][#b8bb26]▸ Active Task[/][/b]\n\n"
            f"{banner_line}\n"
            f"  [#928374]state[/] [{color}]{task.status.value}[/]  "
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


class NotificationPane(Widget):
    MAX_VISIBLE_NOTIFICATIONS = 6

    def compose(self):
        yield Static("[b][#b8bb26]Notifications[/][/b]", classes="pane-title")
        yield Static(id="notifications-content")

    def load(self, history: tuple[NotificationEvent, ...]) -> None:
        title = self.query_one(".pane-title", Static)
        content = self.query_one("#notifications-content", Static)
        visible_events = history[-self.MAX_VISIBLE_NOTIFICATIONS :]

        if visible_events:
            title.update(
                f"[b][#b8bb26]Notifications[/][/b] [#928374]({len(history)})[/]"
            )
        else:
            title.update("[b][#b8bb26]Notifications[/][/b]")

        if not visible_events:
            content.update(
                "[#928374]No notifications yet. Task launches, warnings, and errors will appear here.[/]"
            )
            return

        lines: list[str] = []
        for event in reversed(visible_events):
            icon, color, label = NOTIFICATION_LEVEL_STYLES[event.level]
            title_markup = f" [#928374]·[/] [#d3869b]{event.title}[/]" if event.title else ""
            lines.append(
                f"[{color}]{icon}[/] [b][{color}]{label.upper()}[/][/b]{title_markup}\n"
                f"  [#ebdbb2]{event.message}[/]"
            )
        content.update("\n\n".join(lines))


class HelpBar(Static):
    pass


class StatusBar(Static):
    def update_state(self, state: AppState) -> None:
        counts = state.status_counts
        total = len(state.tasks)
        selected = state.selected_task
        sel_id = selected.task_id if selected else "n/a"
        sel_branch = selected.branch if selected else "n/a"
        # Show position indicator so the user always knows where they are
        if total > 0:
            position = f"{state.selected_index + 1}/{total}"
        else:
            position = "0/0"
        self.update(
            f"[#b8bb26]● {counts[WorkerStatus.RUNNING]} running[/]  "
            f"[#fabd2f]… {counts[WorkerStatus.QUEUED]} queued[/]  "
            f"[#83a598]✓ {counts[WorkerStatus.COMPLETED]} done[/]  "
            f"[#fb4934]✕ {counts[WorkerStatus.FAILED]} failed[/]  "
            f"[#504945]│[/]  "
            f"[b][#b8bb26]▸[/][/b] [#ebdbb2]{sel_id}[/] "
            f"[#928374]({position})[/] "
            f"[#928374]on[/] [#d3869b]{sel_branch}[/]  "
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
                yield NotificationPane(id="notifications-pane")
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
