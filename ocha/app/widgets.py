from __future__ import annotations

from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import ListItem, ListView, Static

from .state import AppState, OutputMode, WorkerSession, WorkerStatus


STATUS_ICON = {
    WorkerStatus.RUNNING: "●",
    WorkerStatus.COMPLETED: "✓",
    WorkerStatus.FAILED: "✕",
    WorkerStatus.STOPPED: "■",
    WorkerStatus.QUEUED: "…",
}


class WorkerListItem(ListItem):
    def __init__(self, worker: WorkerSession) -> None:
        self.worker = worker
        label = Static(self.render_label(), classes=f"worker-row status-{worker.status}")
        super().__init__(label)

    def render_label(self) -> str:
        icon = STATUS_ICON[self.worker.status]
        return f"{icon} {self.worker.role:<11} {self.worker.title}\\n  {self.worker.branch} • {self.worker.owned_directory}"


class AgentsPane(Widget):
    def compose(self):
        yield Static("Workers", classes="pane-title")
        yield ListView(id="workers-list")

    def load(self, state: AppState) -> None:
        list_view = self.query_one(ListView)
        list_view.clear()
        for worker in state.workers:
            list_view.append(WorkerListItem(worker))
        list_view.index = state.selected_index


class TaskHeader(Static):
    def update_worker(self, worker: WorkerSession) -> None:
        self.update(
            "\n".join(
                [
                    f"[b]{worker.title}[/b]",
                    f"role={worker.role}   state={worker.status}   branch={worker.branch}",
                    f"worktree={worker.worktree_path}",
                    f"owner={worker.owned_directory}   retries={worker.retry_count}   elapsed={worker.elapsed}",
                    f"summary={worker.summary}",
                ]
            )
        )


class OutputPane(Static):
    mode: reactive[OutputMode] = reactive(OutputMode.WORKFLOW)

    def update_worker(self, worker: WorkerSession, mode: OutputMode) -> None:
        self.mode = mode
        lines = worker.workflow_log if mode == OutputMode.WORKFLOW else worker.raw_log
        title = "Workflow view" if mode == OutputMode.WORKFLOW else "Raw logs"
        body = "\n".join(f"• {line}" for line in lines)
        self.update(f"[b]{title}[/b]\n\n{body}")


class HelpBar(Static):
    pass


class StatusBar(Static):
    def update_state(self, state: AppState) -> None:
        counts = state.status_counts
        selected = state.selected_worker
        self.update(
            "   ".join(
                [
                    f"running {counts[WorkerStatus.RUNNING]}",
                    f"queued {counts[WorkerStatus.QUEUED]}",
                    f"done {counts[WorkerStatus.COMPLETED]}",
                    f"selected {selected.session_id}",
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
