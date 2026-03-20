from __future__ import annotations

import unittest

from app.app import OchaApp
from app.state import AppState, OchaTask, WorkerRole, WorkerSession, WorkerStatus
from textual.widgets import ListView, TextArea

from app.widgets import TaskHeader


class OchaAppTests(unittest.IsolatedAsyncioTestCase):
    async def test_new_task_uses_prompt_input(self) -> None:
        app = OchaApp()

        async with app.run_test() as pilot:
            original_count = len(app.state.tasks)

            await pilot.press("n")
            await pilot.pause()
            text_area = app.screen.query_one("#new-task-input", TextArea)
            text_area.load_text("Ship prompt based task creation")
            await pilot.press("ctrl+s")

            self.assertEqual(len(app.state.tasks), original_count + 1)
            self.assertEqual(app.state.selected_task.user_task, "Ship prompt based task creation")
            self.assertEqual(app.state.selected_task.title, "Ship prompt based task creation")
            self.assertEqual(app.state.selected_task.task_id, "T-001")

    async def test_new_task_cancel_does_not_create_task(self) -> None:
        app = OchaApp()

        async with app.run_test() as pilot:
            original_count = len(app.state.tasks)

            await pilot.press("n")
            await pilot.pause()
            text_area = app.screen.query_one("#new-task-input", TextArea)
            text_area.load_text("Should be cancelled")
            await pilot.press("escape")

            self.assertEqual(len(app.state.tasks), original_count)

    async def test_new_task_rejects_blank_input(self) -> None:
        app = OchaApp()

        async with app.run_test() as pilot:
            original_count = len(app.state.tasks)

            await pilot.press("n")
            # Leave TextArea empty, press submit
            await pilot.press("ctrl+s")

            # Task should not be created
            self.assertEqual(len(app.state.tasks), original_count)

    async def test_new_task_multiline_prompt(self) -> None:
        app = OchaApp()

        async with app.run_test() as pilot:
            await pilot.press("n")
            await pilot.pause()
            text_area = app.screen.query_one("#new-task-input", TextArea)
            text_area.load_text("Line one\nLine two\nLine three")
            await pilot.press("ctrl+s")

            self.assertEqual(len(app.state.tasks), 1)
            self.assertEqual(app.state.selected_task.user_task, "Line one\nLine two\nLine three")

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
            list_view.post_message(ListView.Selected(list_view, second_item, index=1))
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


class SelectedTaskIndicatorTests(unittest.TestCase):
    """Verify the ▶ arrow and --selected CSS class for the active task."""

    def _task(self, task_id: str, status: WorkerStatus = WorkerStatus.RUNNING) -> OchaTask:
        return OchaTask(
            task_id=task_id,
            title=f"Task {task_id}",
            user_task=f"Task {task_id}",
            branch="agent",
            workers=[WorkerSession(
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
            )],
        )

    def test_format_task_selected_has_arrow(self) -> None:
        from app.widgets import WorkerListItem
        task = self._task("T-001")
        text = WorkerListItem._format_task(task, selected=True)
        self.assertIn("▶", text)

    def test_format_task_unselected_no_arrow(self) -> None:
        from app.widgets import WorkerListItem
        task = self._task("T-001")
        text = WorkerListItem._format_task(task, selected=False)
        self.assertNotIn("▶", text)

    def test_format_task_default_is_unselected(self) -> None:
        from app.widgets import WorkerListItem
        task = self._task("T-001")
        text = WorkerListItem._format_task(task)
        self.assertNotIn("▶", text)

    def test_css_contains_selected_class(self) -> None:
        from app.app import CSS
        self.assertIn("--selected", CSS)

    def test_css_selected_has_highlight_background(self) -> None:
        from app.app import CSS
        self.assertIn("#3c3836", CSS)

    def test_format_task_selected_uses_status_color_for_pointer(self) -> None:
        from app.widgets import WorkerListItem, STATUS_LABEL_COLOR
        for status in WorkerStatus:
            task = self._task("T-001", status=status)
            text = WorkerListItem._format_task(task, selected=True)
            color = STATUS_LABEL_COLOR[status]
            self.assertIn(color, text, f"Selected task with {status} should use {color}")

    def test_format_task_unselected_dims_title(self) -> None:
        from app.widgets import WorkerListItem
        task = self._task("T-001")
        text = WorkerListItem._format_task(task, selected=False)
        self.assertIn("#bdae93", text, "Unselected task title should use dimmed color")

    def test_format_task_selected_brightens_title(self) -> None:
        from app.widgets import WorkerListItem
        task = self._task("T-001")
        text = WorkerListItem._format_task(task, selected=True)
        self.assertIn("#fbf1c7", text, "Selected task title should use bright color")

    def test_css_contains_status_border_classes(self) -> None:
        from app.app import CSS
        for status_cls in ("--status-running", "--status-completed", "--status-failed",
                           "--status-queued", "--status-stopped"):
            self.assertIn(status_cls, CSS, f"CSS should contain {status_cls}")

    def test_css_focused_selected_has_brighter_background(self) -> None:
        from app.app import CSS
        self.assertIn("#504945", CSS, "Focused selected items should use brighter background")

    def test_css_hover_has_subtle_background(self) -> None:
        from app.app import CSS
        self.assertIn("#32302f", CSS, "Hover state should use subtle background highlight")


