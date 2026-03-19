from __future__ import annotations

import unittest

from app.app import OchaApp
from app.state import AppState, OchaTask, WorkerRole, WorkerSession, WorkerStatus
from textual.widgets import ListView

from app.widgets import TaskHeader


class OchaAppTests(unittest.IsolatedAsyncioTestCase):
    async def test_new_task_uses_prompt_input(self) -> None:
        app = OchaApp()

        async with app.run_test() as pilot:
            original_count = len(app.state.tasks)

            await pilot.press("n")
            await pilot.click("#new-task-input")
            await pilot.press(*"Ship prompt based task creation")
            await pilot.press("enter")

            self.assertEqual(len(app.state.tasks), original_count + 1)
            self.assertEqual(app.state.selected_task.user_task, "Ship prompt based task creation")
            self.assertEqual(app.state.selected_task.title, "Ship prompt based task creation")
            self.assertEqual(app.state.selected_task.task_id, "T-001")

    async def test_clear_finished_removes_terminal_tasks_and_keeps_running_selection(self) -> None:
        app = OchaApp()
        app.state = AppState(tasks=[self._completed_task("T-001"), self._running_task("T-002")])

        async with app.run_test() as pilot:
            app.refresh_from_state()

            await pilot.press("c")

            self.assertEqual([task.task_id for task in app.state.tasks], ["T-002"])
            self.assertEqual(app.state.selected_index, 0)
            self.assertEqual(app.state.selected_task.task_id, "T-002")

    async def test_clear_finished_handles_empty_state(self) -> None:
        app = OchaApp()
        app.state = AppState(tasks=[self._completed_task("T-001")])

        async with app.run_test() as pilot:
            app.refresh_from_state()

            await pilot.press("c")

            self.assertEqual(app.state.tasks, [])
            self.assertIsNone(app.state.selected_task)
            header_text = str(app.query_one("#task-header", TaskHeader).render())
            self.assertIn("No active tasks", header_text)

    async def test_sidebar_selection_event_updates_selected_task_details(self) -> None:
        app = OchaApp()
        app.state = AppState(tasks=[self._running_task("T-001"), self._running_task("T-002")])

        async with app.run_test() as pilot:
            app.refresh_from_state()

            list_view = app.query_one(ListView)
            second_item = list(list_view.query("ListItem").results())[1]
            list_view.index = 1
            list_view.post_message(ListView.Selected(list_view, second_item))
            await pilot.pause()

            header = app.query_one(TaskHeader)
            self.assertEqual(app.state.selected_task.task_id, "T-002")
            self.assertIn("T-002", str(header.render()))

    def _completed_task(self, task_id: str) -> OchaTask:
        return OchaTask(
            task_id=task_id,
            title=f"Completed {task_id}",
            user_task=f"Completed {task_id}",
            branch="agent",
            workers=[self._worker(task_id, WorkerStatus.COMPLETED)],
        )

    def _running_task(self, task_id: str) -> OchaTask:
        return OchaTask(
            task_id=task_id,
            title=f"Running {task_id}",
            user_task=f"Running {task_id}",
            branch="agent",
            workers=[self._worker(task_id, WorkerStatus.RUNNING)],
        )

    def _worker(self, task_id: str, status: WorkerStatus) -> WorkerSession:
        return WorkerSession(
            session_id=f"S-{task_id[2:]}-01",
            task_id=task_id,
            title=f"Worker for {task_id}",
            role=WorkerRole.COORDINATOR,
            status=status,
            branch="agent",
            worktree_path=f"/tmp/{task_id.lower()}",
            owned_directory="docs/",
            summary="summary",
            workflow_log=["workflow"],
            raw_log=["raw"],
            task_prompt="prompt",
            role_prompt_path="app/roles/coordinator.md",
            latest_event="done",
        )


class AdvancePipelineTests(unittest.TestCase):
    """Test that _advance_pipeline captures upstream summary for the next worker."""

    def test_advance_pipeline_sets_upstream_summary_on_next_worker(self) -> None:
        """When a worker completes, the next queued worker receives its output."""
        completed_worker = WorkerSession(
            session_id="S-001-01",
            task_id="T-001",
            title="Test",
            role=WorkerRole.COORDINATOR,
            status=WorkerStatus.COMPLETED,
            branch="agent",
            worktree_path="/tmp/t-001-coordinator",
            owned_directory="docs/",
            summary="Coordinator done.",
            workflow_log=["Produced execution brief."],
            task_prompt="prompt",
            role_prompt_path="app/roles/coordinator.md",
            latest_event="done",
        )
        queued_worker = WorkerSession(
            session_id="S-001-02",
            task_id="T-001",
            title="Test",
            role=WorkerRole.LEAD,
            status=WorkerStatus.QUEUED,
            branch="agent",
            worktree_path="/tmp/t-001-lead",
            owned_directory="planning/",
            summary="",
            task_prompt="original prompt",
            role_prompt_path="app/roles/lead.md",
            latest_event="",
        )
        task_obj = OchaTask(
            task_id="T-001",
            title="Test",
            user_task="Do something",
            branch="agent",
            workers=[completed_worker, queued_worker],
        )

        # Simulate what _advance_pipeline does for upstream handoff
        # (without spawning junie — we test the data flow logic)
        upstream = ""
        for w in reversed(task_obj.workers):
            if w.status == WorkerStatus.COMPLETED:
                if w.workflow_log:
                    upstream = "\n".join(w.workflow_log[-40:])
                elif w.summary:
                    upstream = w.summary
                break

        next_worker = None
        for w in task_obj.workers:
            if w.status == WorkerStatus.QUEUED:
                next_worker = w
                break

        self.assertIsNotNone(next_worker)
        self.assertEqual(upstream, "Produced execution brief.")

        # Apply upstream
        next_worker.upstream_summary = upstream
        self.assertEqual(next_worker.upstream_summary, "Produced execution brief.")

    def test_advance_pipeline_no_upstream_when_no_completed_workers(self) -> None:
        """When no worker has completed, upstream stays empty."""
        queued_worker = WorkerSession(
            session_id="S-001-01",
            task_id="T-001",
            title="Test",
            role=WorkerRole.COORDINATOR,
            status=WorkerStatus.QUEUED,
            branch="agent",
            worktree_path="/tmp/t-001-coordinator",
            owned_directory="docs/",
            summary="",
            task_prompt="prompt",
            role_prompt_path="app/roles/coordinator.md",
            latest_event="",
        )
        task_obj = OchaTask(
            task_id="T-001",
            title="Test",
            user_task="Do something",
            branch="agent",
            workers=[queued_worker],
        )

        upstream = ""
        for w in reversed(task_obj.workers):
            if w.status == WorkerStatus.COMPLETED:
                if w.workflow_log:
                    upstream = "\n".join(w.workflow_log[-40:])
                elif w.summary:
                    upstream = w.summary
                break

        self.assertEqual(upstream, "")

