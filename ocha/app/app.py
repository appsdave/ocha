from __future__ import annotations

import asyncio
import os
import signal
import shutil
import subprocess
from functools import partial
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, ListView, Static, TextArea

from .concurrency import ConcurrencyPolicy, compute_execution_plan
from .file_lock import release_all_for_task, release_inactive_locks
from .git_utils import commit_worktree_changes, ensure_pr_title, format_pr_title, merge_worktree_commits
from .notifications import NotificationCenter, NotificationEvent, NotificationLevel
from .orchestrator import build_role_prompt, launch_task, load_role_definitions
from .state import AppState, OutputMode, WorkerRole, WorkerStatus, clear_finished_tasks, sample_state
from .task_files import write_session_manifest, write_session_prompt
from .worktree_manager import cleanup_worktrees, ensure_worktree as wt_ensure
from .widgets import AgentsPane, MainLayout, NotificationPane, OutputPane, StatusBar, TaskHeader
from .workflow_logger import EventCategory, LogLevel, WorkflowLogger, make_logger

OCHA_BRANCH = "agent"


def _wlog(worker) -> WorkflowLogger:
    """Return the worker's structured logger, creating one on the fly if missing."""
    if worker.wlog is None:
        worker.wlog = make_logger(
            worker.role, worker.session_id, legacy_deque=worker.workflow_log,
        )
    return worker.wlog


