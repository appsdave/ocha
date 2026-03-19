from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from app.cli import build_parser, main, resolve_target
from app.install import InstallResult
from app.install import DEFAULT_REPO_URL, default_install_dir
from app.state import TaskStatus


class CliTests(unittest.TestCase):
    def test_parser_defaults_to_no_explicit_command(self) -> None:
        args = build_parser().parse_args([])
        self.assertIsNone(args.command)

    def test_download_parser_accepts_repo_options(self) -> None:
        args = build_parser().parse_args(["download", "./repo", "--branch", "agent", "--force"])
        self.assertEqual(args.command, "download")
        self.assertEqual(args.target, "./repo")
        self.assertEqual(args.branch, "agent")
        self.assertTrue(args.force)

    def test_download_parser_defaults_to_public_repo_url(self) -> None:
        args = build_parser().parse_args(["download"])
        self.assertEqual(args.repo_url, DEFAULT_REPO_URL)

    def test_tui_subcommand_is_not_exposed(self) -> None:
        with self.assertRaises(SystemExit):
            build_parser().parse_args(["tui"])

    def test_resolve_target_uses_default_install_dir(self) -> None:
        self.assertEqual(resolve_target(None), default_install_dir())

    def test_resolve_target_expands_user_path(self) -> None:
        resolved = resolve_target("~/ocha-test-target")
        self.assertIsInstance(resolved, Path)
        self.assertTrue(str(resolved).startswith(str(Path.home())))

    def test_launch_parser_accepts_task_and_project(self) -> None:
        args = build_parser().parse_args(["launch", "finish wiring Junie", "--project", "~/src/ocha"])
        self.assertEqual(args.command, "launch")
        self.assertEqual(args.task, "finish wiring Junie")
        self.assertEqual(args.project, "~/src/ocha")

    def test_update_main_prints_already_up_to_date_message(self) -> None:
        output = io.StringIO()
        with patch(
            "app.cli.update_repo",
            return_value=InstallResult(
                action="already-latest",
                target=Path("/tmp/.ocha"),
                repo_url="https://github.com/appsdave/ocha.git",
                branch="main",
                revision="abc123",
                previous_revision="abc123",
                changed=False,
                change_summary=[],
            ),
        ):
            with redirect_stdout(output):
                exit_code = main(["update", "/tmp/.ocha"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(output.getvalue().strip(), "Already up to date")

    def test_task_parser_accepts_prompt_argument(self) -> None:
        args = build_parser().parse_args(["task", "Build the login page"])
        self.assertEqual(args.command, "task")
        self.assertEqual(args.prompt, "Build the login page")
        self.assertEqual(args.project, ".")

    def test_task_parser_accepts_project_flag(self) -> None:
        args = build_parser().parse_args(["task", "Fix bug", "--project", "~/src/ocha"])
        self.assertEqual(args.prompt, "Fix bug")
        self.assertEqual(args.project, "~/src/ocha")

    def test_task_command_creates_task_and_prints_summary(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["task", "Ship prompt based task creation", "--project", tmpdir])
            self.assertEqual(exit_code, 0)
            rendered = output.getvalue()
            self.assertIn("T-001", rendered)
            self.assertIn("Ship prompt based task creation", rendered)
            self.assertIn("coordinator", rendered)
            # Verify prompt was persisted
            prompt_file = Path(tmpdir) / ".ocha" / "tasks" / "T-001" / "prompt.md"
            self.assertTrue(prompt_file.exists())
            self.assertEqual(prompt_file.read_text(encoding="utf-8"), "Ship prompt based task creation")
            # Verify status marker was written
            import json
            status_file = Path(tmpdir) / ".ocha" / "tasks" / "T-001" / "status.json"
            self.assertTrue(status_file.exists())
            status = json.loads(status_file.read_text(encoding="utf-8"))
            self.assertEqual(status["task_id"], "T-001")
            self.assertEqual(status["status"], TaskStatus.PENDING)

    def test_task_command_json_flag_outputs_json(self) -> None:
        import json as json_mod
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["task", "JSON output test", "--project", tmpdir, "--json"])
            self.assertEqual(exit_code, 0)
            data = json_mod.loads(output.getvalue())
            self.assertEqual(data["task_id"], "T-001")
            self.assertEqual(data["status"], "pending")
            self.assertEqual(len(data["workers"]), 4)

    def test_task_command_reads_stdin_when_no_argument(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            output = io.StringIO()
            with patch("sys.stdin", io.StringIO("Piped task prompt\n")):
                with redirect_stdout(output):
                    exit_code = main(["task", "--project", tmpdir])
            self.assertEqual(exit_code, 0)
            rendered = output.getvalue()
            self.assertIn("T-001", rendered)
            self.assertIn("Piped task prompt", rendered)

    def test_update_main_prints_change_summary(self) -> None:
        output = io.StringIO()
        with patch(
            "app.cli.update_repo",
            return_value=InstallResult(
                action="updated",
                target=Path("/tmp/.ocha"),
                repo_url="https://github.com/appsdave/ocha.git",
                branch="main",
                revision="def456",
                previous_revision="abc123",
                changed=True,
                change_summary=["def456 Add task model", "987abc Show update summary"],
            ),
        ):
            with redirect_stdout(output):
                exit_code = main(["update", "/tmp/.ocha"])

        rendered = output.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("Updated /tmp/.ocha from https://github.com/appsdave/ocha.git on main @ def456", rendered)
        self.assertIn("Previous revision: abc123", rendered)
        self.assertIn("Changes:", rendered)
        self.assertIn("- def456 Add task model", rendered)