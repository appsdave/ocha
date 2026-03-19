from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static

from .orchestrator import launch_task
from .state import AppState, OutputMode, clear_finished_tasks, sample_state
from .widgets import AgentsPane, MainLayout, OutputPane, StatusBar, TaskHeader


CSS = """
Screen {
    layout: vertical;
    background: #11131a;
    color: #e6e8ef;
}

#main-row {
    height: 1fr;
}

#agents-pane {
    width: 34;
    border: solid #3d4456;
    padding: 0 1;
}

#detail-pane {
    width: 1fr;
}

#task-header, #output-pane, #help-bar, #status-bar {
    border: solid #3d4456;
    padding: 0 1;
}

#task-header {
    height: 8;
}

#output-pane {
    height: 1fr;
}

#help-bar, #status-bar {
    height: 3;
}

.pane-title {
    text-style: bold;
    padding-top: 1;
}

.worker-row {
    padding: 0 0 1 0;
}

NewTaskModal {
    align: center middle;
}

NewTaskModal > Container {
    width: 70;
    height: auto;
    border: solid #6b7280;
    background: #1a1d27;
    padding: 1 2;
}

#new-task-actions {
    width: 1fr;
    height: auto;
    layout: horizontal;
}

.new-task-button {
    margin-right: 1;
}
"""


class NewTaskModal(ModalScreen[str | None]):
    BINDINGS = [("escape", "cancel", "Cancel")]

    def compose(self) -> ComposeResult:
        with Container():
            yield Static("[b]Create new ocha task[/b]\nEnter the operator task to turn into coordinated Junie sessions.")
            yield Input(placeholder="Describe the task for ocha to launch", id="new-task-input")
            with Horizontal(id="new-task-actions"):
                yield Button("Launch", id="submit-task", variant="primary", classes="new-task-button")
                yield Button("Cancel", id="cancel-task")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit(event.value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "submit-task":
            self._submit(self.query_one(Input).value)
            return
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _submit(self, value: str) -> None:
        task = value.strip()
        if not task:
            self.notify("Task prompt cannot be empty.", severity="warning")
            return
        self.dismiss(task)


class OchaApp(App[None]):
    TITLE = "ocha"
    SUB_TITLE = "Python/Textual rebuild"
    CSS = CSS
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("up", "move_up", "Up"),
        Binding("down", "move_down", "Down"),
        Binding("v", "toggle_view", "Toggle View"),
        Binding("h,left", "focus_agents", "Focus Agents"),
        Binding("l,right", "focus_output", "Focus Output"),
        Binding("n", "new_task", "New Task"),
        Binding("c", "clear_finished", "Clear Finished"),
        Binding("k", "kill_selected", "Kill Selected"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.state: AppState = sample_state()

    def compose(self) -> ComposeResult:
        yield MainLayout()

    def on_mount(self) -> None:
        self.refresh_from_state()
        self.action_focus_agents()

    def refresh_from_state(self) -> None:
        self.query_one(AgentsPane).load(self.state)
        selected = self.state.selected_task
        self.query_one(TaskHeader).update_task(selected)
        self.query_one(OutputPane).update_task(selected, self.state.output_mode)
        self.query_one(StatusBar).update_state(self.state)

    def action_move_up(self) -> None:
        if self.state.selected_index > 0:
            self.state.selected_index -= 1
            self.refresh_from_state()

    def action_move_down(self) -> None:
        if self.state.selected_index < len(self.state.tasks) - 1:
            self.state.selected_index += 1
            self.refresh_from_state()

    def action_toggle_view(self) -> None:
        self.state.output_mode = (
            OutputMode.RAW if self.state.output_mode == OutputMode.WORKFLOW else OutputMode.WORKFLOW
        )
        self.refresh_from_state()

    def action_focus_agents(self) -> None:
        self.query_one("#workers-list").focus()

    def action_focus_output(self) -> None:
        self.query_one(OutputPane).focus()

    def action_new_task(self) -> None:
        self.push_screen(NewTaskModal(), self._launch_task_from_prompt)

    def action_clear_finished(self) -> None:
        original_count = len(self.state.tasks)
        self.state = clear_finished_tasks(self.state)
        cleared_count = original_count - len(self.state.tasks)
        if not cleared_count:
            self.notify("No finished tasks to clear.")
            return
        self.refresh_from_state()
        self.notify(f"Cleared {cleared_count} finished task{'s' if cleared_count != 1 else ''}.")

    def action_kill_selected(self) -> None:
        self.notify("Kill selected is a placeholder in the scaffold.")

    def _launch_task_from_prompt(self, task: str | None) -> None:
        if task is None:
            self.notify("New task cancelled.")
            return
        self.state = launch_task(self.state, task)
        self.refresh_from_state()
        self.notify("Prepared coordinator, lead, builder, and reviewer Junie sessions for the new task.")
