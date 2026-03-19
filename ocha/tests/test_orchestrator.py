from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.orchestrator import build_launch_specs, build_role_prompt, launch_task, load_role_definitions
from app.state import WorkerRole, sample_state


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
        self.assertEqual(launched_task.task_id, "T-001")
        self.assertEqual(launched_task.status.value, "running")
        self.assertEqual(launched_workers[0].status.value, "running")
        self.assertEqual(launched_workers[1].status.value, "queued")
        self.assertEqual(launched_workers[0].role_prompt_path, "app/roles/coordinator.md")
        self.assertIn("junie_command=junie --project", launched_workers[0].raw_log[1])
        self.assertEqual(state.selected_worker.session_id, launched_workers[0].session_id)

    def test_build_role_prompt_without_upstream_output(self) -> None:
        definitions = load_role_definitions()
        definition = definitions[WorkerRole.COORDINATOR]
        prompt = build_role_prompt(
            definition,
            task_id="T-001",
            session_id="S-001-01",
            title="Test task",
            user_task="Do something",
            project_path=Path("/tmp/test"),
            worktree_path=Path("/tmp/test/.worktrees/t-001-coordinator"),
            owned_directory="docs/",
        )
        self.assertIn("## Runtime context", prompt)
        self.assertIn("## Operator task", prompt)
        self.assertNotIn("## Prior phase output", prompt)

    def test_build_role_prompt_with_upstream_output_injects_section(self) -> None:
        definitions = load_role_definitions()
        definition = definitions[WorkerRole.LEAD]
        upstream = "The coordinator produced this execution brief."
        prompt = build_role_prompt(
            definition,
            task_id="T-001",
            session_id="S-001-02",
            title="Test task",
            user_task="Do something",
            project_path=Path("/tmp/test"),
            worktree_path=Path("/tmp/test/.worktrees/t-001-lead"),
            owned_directory="planning/",
            upstream_output=upstream,
        )
        self.assertIn("## Prior phase output", prompt)
        self.assertIn("The coordinator produced this execution brief.", prompt)
        # Ensure ordering: upstream appears between operator task and execution rules
        upstream_pos = prompt.index("## Prior phase output")
        rules_pos = prompt.index("## Execution rules")
        self.assertLess(upstream_pos, rules_pos)


class RolePromptContractTests(unittest.TestCase):
    """Verify each role .md file contains the expected input/output contracts."""

    def setUp(self) -> None:
        self.definitions = load_role_definitions()

    def test_coordinator_has_execution_brief_contract(self) -> None:
        md = self.definitions[WorkerRole.COORDINATOR].prompt_markdown
        self.assertIn("## What you receive", md)
        self.assertIn("## What you must produce", md)
        self.assertIn("Execution Brief", md)

    def test_lead_has_task_plan_contract(self) -> None:
        md = self.definitions[WorkerRole.LEAD].prompt_markdown
        self.assertIn("## What you receive", md)
        self.assertIn("## What you must produce", md)
        self.assertIn("Task Plan", md)

    def test_builder_has_change_summary_contract(self) -> None:
        md = self.definitions[WorkerRole.BUILDER].prompt_markdown
        self.assertIn("## What you receive", md)
        self.assertIn("## What you must produce", md)
        self.assertIn("Change Summary", md)

    def test_reviewer_has_review_verdict_contract(self) -> None:
        md = self.definitions[WorkerRole.REVIEWER].prompt_markdown
        self.assertIn("## What you receive", md)
        self.assertIn("## What you must produce", md)
        self.assertIn("Review Verdict", md)
