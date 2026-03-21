from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.file_lock import FileLockEntry, load_locks, save_locks
from app.orchestrator import build_launch_specs, build_role_prompt, create_task_from_prompt, launch_task, load_role_definitions, persist_task_prompt, summarize_task, _next_task_number
from app.state import TaskStatus, WorkerRole, sample_state


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

    def test_launch_task_releases_stale_locks_before_acquiring_new_ones(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            save_locks(
                root,
                [
                    FileLockEntry(
                        session_id="S-099-03",
                        task_id="T-099",
                        role="builder",
                        owned_patterns=["app/"],
                    ),
                ],
            )

            state = launch_task(sample_state(), "Fix stale lock noise", project_path=root)

            locks = load_locks(root)
            stale = [l for l in locks if l.session_id == "S-099-03"]
            self.assertEqual(len(stale), 1)
            self.assertTrue(stale[0].released)

            new_worker_ids = {w.session_id for w in state.selected_task.workers}
            new_locks = [l for l in locks if l.session_id in new_worker_ids]
            self.assertEqual(len(new_locks), 4)
            self.assertTrue(all(not l.released for l in new_locks))

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


class MultilinePromptTests(unittest.TestCase):
    def test_multiline_prompt_preserved_in_launch_specs(self) -> None:
        multiline = "Line one\nLine two\nLine three"
        with tempfile.TemporaryDirectory() as tmpdir:
            specs = build_launch_specs(multiline, project_path=Path(tmpdir))

        for spec in specs:
            self.assertIn("Line one", spec.prompt)
            self.assertIn("Line two", spec.prompt)
            self.assertIn("Line three", spec.prompt)

    def test_summarize_task_multiline(self) -> None:
        result = summarize_task("First line\nSecond line\nThird line")
        self.assertNotIn("\n", result)
        self.assertIn("First line", result)
        self.assertIn("Second line", result)

    def test_summarize_task_empty(self) -> None:
        self.assertEqual(summarize_task(""), "Untitled task")

    def test_summarize_task_whitespace_only(self) -> None:
        self.assertEqual(summarize_task("   \n  \n  "), "Untitled task")

    def test_summarize_task_truncates_long_input(self) -> None:
        long_input = "a" * 100
        result = summarize_task(long_input)
        self.assertTrue(len(result) <= 73)  # 72 + ellipsis
        self.assertTrue(result.endswith("…"))


class PersistTaskPromptTests(unittest.TestCase):
    def test_persist_task_prompt_creates_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = persist_task_prompt("T-001", "Do something", Path(tmpdir))
            self.assertTrue(path.exists())
            self.assertEqual(path.read_text(encoding="utf-8"), "Do something")
            self.assertEqual(path.parent.name, "T-001")

    def test_persist_task_prompt_multiline(self) -> None:
        multiline = "Line one\nLine two\nLine three"
        with tempfile.TemporaryDirectory() as tmpdir:
            path = persist_task_prompt("T-002", multiline, Path(tmpdir))
            self.assertEqual(path.read_text(encoding="utf-8"), multiline)

    def test_launch_task_persists_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            launch_task(sample_state(), "Persist me", project_path=Path(tmpdir))
            prompt_file = Path(tmpdir) / ".ocha" / "tasks" / "T-001" / "prompt.md"
            self.assertTrue(prompt_file.exists())
            self.assertEqual(prompt_file.read_text(encoding="utf-8"), "Persist me")


class CreateTaskFromPromptTests(unittest.TestCase):
    def test_creates_prompt_file_and_status_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = create_task_from_prompt("Build the login page", project_path=Path(tmpdir))
            self.assertEqual(result.task_id, "T-001")
            self.assertEqual(result.title, "Build the login page")
            self.assertEqual(result.status, TaskStatus.PENDING)
            self.assertEqual(result.task_dir, Path(tmpdir) / ".ocha" / "tasks" / "T-001")
            self.assertTrue(result.prompt_path.exists())
            self.assertEqual(result.prompt_path.read_text(encoding="utf-8"), "Build the login page")
            # status.json written
            import json
            status_file = result.status_path
            self.assertTrue(status_file.exists())
            status = json.loads(status_file.read_text(encoding="utf-8"))
            self.assertEqual(status["status"], "pending")

    def test_returns_specs_for_all_roles(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = create_task_from_prompt("Fix a bug", project_path=Path(tmpdir))
            self.assertEqual(len(result.specs), 4)
            roles = [s.role.value for s in result.specs]
            self.assertEqual(roles, ["coordinator", "lead", "builder", "reviewer"])

    def test_respects_custom_task_number(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = create_task_from_prompt("Custom number", project_path=Path(tmpdir), task_number=42)
            self.assertEqual(result.task_id, "T-042")

    def test_auto_increments_task_number(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            r1 = create_task_from_prompt("First task", project_path=Path(tmpdir))
            r2 = create_task_from_prompt("Second task", project_path=Path(tmpdir))
            self.assertEqual(r1.task_id, "T-001")
            self.assertEqual(r2.task_id, "T-002")

    def test_persists_per_worker_session_artifacts(self) -> None:
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            result = create_task_from_prompt("Session prompt test", project_path=Path(tmpdir))
            for spec in result.specs:
                session_dir = result.task_dir / "sessions" / spec.session_id
                session_file = session_dir / "prompt.md"
                manifest_file = session_dir / "session.json"
                self.assertTrue(session_file.exists(), f"Missing {session_file}")
                content = session_file.read_text(encoding="utf-8")
                self.assertIn("## Runtime context", content)
                self.assertIn("Session prompt test", content)
                self.assertTrue(manifest_file.exists(), f"Missing {manifest_file}")
                manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
                self.assertEqual(manifest["session_id"], spec.session_id)
                self.assertEqual(manifest["role"], spec.role.value)
                self.assertEqual(manifest["owned_directory"], spec.owned_directory)

    def test_to_json_round_trips(self) -> None:
        import json
        with tempfile.TemporaryDirectory() as tmpdir:
            result = create_task_from_prompt("JSON test", project_path=Path(tmpdir))
            data = json.loads(result.to_json())
            self.assertEqual(data["task_id"], "T-001")
            self.assertEqual(data["status"], "pending")
            self.assertEqual(len(data["workers"]), 4)
            self.assertIn("task_dir", data)
            self.assertIn("prompt_path", data)
            self.assertIn("status_path", data)
            self.assertTrue(data["workers"][0]["prompt_path"].endswith("/prompt.md"))
            self.assertTrue(data["workers"][0]["manifest_path"].endswith("/session.json"))


class RolePromptContractTests(unittest.TestCase):
    """Verify each role .md file contains the expected input/output contracts."""

    def setUp(self) -> None:
        self.definitions = load_role_definitions()

    def test_coordinator_has_summary_contract(self) -> None:
        md = self.definitions[WorkerRole.COORDINATOR].prompt_markdown
        self.assertIn("## What you receive", md)
        self.assertIn("## What you must produce", md)
        self.assertIn("## Summary", md)
        self.assertIn("Do NOT produce", md)

    def test_lead_has_summary_contract(self) -> None:
        md = self.definitions[WorkerRole.LEAD].prompt_markdown
        self.assertIn("## What you receive", md)
        self.assertIn("## What you must produce", md)
        self.assertIn("## Summary", md)
        self.assertIn("Do NOT produce", md)

    def test_builder_has_summary_contract(self) -> None:
        md = self.definitions[WorkerRole.BUILDER].prompt_markdown
        self.assertIn("## What you receive", md)
        self.assertIn("## What you must produce", md)
        self.assertIn("## Summary", md)
        self.assertIn("Do NOT produce", md)

    def test_reviewer_has_review_summary_contract(self) -> None:
        md = self.definitions[WorkerRole.REVIEWER].prompt_markdown
        self.assertIn("## What you receive", md)
        self.assertIn("## What you must produce", md)
        self.assertIn("## Review Summary", md)
        self.assertIn("Do NOT produce", md)