# ── Gruvbox Dark Green theme ──────────────────────────────────────────
CSS = """
Screen {
    layout: vertical;
    background: #282828;
    color: #ebdbb2;
    scrollbar-size: 0 0;
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

#agents-pane:focus-within {
    border: solid #b8bb26;
}

#detail-pane {
    width: 1fr;
    height: 1fr;
}

#task-header {
    height: auto;
    max-height: 14;
    border: solid #504945;
    padding: 0 1;
    background: #282828;
}

#task-header:focus-within {
    border: solid #b8bb26;
}

#output-pane {
    height: 1fr;
    min-height: 4;
    border: solid #504945;
    padding: 0 1;
    background: #282828;
}

#output-pane:focus-within {
    border: solid #b8bb26;
}

#output-content {
    width: 1fr;
    height: auto;
    background: #282828;
}

#notifications-pane {
    height: 10;
    min-height: 7;
    border: solid #504945;
    padding: 0 1;
    background: #282828;
}

#notifications-content {
    width: 1fr;
    height: auto;
    background: #282828;
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
    padding: 0 1 1 0;
}

VerticalScroll {
    scrollbar-size: 0 0;
}

ListView {
    background: #282828;
    scrollbar-size: 0 0;
    & > ListItem {
        background: #282828;
        color: #a89984;
        /* Neutralise Textual's built-in highlight — we rely on the
           status-colored arrow and border-left instead. */
        &.-highlight {
            background: #282828;
            color: #a89984;
            text-style: none;
            background-tint: transparent;
        }
        &:hover {
            background: #32302f;
        }
        /* Active / selected task — subtle bg bump + status border */
        &.--selected {
            background: #3c3836;
            color: #fbf1c7;
        }
        &.--selected.-highlight {
            background: #3c3836;
            color: #fbf1c7;
        }
        &.--status-running.--selected {
            border-left: tall #b8bb26;
        }
        &.--status-completed.--selected {
            border-left: tall #83a598;
        }
        &.--status-failed.--selected {
            border-left: tall #fb4934;
        }
        &.--status-queued.--selected {
            border-left: tall #fabd2f;
        }
        &.--status-stopped.--selected {
            border-left: tall #928374;
        }
    }
    &:focus {
        background-tint: transparent;
        /* Focused-pane cursor (non-selected item) — very faint */
        & > ListItem.-highlight {
            background: #32302f;
            color: #ebdbb2;
            text-style: none;
            background-tint: transparent;
        }
        /* Focused + selected — slightly brighter bg */
        & > ListItem.--selected {
            background: #3c3836;
            color: #fbf1c7;
        }
        & > ListItem.--selected.-highlight {
            background: #504945;
            color: #fbf1c7;
            text-style: none;
            background-tint: transparent;
        }
        & > ListItem.--selected.--status-running {
            border-left: tall #b8bb26;
        }
        & > ListItem.--selected.--status-completed {
            border-left: tall #83a598;
        }
        & > ListItem.--selected.--status-failed {
            border-left: tall #fb4934;
        }
        & > ListItem.--selected.--status-queued {
            border-left: tall #fabd2f;
        }
        & > ListItem.--selected.--status-stopped {
            border-left: tall #928374;
        }
    }
}

/* ── Floating new-task overlay ── */
NewTaskOverlay {
    align: center middle;
    background: rgba(0, 0, 0, 0.65);
}

#new-task-box {
    width: 1fr;
    max-width: 72;
    margin: 2 4;
    height: auto;
    border: solid #504945;
    background: #282828;
    padding: 1 2;
}

#new-task-title {
    color: #ebdbb2;
    padding: 0 0 1 0;
}

#new-task-box TextArea {
    background: #3c3836;
    color: #fbf1c7;
    border: solid #504945;
    height: 8;
    width: 1fr;
}

#new-task-box TextArea:focus {
    border: solid #b8bb26;
}

#new-task-hint {
    color: #928374;
    padding: 1 0 0 0;
    height: auto;
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

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("ctrl+s", "submit_task", "Submit"),
    ]

    MAX_PROMPT_LENGTH = 100_000  # ~100 KB guard

    def compose(self) -> ComposeResult:
        with Container(id="new-task-box"):
            yield Static("[#b8bb26]>[/] [b]new task[/b]", id="new-task-title")
            yield TextArea(id="new-task-input")
            yield Static(
                "[#504945]ctrl+s[/] [#928374]submit[/]  "
                "[#504945]esc[/] [#928374]cancel[/]",
                id="new-task-hint",
            )

    def on_mount(self) -> None:
        self.query_one(TextArea).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "submit-task":
            self._submit(self.query_one(TextArea).text)
            return
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_submit_task(self) -> None:
        self._submit(self.query_one(TextArea).text)

    def _submit(self, value: str) -> None:
        task = value.strip()
        if not task:
            self.notify("Task prompt cannot be empty.", severity="warning")
            return
        if len(task) > self.MAX_PROMPT_LENGTH:
            self.notify(
                f"Prompt too long ({len(task):,} chars). Maximum is {self.MAX_PROMPT_LENGTH:,}.",
                severity="warning",
            )
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


def _kill_process_tree(proc: asyncio.subprocess.Process) -> None:
    """Kill a subprocess and all of its descendants.

    When ``start_new_session=True`` was used to spawn the process, every
    child (including Java processes started by Junie) shares the same
    session-id.  Sending SIGKILL to the negative PID kills the entire
    process group so nothing is left behind consuming RAM/swap.

    Falls back to killing just the direct process when the group signal
    fails (e.g. the process already exited).
    """
    pid = proc.pid
    if pid is None:
        return
    try:
        # Kill the entire process group rooted at the session leader.
        os.killpg(os.getpgid(pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        # Process (group) already gone or we lack permissions — try direct kill.
        try:
            proc.kill()
        except ProcessLookupError:
            pass


class OchaApp(App[None]):
    TITLE = "ocha"
    SUB_TITLE = "Python/Textual rebuild"
    CSS = CSS
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("up", "move_up", "Up", show=False),
        Binding("down", "move_down", "Down", show=False),
        Binding("v", "toggle_view", "Toggle View"),
        Binding("left", "focus_agents", "Focus Agents"),
        Binding("right", "focus_output", "Focus Output"),
        Binding("n", "new_task", "New Task"),
        Binding("c", "clear_finished", "Clear Finished"),
        Binding("x", "kill_selected", "Kill Selected"),
        Binding("tab", "cycle_focus", "Cycle Focus", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.state: AppState = sample_state()
        self._tick_fingerprint: tuple = ()
        self._running_procs: dict[str, asyncio.subprocess.Process] = {}
        self.notification_center = NotificationCenter(self._dispatch_notification)

    def compose(self) -> ComposeResult:
        yield MainLayout()

    async def on_unmount(self) -> None:
        """Terminate all running subprocesses and their entire process trees
        before the event loop closes (avoids 'Event loop is closed' errors
        and prevents leaked Java/child processes from consuming RAM)."""
        for proc in list(self._running_procs.values()):
            if proc.returncode is None:
                _kill_process_tree(proc)
        for proc in list(self._running_procs.values()):
            try:
                await proc.wait()
            except Exception:
                pass
        self._running_procs.clear()
        for task in self.state.tasks:
            self._release_task_locks(task)

    def on_mount(self) -> None:
        self._ensure_ocha_branch()
        self._reconcile_locks()
        self.refresh_from_state()
        self.action_focus_agents()
        self.set_interval(1.0, self._tick)

    def _project_root(self) -> Path:
        return Path.cwd().resolve()

    def _active_session_ids(self) -> set[str]:
        return {
            worker.session_id
            for task in self.state.tasks
            for worker in task.workers
            if worker.status in (WorkerStatus.RUNNING, WorkerStatus.QUEUED)
        }

    def _reconcile_locks(self) -> int:
        return release_inactive_locks(self._project_root(), self._active_session_ids())

    def _release_task_locks(self, task_obj) -> int:
        return release_all_for_task(self._project_root(), task_obj.task_id)

    def _dispatch_notification(self, event: NotificationEvent) -> None:
        self._refresh_notifications()
        self.notify(
            event.rich_message(),
            title=event.title,
            severity=event.severity,
            timeout=event.timeout,
        )

    def _notify(
        self,
        message: str,
        *,
        level: NotificationLevel = NotificationLevel.INFO,
        title: str = "",
        timeout: float | None = None,
        dedupe_key: str | None = None,
    ) -> bool:
        return self.notification_center.emit(
            message,
            level=level,
            title=title,
            timeout=timeout,
            dedupe_key=dedupe_key,
        )

    def _tick(self) -> None:
        """Periodic UI refresh for elapsed timers and async state changes."""
        if not self.state.tasks:
            return
        has_active = any(
            t.status in (WorkerStatus.RUNNING, WorkerStatus.QUEUED)
            for t in self.state.tasks
        )
        if not has_active:
            return
        # Build a lightweight fingerprint to skip refresh when nothing changed
        selected = self.state.selected_task
        if selected is not None:
            fp: tuple = (
                selected.task_id,
                selected.status.value,
                self.state.output_mode,
                # Only count total lines — avoids iterating every line
                sum(len(w.workflow_log) + len(w.raw_log) for w in selected.workers),
                # Include elapsed so timers update
                selected.elapsed,
            )
        else:
            fp = ()
        if fp != self._tick_fingerprint:
            self._tick_fingerprint = fp
            self.refresh_from_state()

    def _ensure_ocha_branch(self) -> None:
        """Create and checkout the agent branch if it doesn't already exist."""
        try:
            # Check if we're in a git repo
            top = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True, text=True, timeout=5,
            )
            if top.returncode != 0:
                self._notify("Not a git repo — skipping branch setup", level=NotificationLevel.WARNING)
                return

            current = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, text=True, timeout=5,
            )
            if current.returncode == 0 and current.stdout.strip() == OCHA_BRANCH:
                return  # already on ocha branch, silently continue

            # Check if branch exists
            check = subprocess.run(
                ["git", "rev-parse", "--verify", OCHA_BRANCH],
                capture_output=True, text=True, timeout=5,
            )
            if check.returncode == 0:
                result = subprocess.run(
                    ["git", "checkout", OCHA_BRANCH],
                    capture_output=True, text=True, timeout=10,
                )
            else:
                result = subprocess.run(
                    ["git", "checkout", "-b", OCHA_BRANCH],
                    capture_output=True, text=True, timeout=10,
                )

            if result.returncode != 0:
                self._notify(
                    f"Failed to switch to {OCHA_BRANCH}: {result.stderr.strip()}",
                    level=NotificationLevel.ERROR,
                )
                return

            # Verify the branch is actually checked out
            verify = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, text=True, timeout=5,
            )
            if verify.returncode == 0 and verify.stdout.strip() == OCHA_BRANCH:
                pass  # silently on branch
            else:
                self._notify(
                    f"Branch switch failed — on {verify.stdout.strip()}",
                    level=NotificationLevel.ERROR,
                )
        except Exception as exc:
            self._notify(f"Branch setup error: {exc}", level=NotificationLevel.ERROR)

    def refresh_from_state(self) -> None:
        try:
            self.query_one(AgentsPane).load(self.state)
            selected = self.state.selected_task
            total = len(self.state.tasks)
            position = f"{self.state.selected_index + 1}/{total}" if total > 0 else ""
            self.query_one(TaskHeader).update_task(selected, position=position)
            self.query_one(OutputPane).update_task(selected, self.state.output_mode)
            self._refresh_notifications()
            self.query_one(StatusBar).update_state(self.state)
        except Exception:
            pass  # widgets not yet mounted

    def _refresh_notifications(self) -> None:
        try:
            self.query_one(NotificationPane).load(self.notification_center.history)
        except Exception:
            pass  # widget not yet mounted

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
        if any(isinstance(s, NewTaskOverlay) for s in self.screen_stack):
            return  # prevent double-open
        self.push_screen(NewTaskOverlay(), self._launch_task_from_prompt)

    def action_clear_finished(self) -> None:
        original_count = len(self.state.tasks)
        self.state = clear_finished_tasks(self.state)
        cleared_count = original_count - len(self.state.tasks)
        if not cleared_count:
            self._notify("No finished tasks to clear.")
            return
        self.refresh_from_state()
        self._notify(
            f"Cleared {cleared_count} finished task{'s' if cleared_count != 1 else ''}.",
            level=NotificationLevel.SUCCESS,
        )

    def action_kill_selected(self) -> None:
        task = self.state.selected_task
        if task is None:
            self._notify("No task selected to kill.", level=NotificationLevel.WARNING)
            return
        self.push_screen(KillConfirmOverlay(task.task_id, task.title), self._handle_kill)

    def _handle_kill(self, confirmed: bool) -> None:
        if not confirmed:
            return
        task = self.state.selected_task
        if task is None:
            return
        killed_count = 0
        for worker in task.workers:
            if worker.status in (WorkerStatus.RUNNING, WorkerStatus.QUEUED):
                worker.status = WorkerStatus.STOPPED
                # Kill the actual junie process and all its children (e.g. Java)
                proc = self._running_procs.pop(worker.session_id, None)
                if proc and proc.returncode is None:
                    _kill_process_tree(proc)
                from datetime import datetime
                worker.finished_at = datetime.now()
                _wlog(worker).lifecycle(
                    f"Killed by operator at {worker.finished_at:%H:%M:%S}.",
                    LogLevel.WARNING,
                )
                worker.summary = "Killed by operator."
                killed_count += 1
        released_locks = self._release_task_locks(task)
        self.refresh_from_state()
        message = (
            f"Killed task {task.task_id} — {killed_count} worker{'s' if killed_count != 1 else ''} stopped."
        )
        if released_locks:
            message += f" Released {released_locks} lock{'s' if released_locks != 1 else ''}."
        self._notify(message, level=NotificationLevel.WARNING)

    def _launch_task_from_prompt(self, task: str | None) -> None:
        if task is None:
            self._notify("New task cancelled.")
            return
        self.state = launch_task(self.state, task)
        self.refresh_from_state()
        task_obj = self.state.selected_task
        if task_obj:
            running = sum(1 for w in task_obj.workers if w.status == WorkerStatus.RUNNING)
            queued = sum(1 for w in task_obj.workers if w.status == WorkerStatus.QUEUED)
            self._notify(
                f"Task {task_obj.task_id} launched — {running} running, {queued} queued",
                level=NotificationLevel.SUCCESS,
            )
            # Actually spawn Junie headless for the running worker
            self._spawn_junie_workers(task_obj)
        else:
            self._notify("Task launched.")

    def _load_junie_api_key(self) -> str | None:
        """Load JUNIE_API_KEY from environment or .env file."""
        key = os.environ.get("JUNIE_API_KEY")
        if key:
            return key
        # Try loading from .env in the install directory
        for env_path in [Path.cwd() / ".env", Path.home() / ".ocha" / ".env"]:
            if env_path.exists():
                for line in env_path.read_text().splitlines():
                    line = line.strip()
                    if line.startswith("JUNIE_API_KEY=") and len(line) > len("JUNIE_API_KEY="):
                        return line.split("=", 1)[1].strip()
        return None

    def _ensure_worktree(self, worker) -> bool:
        """Create a git worktree for the worker if it doesn't exist.

        Delegates to :func:`worktree_manager.ensure_worktree` for
        idempotent, error-isolated worktree creation.

        Returns True on success, False on failure.
        """
        result = wt_ensure(worker.worktree_path, branch=OCHA_BRANCH)
        level = LogLevel.SUCCESS if result.success else LogLevel.ERROR
        _wlog(worker).git(result.message, level)
        return result.success

    def _write_prompt_file(self, worker) -> Path:
        """Write the worker's prompt to a file and return the path."""
        repo_root = Path.cwd().resolve()
        prompt_file = write_session_prompt(worker.task_id, worker.session_id, worker.task_prompt, repo_root)
        write_session_manifest(
            worker.task_id,
            worker.session_id,
            {
                "task_id": worker.task_id,
                "session_id": worker.session_id,
                "role": worker.role.value,
                "owned_directory": worker.owned_directory,
                "worktree_path": str(worker.worktree_path),
                "role_prompt_path": worker.role_prompt_path,
            },
            repo_root,
        )
        return prompt_file

    def _spawn_junie_workers(self, task_obj) -> None:
        """Spawn Junie CLI headless for each RUNNING worker in the task."""
        junie_bin = shutil.which("junie")
        if not junie_bin:
            self._notify(
                "junie CLI not found on PATH",
                level=NotificationLevel.ERROR,
                dedupe_key="junie-cli-missing",
            )
            return
        api_key = self._load_junie_api_key()
        if not api_key:
            self._notify(
                "JUNIE_API_KEY not set — add it to .env or run install.sh",
                level=NotificationLevel.ERROR,
                dedupe_key="junie-api-key-missing",
            )
            return
        for worker in task_obj.workers:
            if worker.status == WorkerStatus.RUNNING:
                self.run_worker(self._run_junie_for_worker(worker, task_obj, api_key))

    async def _run_junie_for_worker(self, worker, task_obj, api_key: str | None = None) -> None:
        """Run Junie headless CLI for a single worker and stream output."""
        try:
            # Create worktree for this worker
            if not self._ensure_worktree(worker):
                from datetime import datetime
                worker.finished_at = datetime.now()
                worker.status = WorkerStatus.FAILED
                worker.summary = "Failed to create worktree."
                self._advance_pipeline(task_obj)
                return

            project_path = Path(worker.worktree_path)

            # Load API key if not passed (for pipeline-advanced workers)
            if not api_key:
                api_key = self._load_junie_api_key()

            # Write prompt to file to avoid shell arg-length limits
            prompt_file = self._write_prompt_file(worker)

            # Truncate upstream-heavy prompts to stay within Junie's
            # internal issue parser limits (~32 KB safe ceiling).
            MAX_TASK_BYTES = 32_000
            task_text = prompt_file.read_text(encoding="utf-8")
            if len(task_text.encode("utf-8")) > MAX_TASK_BYTES:
                task_text = task_text[:MAX_TASK_BYTES].rsplit("\n", 1)[0]
                _wlog(worker).prompt(
                    f"Prompt truncated to ~{MAX_TASK_BYTES // 1000} KB to stay within Junie limits.",
                    LogLevel.WARNING,
                )
                prompt_file.write_text(task_text, encoding="utf-8")

            cmd = [
                "junie",
                f"--auth={api_key}" if api_key else None,
                "--project", str(project_path),
                "--output-format", "text",
            ]
            # Remove None entries
            cmd = [c for c in cmd if c is not None]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                start_new_session=True,
            )

            # Feed the task via stdin to avoid CLI arg-length and
            # markdown-parsing issues inside Junie's issue builder.
            proc.stdin.write(task_text.encode("utf-8"))
            proc.stdin.write_eof()
            self._running_procs[worker.session_id] = proc

            _wlog(worker).junie(f"Started junie process (PID {proc.pid}).")
            worker.latest_event = "junie_started"
            self.refresh_from_state()

            async for raw_line in proc.stdout:
                line = raw_line.decode(errors="replace").rstrip()
                worker.raw_log.append(line)
                if line:
                    _wlog(worker).junie(line, LogLevel.DEBUG)
                    worker.latest_event = line[:80]
                    self.refresh_from_state()

            rc = await proc.wait()
            self._running_procs.pop(worker.session_id, None)

            from datetime import datetime
            worker.finished_at = datetime.now()
            wl = _wlog(worker)
            if rc == 0:
                worker.status = WorkerStatus.COMPLETED
                worker.summary = "Junie session completed successfully."
                wl.lifecycle("Session completed.", LogLevel.SUCCESS)
                # Commit changes inside the worktree so they are reachable
                try:
                    sha = commit_worktree_changes(
                        worker.worktree_path,
                        f"ocha: {worker.role} {worker.session_id}",
                    )
                    if sha:
                        worker.worktree_commit_sha = sha
                        wl.git(f"Worktree committed: {sha[:8]}", LogLevel.SUCCESS)
                    else:
                        wl.git("Worktree clean — nothing to commit.", LogLevel.DEBUG)
                except Exception as commit_exc:
                    wl.git(f"Worktree commit error: {commit_exc}", LogLevel.ERROR)
            else:
                worker.status = WorkerStatus.FAILED
                worker.summary = f"Junie exited with code {rc}."
                wl.lifecycle(f"Session failed (exit code {rc}).", LogLevel.ERROR)

            self.refresh_from_state()
            # Advance pipeline: start next queued worker in this task
            self._advance_pipeline(task_obj)

        except Exception as exc:
            from datetime import datetime
            worker.finished_at = datetime.now()
            worker.status = WorkerStatus.FAILED
            worker.summary = f"Error: {exc}"
            _wlog(worker).junie(f"Error launching junie: {exc}", LogLevel.ERROR)
            self._advance_pipeline(task_obj)

    def _advance_pipeline(self, task_obj) -> None:
        """Start the next execution group in the pipeline after one finishes.

        Uses :func:`compute_execution_plan` to determine which workers
        can run concurrently (non-overlapping owned directories) and
        launches them together via parallel ``run_worker`` calls.

        Captures the most recently completed worker's summary and injects
        it as ``upstream_output`` into every worker in the next group so
        each phase receives the prior phase's artifact.
        """
        # Check if any worker is still running
        still_running = any(w.status == WorkerStatus.RUNNING for w in task_obj.workers)
        if still_running:
            return

        # Collect the last completed worker's output for handoff.
        MAX_UPSTREAM_LINES = 20
        MAX_UPSTREAM_CHARS = 4_000
        upstream = ""
        for w in reversed(task_obj.workers):
            if w.status == WorkerStatus.COMPLETED:
                if w.workflow_log:
                    upstream = "\n".join(list(w.workflow_log)[-MAX_UPSTREAM_LINES:])
                elif w.summary:
                    upstream = w.summary
                if len(upstream) > MAX_UPSTREAM_CHARS:
                    upstream = upstream[:MAX_UPSTREAM_CHARS].rsplit("\n", 1)[0]
                break

        # Compute execution groups from queued workers only
        queued_workers = [
            (i, w) for i, w in enumerate(task_obj.workers)
            if w.status == WorkerStatus.QUEUED
        ]
        if not queued_workers:
            # All done — summarize
            completed = sum(1 for w in task_obj.workers if w.status == WorkerStatus.COMPLETED)
            failed = sum(1 for w in task_obj.workers if w.status == WorkerStatus.FAILED)
            level = LogLevel.SUCCESS if failed == 0 else LogLevel.WARNING
            _wlog(task_obj.workers[-1]).pipeline(
                f"Pipeline finished — {completed} completed, {failed} failed.",
                level,
            )
            # Run the branch/push/PR process
            self.run_worker(self._post_pipeline_git_flow(task_obj))
            return

        # Use compute_execution_plan on queued workers to find the next
        # parallel group.  Only launch the first group; subsequent groups
        # will be launched when this group completes.
        queued_sessions = [w for _, w in queued_workers]
        plan = compute_execution_plan(queued_sessions, ConcurrencyPolicy.AUTO)

        if not plan:
            return

        first_group = plan[0]
        workers_to_launch = list(first_group.workers)

        junie_bin = shutil.which("junie")
        if not junie_bin:
            for w in workers_to_launch:
                w.status = WorkerStatus.FAILED
                w.summary = "junie CLI not found"
                _wlog(w).junie("junie CLI not found on PATH.", LogLevel.ERROR)
            return

        api_key = self._load_junie_api_key()

        for w in workers_to_launch:
            nwl = _wlog(w)
            if upstream:
                w.upstream_summary = upstream
                w.task_prompt = self._rebuild_prompt_with_upstream(
                    w, task_obj, upstream,
                )
                nwl.pipeline(
                    f"Received upstream output from prior phase ({len(upstream)} chars).",
                )

            w.status = WorkerStatus.RUNNING
            group_size = len(workers_to_launch)
            if group_size > 1:
                nwl.pipeline(
                    f"Pipeline advanced — starting {w.role} "
                    f"(parallel group of {group_size}).",
                )
            else:
                nwl.pipeline(f"Pipeline advanced — starting {w.role}.")
            self.run_worker(self._run_junie_for_worker(w, task_obj, api_key))

    def _rebuild_prompt_with_upstream(
        self, worker, task_obj, upstream_output: str,
    ) -> str:
        """Rebuild a worker's task prompt to include upstream phase output."""
        try:
            role_defs = load_role_definitions()
            definition = role_defs[WorkerRole(worker.role)]
            project_path = Path.cwd().resolve()
            return build_role_prompt(
                definition,
                task_id=worker.task_id,
                session_id=worker.session_id,
                title=task_obj.title,
                user_task=task_obj.user_task,
                project_path=project_path,
                worktree_path=Path(worker.worktree_path),
                owned_directory=worker.owned_directory,
                upstream_output=upstream_output,
            )
        except Exception:
            # Fallback: append upstream to existing prompt
            return worker.task_prompt + f"\n\n## Prior phase output\n\n{upstream_output}"

    async def _post_pipeline_git_flow(self, task_obj) -> None:
        """After all workers finish, cherry-pick worktree commits onto ``agent``, rebase, and push.

        All blocking ``subprocess.run`` calls are delegated to a background
        thread via ``asyncio.to_thread`` so the Textual event loop stays
        responsive while git operations execute.
        """
        wl = _wlog(task_obj.workers[-1])
        branch_name = OCHA_BRANCH

        def _run_git(*args: str, timeout: int = 30, **kwargs) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                list(args), capture_output=True, text=True, timeout=timeout, **kwargs,
            )

        GitMsg = tuple[LogLevel, str]

        def _git_flow_sync() -> list[GitMsg]:
            """Execute git flow in a sync context (called via to_thread)."""
            messages: list[GitMsg] = []
            worktree_shas = [
                w.worktree_commit_sha
                for w in task_obj.workers
                if w.worktree_commit_sha
            ]

            if worktree_shas:
                merge_logs = merge_worktree_commits(worktree_shas, branch_name)
                messages.extend((LogLevel.INFO, m) for m in merge_logs)
            else:
                current = _run_git("git", "rev-parse", "--abbrev-ref", "HEAD", timeout=5)
                if current.returncode == 0 and current.stdout.strip() != branch_name:
                    _run_git("git", "checkout", branch_name, timeout=10)
                messages.append((LogLevel.INFO, f"On branch {branch_name} (no worktree commits)."))

                _run_git("git", "add", "-A", "--", ".", ":!.worktrees", ":!.env", timeout=10)

                diff_check = _run_git("git", "diff", "--cached", "--quiet", timeout=5)
                if diff_check.returncode != 0:
                    commit_msg = f"ocha: {task_obj.title}"
                    commit_result = _run_git("git", "commit", "-m", commit_msg, timeout=15)
                    if commit_result.returncode == 0:
                        messages.append((LogLevel.SUCCESS, f"Committed: {commit_msg}"))
                    else:
                        messages.append((
                            LogLevel.WARNING,
                            f"Commit note: {commit_result.stdout.strip() or commit_result.stderr.strip()}",
                        ))
                else:
                    messages.append((LogLevel.DEBUG, "No changes to commit."))

            _run_git("git", "fetch", "origin", branch_name, timeout=30)
            rebase_result = _run_git("git", "rebase", f"origin/{branch_name}", timeout=30)
            if rebase_result.returncode == 0:
                messages.append((LogLevel.SUCCESS, f"Rebased on origin/{branch_name}."))
            else:
                messages.append((LogLevel.WARNING, f"Rebase skipped: {rebase_result.stderr.strip()}"))

            push_result = _run_git("git", "push", "-u", "origin", branch_name, timeout=30)
            if push_result.returncode == 0:
                messages.append((LogLevel.SUCCESS, f"Pushed branch {branch_name} to origin."))
            else:
                messages.append((LogLevel.ERROR, f"Push failed: {push_result.stderr.strip()}"))

            # Format a clean PR title and create-or-update the PR
            pr_title = format_pr_title(task_obj.task_id, task_obj.title)
            pr_msg = ensure_pr_title(branch_name, pr_title)
            messages.append((LogLevel.INFO, pr_msg))

            messages.append((LogLevel.INFO, f"Staying on shared branch {branch_name}."))

            wt_paths = [w.worktree_path for w in task_obj.workers]
            cleanup_results = cleanup_worktrees(wt_paths, prune=True, timeout=15)
            cleaned = sum(1 for r in cleanup_results if r.success)
            messages.append((LogLevel.DEBUG, f"Cleaned up {cleaned}/{len(wt_paths)} worktrees."))
            released_locks = release_all_for_task(Path.cwd().resolve(), task_obj.task_id)
            messages.append((LogLevel.DEBUG, f"Released {released_locks} lock{'s' if released_locks != 1 else ''}."))
            return messages

        try:
            messages = await asyncio.to_thread(_git_flow_sync)
            for level, msg in messages:
                wl.git(msg, level)
        except Exception as exc:
            wl.git(f"Git flow error: {exc}", LogLevel.ERROR)

    def _sync_selection_from_sidebar(self, list_view: ListView) -> None:
        if list_view.index is None or list_view.index == self.state.selected_index:
            return
        self.state.selected_index = list_view.index
        self.refresh_from_state()
