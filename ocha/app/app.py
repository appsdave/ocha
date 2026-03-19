from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, ListView, Static

from .orchestrator import launch_task
from .state import AppState, OutputMode, WorkerStatus, clear_finished_tasks, sample_state
from .widgets import AgentsPane, MainLayout, OutputPane, StatusBar, TaskHeader

OCHA_BRANCH = "ocha"


# ── Gruvbox Dark Green theme ──────────────────────────────────────────
CSS = """
Screen {
    layout: vertical;
    background: #282828;
    color: #ebdbb2;
}

#main-row {
    height: 1fr;
}

#agents-pane {
    width: 36;
    border: solid #504945;
    padding: 0 1;
    background: #282828;
}

#detail-pane {
    width: 1fr;
    height: 1fr;
}

#task-header {
    height: auto;
    max-height: 12;
    border: solid #504945;
    padding: 0 1;
    background: #282828;
}

#output-pane {
    height: 1fr;
    min-height: 4;
    border: solid #504945;
    padding: 0 1;
    background: #282828;
    overflow-y: auto;
}

#help-bar {
    height: 1;
    background: #3c3836;
    color: #ebdbb2;
    padding: 0 1;
    border: none;
}

#status-bar {
    height: 1;
    background: #282828;
    color: #ebdbb2;
    padding: 0 1;
    border-top: solid #504945;
}

.pane-title {
    text-style: bold;
    color: #b8bb26;
    padding: 0 0 1 0;
}

.worker-row {
    padding: 0 0 1 0;
}

ListView {
    background: #282828;
}

ListView > ListItem {
    background: #282828;
    color: #ebdbb2;
}

ListView > ListItem.--highlight {
    background: #3c3836;
}

ListView:focus > ListItem.--highlight {
    background: #504945;
}

/* ── Floating new-task overlay ── */
NewTaskOverlay {
    align: center middle;
    background: rgba(0, 0, 0, 0.65);
}

#new-task-box {
    width: 60;
    height: auto;
    border: solid #504945;
    background: #282828;
    padding: 1 2;
}

#new-task-title {
    color: #ebdbb2;
    padding: 0 0 1 0;
}

#new-task-box Input {
    background: #3c3836;
    color: #fbf1c7;
    border: solid #504945;
}

#new-task-box Input:focus {
    border: solid #b8bb26;
}

#new-task-hint {
    color: #928374;
    padding: 1 0 0 0;
    height: 1;
}

/* ── Kill-confirm overlay ── */
KillConfirmOverlay {
    align: center middle;
    background: rgba(0, 0, 0, 0.65);
}

#kill-box {
    width: 50;
    height: auto;
    border: solid #fb4934;
    background: #282828;
    padding: 1 2;
}

#kill-box Static {
    color: #ebdbb2;
}

#kill-box Button {
    background: #3c3836;
    color: #ebdbb2;
    border: solid #504945;
}

#kill-box #kill-yes {
    background: #fb4934;
    color: #282828;
    border: solid #fb4934;
}

#kill-actions {
    width: 1fr;
    height: auto;
    layout: horizontal;
}

.kill-button {
    margin-right: 1;
}
"""


