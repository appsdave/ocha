from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.orchestrator import build_launch_specs, launch_task, load_role_definitions
from app.state import sample_state


class OrchestratorTests(unittest.TestCase):
    def test_load_role_definitions_includes_all_worker_roles(self) -> None:
        definitions = load_role_definitions()

        self.assertEqual({role.value for role in definitions}, {"coordinator", "lead", "builder", "reviewer"})
        self.assertIn("You are the `ocha` coordinator.", definitions[next(iter(definitions))].prompt_markdown)

    def test_build_launch_specs_builds_role_prompts_and_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            specs = build_launch_specs(
                "Finish the role-based headless launch flow.",
                project_path=Path(tmpdir),
                task_number=7,
            )

        self.assertEqual([spec.role.value for spec in specs], ["coordinator", "lead", "builder", "reviewer"])
        self.assertEqual(specs[0].task_id, "T-007")
        self.assertIn("## Runtime context", specs[0].prompt)
        self.assertIn("--project", specs[0].command)
        self.assertEqual(specs[0].command[0], "junie")

    def test_launch_task_appends_role_backed_worker_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state = launch_task(
                sample_state(),
                "Wire role markdown prompts into new task launches.",
                project_path=Path(tmpdir),
            )

        launched_task = state.selected_task
        launched_workers = launched_task.workers
        self.assertEqual(len(launched_workers), 4)
        self.assertEqual(launched_task.task_id, "T-102")
        self.assertEqual(launched_task.status.value, "running")
        self.assertEqual(launched_workers[0].status.value, "running")
        self.assertEqual(launched_workers[1].status.value, "queued")
        self.assertEqual(launched_workers[0].role_prompt_path, "app/roles/coordinator.md")
        self.assertIn("junie_command=junie --project", launched_workers[0].raw_log[1])
        self.assertEqual(state.selected_worker.session_id, launched_workers[0].session_id)
