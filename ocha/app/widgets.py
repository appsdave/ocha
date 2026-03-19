from __future__ import annotations

from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import ListItem, ListView, Static

from .state import AppState, OchaTask, OutputMode, WorkerStatus


STATUS_ICON = {
    WorkerStatus.RUNNING: "[#41d995]●[/]",
    WorkerStatus.COMPLETED: "[#7aa2f7]✓[/]",
    WorkerStatus.FAILED: "[#f7768e]✕[/]",
    WorkerStatus.STOPPED: "[#787c99]■[/]",
    WorkerStatus.QUEUED: "[#e0af68]…[/]",
}

STATUS_LABEL_COLOR = {
    WorkerStatus.RUNNING: "#41d995",
    WorkerStatus.COMPLETED: "#7aa2f7",
    WorkerStatus.FAILED: "#f7768e",
    WorkerStatus.STOPPED: "#787c99",
    WorkerStatus.QUEUED: "#e0af68",
}


class WorkerListItem(ListItem):
    def __init__(self, task: OchaTask, selected: bool = False) -> None:
        self.ocha_task = task
        label = Static(self._render(task), classes="worker-row")
        super().__init__(label)

    @staticmethod
    def _render(task: OchaTask) -> str:
        icon = STATUS_ICON[task.status]
        color = STATUS_LABEL_COLOR[task.status]
        elapsed = task.elapsed
        title = task.title if len(task.title) <= 40 else task.title[:37] + "..."
        return (
            f"{icon} [{color}]{task.task_id}[/]  {title}\n"
            f"  [#565f89]{task.branch}[/] · [{color}]{task.status.value}[/] · [#565f89]{elapsed}[/]"
        )


class AgentsPane(Widget):
    def compose(self):
        yield Static("[b][#7aa2f7]Tasks[/][/b]", classes="pane-title")
        yield ListView(id="workers-list")

    def load(self, state: AppState) -> None:
        list_view = self.query_one(ListView)
        list_view.clear()
        for i, task in enumerate(state.tasks):
            list_view.append(WorkerListItem(task, selected=(i == state.selected_index)))
        list_view.index = state.selected_index if state.tasks else None


class TaskHeader(Static):
    def update_task(self, task: OchaTask | None) -> None:
        if task is None:
            self.update(
                "[b][#7aa2f7]Task Detail[/][/b]\n\n"
                "[#565f89]No active tasks. Press [/][#e0af68]n[/][#565f89] to create a new task.[/]"
            )
            return
        worker = task.primary_worker
        color = STATUS_LABEL_COLOR[task.status]
        icon = STATUS_ICON[task.status]
        pipeline_parts = []
        for w in sorted(task.workers, key=lambda w: w.role.value):
            wc = STATUS_LABEL_COLOR[w.status]
            pipeline_parts.append(f"[{wc}]{w.role}[/] [{wc}]{w.status.value}[/]")
        pipeline = "  [#3d4456]│[/]  ".join(pipeline_parts)

        self.update(
            f"[b][#7aa2f7]Task Detail[/][/b]\n\n"
            f"  {icon} [b]{task.title}[/b]\n"
            f"  [#565f89]id[/] [#c0caf5]{task.task_id}[/]  "
            f"[#565f89]state[/] [{color}]{task.status.value}[/]  "
            f"[#565f89]branch[/] [#bb9af7]{task.branch}[/]  "
            f"[#565f89]elapsed[/] [#c0caf5]{task.elapsed}[/]\n"
            f"  [#565f89]role[/] [#c0caf5]{worker.role}[/]  "
            f"[#565f89]worktree[/] [#565f89]{worker.worktree_path}[/]  "
            f"[#565f89]retries[/] [#c0caf5]{worker.retry_count}[/]\n"
            f"  [#565f89]pipeline[/]  {pipeline}\n"
            f"  [#565f89]summary[/]  [#c0caf5]{task.summary}[/]"
        )


class OutputPane(Static):
    mode: reactive[OutputMode] = reactive(OutputMode.WORKFLOW)

    def update_task(self, task: OchaTask | None, mode: OutputMode) -> None:
        self.mode = mode
        title_label = "Workflow" if mode == OutputMode.WORKFLOW else "Raw Logs"
        if task is None:
            self.update(
                f"[b][#7aa2f7]{title_label}[/][/b]\n\n"
                f"[#565f89]No task selected.[/]"
            )
            return
        lines = task.output_lines(mode)
        body_parts = []
        for line in lines:
            if line.startswith("[coordinator]"):
                body_parts.append(f"  [#bb9af7]{line}[/]")
            elif line.startswith("[lead]"):
                body_parts.append(f"  [#7aa2f7]{line}[/]")
            elif line.startswith("[builder]"):
                body_parts.append(f"  [#41d995]{line}[/]")
            elif line.startswith("[reviewer]"):
                body_parts.append(f"  [#e0af68]{line}[/]")
            else:
                body_parts.append(f"  [#a9b1d6]{line}[/]")
        body = "\n".join(body_parts)
        self.update(f"[b][#7aa2f7]{title_label}[/][/b]\n\n{body}")


class HelpBar(Static):
    pass


class StatusBar(Static):
    def update_state(self, state: AppState) -> None:
        counts = state.status_counts
        selected = state.selected_task
        sel_id = selected.task_id if selected else "n/a"
        sel_branch = selected.branch if selected else "n/a"
        self.update(
            f"[#41d995]● {counts[WorkerStatus.RUNNING]} running[/]  "
            f"[#e0af68]… {counts[WorkerStatus.QUEUED]} queued[/]  "
            f"[#7aa2f7]✓ {counts[WorkerStatus.COMPLETED]} done[/]  "
            f"[#f7768e]✕ {counts[WorkerStatus.FAILED]} failed[/]  "
            f"[#3d4456]│[/]  "
            f"[#c0caf5]{sel_id}[/] [#565f89]on[/] [#bb9af7]{sel_branch}[/]  "
            f"[#3d4456]│[/]  "
            f"[#565f89]view:[/] [#c0caf5]{state.output_mode}[/]"
        )


class MainLayout(Widget):
    def compose(self):
        with Horizontal(id="main-row"):
            yield AgentsPane(id="agents-pane")
            with Vertical(id="detail-pane"):
                yield TaskHeader(id="task-header")
                yield OutputPane(id="output-pane")
        yield HelpBar(
            "[#3d4456]│[/] [#e0af68]n[/] [#a9b1d6]new[/] "
            "[#3d4456]│[/] [#e0af68]↑↓[/] [#a9b1d6]move[/] "
            "[#3d4456]│[/] [#e0af68]v[/] [#a9b1d6]view[/] "
            "[#3d4456]│[/] [#e0af68]h/l[/] [#a9b1d6]focus[/] "
            "[#3d4456]│[/] [#e0af68]c[/] [#a9b1d6]clear[/] "
            "[#3d4456]│[/] [#e0af68]k[/] [#a9b1d6]kill[/] "
            "[#3d4456]│[/] [#e0af68]q[/] [#a9b1d6]quit[/] "
            "[#3d4456]│[/]",
            id="help-bar",
        )
        yield StatusBar(id="status-bar")
