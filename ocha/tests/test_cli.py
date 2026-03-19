from __future__ import annotations

import unittest
from pathlib import Path

from app.cli import build_parser, resolve_target
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