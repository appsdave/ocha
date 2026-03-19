from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from app.cli import build_parser, main, resolve_target
from app.install import InstallResult
from app.install import DEFAULT_REPO_URL, default_install_dir


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