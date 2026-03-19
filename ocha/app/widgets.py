from __future__ import annotations

from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import ListItem, ListView, Static

from .state import AppState, OchaTask, OutputMode, WorkerSession, WorkerStatus


STATUS_ICON = {
    WorkerStatus.RUNNING: "●",
    WorkerStatus.COMPLETED: "✓",
    WorkerStatus.FAILED: "✕",
    WorkerStatus.STOPPED: "■",
    WorkerStatus.QUEUED: "…",
}


class WorkerListItem(ListItem):
    def __init__(self, task: OchaTask) -> None:
        self.task = task
        label = Static(self.render_label(), classes=f"worker-row status-{task.status}")
        super().__init__(label)

    def render_label(self) -> str:
        icon = STATUS_ICON[self.task.status]
        return f"{icon} {self.task.task_id:<6} {self.task.title}\\n  {self.task.branch} • {self.task.pipeline_summary}"


class AgentsPane(Widget):
    def compose(self):
        yield Static("Tasks", classes="pane-title")
        yield ListView(id="workers-list")

    def load(self, state: AppState) -> None:
        list_view = self.query_one(ListView)
        list_view.clear()
        for task in state.tasks:
            list_view.append(WorkerListItem(task))
        list_view.index = state.selected_index


class TaskHeader(Static):
    def update_task(self, task: OchaTask) -> None:
        worker = task.primary_worker
        self.update(
            "\n".join(
                [
                    f"[b]{task.title}[/b]",
                    f"task={task.task_id}   state={task.status}   branch={task.branch}",
                    f"pipeline={task.pipeline_summary}",
                    f"worktree={worker.worktree_path}",
                    f"active_role={worker.role}   owner={worker.owned_directory}   retries={worker.retry_count}   elapsed={task.elapsed}",
                    f"prompt={worker.role_prompt_path}   event={worker.latest_event or 'n/a'}",
                    f"summary={task.summary}",
                ]
            )
        )


class OutputPane(Static):
    mode: reactive[OutputMode] = reactive(OutputMode.WORKFLOW)

    def update_task(self, task: OchaTask, mode: OutputMode) -> None:
        self.mode = mode
        lines = task.output_lines(mode)
        title = "Workflow view" if mode == OutputMode.WORKFLOW else "Raw logs"
        body = "\n".join(f"• {line}" for line in lines)
        self.update(f"[b]{title}[/b]\n\n{body}")


class HelpBar(Static):
    pass


class StatusBar(Static):
    def update_state(self, state: AppState) -> None:
        counts = state.status_counts
        selected = state.selected_task
        self.update(
            "   ".join(
                [
                    f"running {counts[WorkerStatus.RUNNING]}",
                    f"queued {counts[WorkerStatus.QUEUED]}",
                    f"done {counts[WorkerStatus.COMPLETED]}",
                    f"selected {selected.task_id}",
                    f"branch {selected.branch}",
                    f"mode {state.output_mode}",
                ]
            )
        )


class MainLayout(Widget):
    def compose(self):
        with Horizontal(id="main-row"):
            yield AgentsPane(id="agents-pane")
            with Vertical(id="detail-pane"):
                yield TaskHeader(id="task-header")
                yield OutputPane(id="output-pane")
        yield HelpBar("n new task   ↑/↓ move   v toggle view   h/l focus   c clear done   k kill   q quit", id="help-bar")
        yield StatusBar(id="status-bar")