class NewTaskOverlay(ModalScreen[str | None]):
    """Minimal floating overlay for creating a new task."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def compose(self) -> ComposeResult:
        with Container(id="new-task-box"):
            yield Static("[#b8bb26]>[/] [b]new task[/b]", id="new-task-title")
            yield Input(placeholder="what should ocha do?", id="new-task-input")
            yield Static(
                "[#504945]enter[/] [#928374]submit[/]  "
                "[#504945]esc[/] [#928374]cancel[/]",
                id="new-task-hint",
            )

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


class KillConfirmOverlay(ModalScreen[bool]):
    """Floating confirmation before killing a task."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, task_id: str, task_title: str) -> None:
        super().__init__()
        self._task_id = task_id
        self._task_title = task_title

    def compose(self) -> ComposeResult:
        with Container(id="kill-box"):
            yield Static(
                f"[b][#fb4934]Kill task?[/][/b]\n"
                f"[#ebdbb2]{self._task_id}[/] — [#a89984]{self._task_title}[/]"
            )
            with Horizontal(id="kill-actions"):
                yield Button("Kill", id="kill-yes", classes="kill-button")
                yield Button("Cancel", id="kill-no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "kill-yes")

    def action_cancel(self) -> None:
        self.dismiss(False)


class OchaApp(App[None]):
    TITLE = "ocha"
    SUB_TITLE = "Python/Textual rebuild"
    CSS = CSS
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("up,k", "move_up", "Up", show=False),
        Binding("down,j", "move_down", "Down", show=False),
        Binding("v", "toggle_view", "Toggle View"),
        Binding("h,left", "focus_agents", "Focus Agents"),
        Binding("l,right", "focus_output", "Focus Output"),
        Binding("n", "new_task", "New Task"),
        Binding("c", "clear_finished", "Clear Finished"),
        Binding("x", "kill_selected", "Kill Selected"),
        Binding("tab", "cycle_focus", "Cycle Focus", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.state: AppState = sample_state()

    def compose(self) -> ComposeResult:
        yield MainLayout()

    def on_mount(self) -> None:
        self._ensure_ocha_branch()
        self.refresh_from_state()
        self.action_focus_agents()
        self.set_interval(1.0, self._tick)
        self._running_procs: dict[str, asyncio.subprocess.Process] = {}

    def _tick(self) -> None:
        """Periodic refresh so elapsed timers and status updates appear."""
        self.refresh_from_state()

    def _ensure_ocha_branch(self) -> None:
        """Create and checkout the ocha branch if it doesn't already exist."""
        try:
            current = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, text=True, timeout=5,
            )
            if current.returncode == 0 and current.stdout.strip() == OCHA_BRANCH:
                return
            # Check if branch exists
            check = subprocess.run(
                ["git", "rev-parse", "--verify", OCHA_BRANCH],
                capture_output=True, text=True, timeout=5,
            )
            if check.returncode == 0:
                subprocess.run(["git", "checkout", OCHA_BRANCH], capture_output=True, timeout=5)
            else:
                subprocess.run(["git", "checkout", "-b", OCHA_BRANCH], capture_output=True, timeout=5)
        except Exception:
            pass  # non-fatal — works fine without git

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

    def action_cycle_focus(self) -> None:
        if self.query_one("#workers-list").has_focus:
            self.action_focus_output()
        else:
            self.action_focus_agents()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.list_view.id != "workers-list" or event.item is None:
            return
        self._sync_selection_from_sidebar(event.list_view)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id != "workers-list":
            return
        self._sync_selection_from_sidebar(event.list_view)

    def action_new_task(self) -> None:
        self.push_screen(NewTaskOverlay(), self._launch_task_from_prompt)

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
        task = self.state.selected_task
        if task is None:
            self.notify("No task selected to kill.")
            return
        self.push_screen(KillConfirmOverlay(task.task_id, task.title), self._handle_kill)

    def _handle_kill(self, confirmed: bool) -> None:
        if not confirmed:
            self.notify("Kill cancelled.")
            return
        task = self.state.selected_task
        if task is None:
            return
        for worker in task.workers:
            if worker.status in (WorkerStatus.RUNNING, WorkerStatus.QUEUED):
                worker.status = WorkerStatus.STOPPED
                # Kill the actual junie process if running
                proc = self._running_procs.pop(worker.session_id, None)
                if proc and proc.returncode is None:
                    try:
                        proc.terminate()
                    except ProcessLookupError:
                        pass
                from datetime import datetime
                worker.finished_at = datetime.now()
        self.refresh_from_state()
        self.notify(f"Killed task {task.task_id}.")

    def _launch_task_from_prompt(self, task: str | None) -> None:
        if task is None:
            self.notify("New task cancelled.")
            return
        self.state = launch_task(self.state, task)
        self.refresh_from_state()
        task_obj = self.state.selected_task
        if task_obj:
            running = sum(1 for w in task_obj.workers if w.status == WorkerStatus.RUNNING)
            queued = sum(1 for w in task_obj.workers if w.status == WorkerStatus.QUEUED)
            self.notify(
                f"[#b8bb26]●[/] Task {task_obj.task_id} launched — "
                f"{running} running, {queued} queued",
                severity="information",
            )
            # Actually spawn Junie headless for the running worker
            self._spawn_junie_workers(task_obj)
        else:
            self.notify("Task launched.")

    def _spawn_junie_workers(self, task_obj) -> None:
        """Spawn Junie CLI headless for each RUNNING worker in the task."""
        junie_bin = shutil.which("junie")
        if not junie_bin:
            self.notify("[#fb4934]junie CLI not found on PATH[/]", severity="error")
            return
        for worker in task_obj.workers:
            if worker.status == WorkerStatus.RUNNING:
                self.run_worker(self._run_junie_for_worker(worker, task_obj))

    async def _run_junie_for_worker(self, worker, task_obj) -> None:
        """Run Junie headless CLI for a single worker and stream output."""
        try:
            worktree_path = Path(worker.worktree_path)
            worktree_path.mkdir(parents=True, exist_ok=True)

            cmd = [
                "junie",
                "--project", str(worktree_path),
                "--session-id", worker.session_id,
                "--output-format", "text",
                "--task", worker.task_prompt,
            ]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            self._running_procs[worker.session_id] = proc

            worker.workflow_log.append(f"Started junie process (PID {proc.pid}).")
            worker.latest_event = "junie_started"

            async for raw_line in proc.stdout:
                line = raw_line.decode(errors="replace").rstrip()
                worker.raw_log.append(line)
                if line:
                    worker.workflow_log.append(line)
                    worker.latest_event = line[:80]

            rc = await proc.wait()
            self._running_procs.pop(worker.session_id, None)

            from datetime import datetime
            worker.finished_at = datetime.now()
            if rc == 0:
                worker.status = WorkerStatus.COMPLETED
                worker.summary = "Junie session completed successfully."
                worker.workflow_log.append("Session completed.")
            else:
                worker.status = WorkerStatus.FAILED
                worker.summary = f"Junie exited with code {rc}."
                worker.workflow_log.append(f"Session failed (exit code {rc}).")
        except Exception as exc:
            from datetime import datetime
            worker.finished_at = datetime.now()
            worker.status = WorkerStatus.FAILED
            worker.summary = f"Error: {exc}"
            worker.workflow_log.append(f"Error launching junie: {exc}")

    def _sync_selection_from_sidebar(self, list_view: ListView) -> None:
        if list_view.index is None or list_view.index == self.state.selected_index:
            return
        self.state.selected_index = list_view.index
        self.refresh_from_state()
