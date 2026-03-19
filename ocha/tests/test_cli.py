from __future__ import annotations

import unittest
from pathlib import Path

from app.cli import build_parser, resolve_target
from app.install import default_checkout_dir


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

    def test_resolve_target_uses_default_checkout(self) -> None:
        self.assertEqual(resolve_target(None), default_checkout_dir())

    def test_resolve_target_expands_user_path(self) -> None:
        resolved = resolve_target("~/ocha-test-target")
        self.assertIsInstance(resolved, Path)
        self.assertTrue(str(resolved).startswith(str(Path.home())))