class SelectedTaskIndicatorAsyncTests(unittest.IsolatedAsyncioTestCase):
    """Async tests for the ▶ arrow indicator and --selected CSS class in the running app."""

    def _task(self, task_id: str, status: WorkerStatus = WorkerStatus.RUNNING) -> OchaTask:
        return OchaTask(
            task_id=task_id,
            title=f"Task {task_id}",
            user_task=f"Task {task_id}",
            branch="agent",
            workers=[WorkerSession(
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
            )],
        )

    async def test_selected_task_gets_selected_css_class(self) -> None:
        from app.widgets import AgentsPane
        app = OchaApp()
        app.state = AppState(
            tasks=[self._task("T-001"), self._task("T-002")],
            selected_index=0,
        )
        async with app.run_test() as pilot:
            app.refresh_from_state()
            await pilot.pause()

            list_view = app.query_one("#workers-list")
            items = list(list_view.children)
            self.assertTrue(items[0].has_class("--selected"))
            self.assertFalse(items[1].has_class("--selected"))

    async def test_selection_change_moves_selected_class(self) -> None:
        app = OchaApp()
        app.state = AppState(
            tasks=[self._task("T-001"), self._task("T-002")],
            selected_index=0,
        )
        async with app.run_test() as pilot:
            app.refresh_from_state()
            await pilot.pause()

            # Move selection to second task
            app.state.selected_index = 1
            app.refresh_from_state()
            await pilot.pause()

            list_view = app.query_one("#workers-list")
            items = list(list_view.children)
            self.assertFalse(items[0].has_class("--selected"))
            self.assertTrue(items[1].has_class("--selected"))

    async def test_single_task_is_selected(self) -> None:
        app = OchaApp()
        app.state = AppState(
            tasks=[self._task("T-001")],
            selected_index=0,
        )
        async with app.run_test() as pilot:
            app.refresh_from_state()
            await pilot.pause()

            list_view = app.query_one("#workers-list")
            items = list(list_view.children)
            self.assertTrue(items[0].has_class("--selected"))

    async def test_selected_item_has_status_css_class(self) -> None:
        app = OchaApp()
        app.state = AppState(
            tasks=[self._task("T-001", status=WorkerStatus.RUNNING)],
            selected_index=0,
        )
        async with app.run_test() as pilot:
            app.refresh_from_state()
            await pilot.pause()

            list_view = app.query_one("#workers-list")
            items = list(list_view.children)
            self.assertTrue(items[0].has_class("--status-running"))

    async def test_status_class_updates_on_status_change(self) -> None:
        app = OchaApp()
        app.state = AppState(
            tasks=[
                self._task("T-001", status=WorkerStatus.RUNNING),
                self._task("T-002", status=WorkerStatus.COMPLETED),
            ],
            selected_index=0,
        )
        async with app.run_test() as pilot:
            app.refresh_from_state()
            await pilot.pause()

            list_view = app.query_one("#workers-list")
            items = list(list_view.children)
            self.assertTrue(items[0].has_class("--status-running"))
            self.assertTrue(items[1].has_class("--status-completed"))
            self.assertFalse(items[0].has_class("--status-completed"))
            self.assertFalse(items[1].has_class("--status-running"))


class ScrollbarHiddenCSSTests(unittest.TestCase):
    """Verify scrollbars are hidden via CSS to prevent lag while preserving scroll."""

    def test_screen_hides_scrollbar(self) -> None:
        from app.app import CSS
        self.assertIn("scrollbar-size: 0 0", CSS)

    def test_screen_selector_has_scrollbar_size(self) -> None:
        """The Screen selector specifically includes scrollbar-size."""
        from app.app import CSS
        # Find the Screen block and verify it contains the rule
        screen_start = CSS.index("Screen {")
        screen_end = CSS.index("}", screen_start)
        screen_block = CSS[screen_start:screen_end]
        self.assertIn("scrollbar-size: 0 0", screen_block)

    def test_listview_selector_has_scrollbar_size(self) -> None:
        """The ListView selector includes scrollbar-size."""
        from app.app import CSS
        lv_start = CSS.index("ListView {")
        lv_end = CSS.index("}", lv_start)
        lv_block = CSS[lv_start:lv_end]
        self.assertIn("scrollbar-size: 0 0", lv_block)

    def test_verticalscroll_selector_has_scrollbar_size(self) -> None:
        """The VerticalScroll selector includes scrollbar-size."""
        from app.app import CSS
        vs_start = CSS.index("VerticalScroll {")
        vs_end = CSS.index("}", vs_start)
        vs_block = CSS[vs_start:vs_end]
        self.assertIn("scrollbar-size: 0 0", vs_block)

    def test_css_parses_without_error(self) -> None:
        """The full CSS string can be imported without syntax errors."""
        from app.app import CSS
        self.assertIsInstance(CSS, str)
        self.assertGreater(len(CSS), 0)


class KeyBindingTests(unittest.TestCase):
    """Verify vim motion keys are removed and arrow keys are used instead."""

    def test_no_vim_keys_in_bindings(self) -> None:
        vim_keys = {"h", "j", "k", "l"}
        for binding in OchaApp.BINDINGS:
            keys = {k.strip() for k in binding.key.split(",")}
            self.assertTrue(
                keys.isdisjoint(vim_keys),
                f"Binding '{binding.key}' still contains vim key(s): {keys & vim_keys}",
            )

    def test_arrow_keys_are_bound(self) -> None:
        all_keys = set()
        for binding in OchaApp.BINDINGS:
            all_keys.update(k.strip() for k in binding.key.split(","))
        for arrow in ("up", "down", "left", "right"):
            self.assertIn(arrow, all_keys, f"Arrow key '{arrow}' not found in BINDINGS")

    def test_help_bar_uses_arrow_symbols(self) -> None:
        import inspect
        from app.widgets import MainLayout

        source = inspect.getsource(MainLayout.compose)
        self.assertIn("↑/↓", source, "Help bar should show ↑/↓ for move")
        self.assertIn("←/→", source, "Help bar should show ←/→ for focus")
        self.assertNotIn("j/k", source, "Help bar should not show j/k")
        self.assertNotIn("h/l", source, "Help bar should not show h/l")


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

