from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.install import (
    FileChangeStat,
    InstallError,
    UpdateChangelog,
    build_update_changelog,
    clone_repo,
    default_install_dir,
    ensure_bootstrap,
    resolve_project_dir,
    update_repo,
    _parse_numstat_line,
    _parse_name_status_line,
)


class InstallTests(unittest.TestCase):
    def test_default_install_dir_uses_home_dot_ocha(self) -> None:
        self.assertEqual(default_install_dir(Path("/tmp/home")), Path("/tmp/home/.ocha"))

    def test_resolve_project_dir_prefers_nested_ocha_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            checkout = Path(tmpdir)
            project = checkout / "ocha"
            project.mkdir()
            (project / "pyproject.toml").write_text("[project]\nname='ocha'\n")

            self.assertEqual(resolve_project_dir(checkout), project)

    def test_ensure_bootstrap_installs_from_nested_project_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            checkout = Path(tmpdir)
            project = checkout / "ocha"
            project.mkdir()
            (project / "pyproject.toml").write_text("[project]\nname='ocha'\n")

            with patch("app.install.shutil.which", return_value="/usr/bin/python3"):
                with patch("app.install.run_command") as run_command:
                    ensure_bootstrap(checkout)

            self.assertEqual(run_command.call_args_list[0].args[0], ["python3", "-m", "venv", str(checkout / ".venv")])
            self.assertEqual(
                run_command.call_args_list[1].args[0],
                [str(checkout / ".venv" / "bin" / "python"), "-m", "pip", "install", "-e", str(project)],
            )

    def test_clone_repo_rejects_non_empty_target_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "checkout"
            target.mkdir()
            (target / "README.md").write_text("existing")

            with self.assertRaises(InstallError):
                clone_repo(target)

    def test_update_repo_requires_git_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "checkout"
            target.mkdir()

            with self.assertRaises(InstallError):
                update_repo(target)

    def test_update_repo_marks_already_latest_when_revision_is_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "checkout"
            (target / ".git").mkdir(parents=True)

            R = type("Result", (), {})

            def _make(stdout: str = ""):
                r = R()
                r.stdout = stdout
                return r

            with patch("app.install.run_git") as run_git:
                run_git.side_effect = [
                    _make("abc123\n"),   # resolve_revision (before)
                    None,                 # fetch
                    None,                 # checkout
                    None,                 # reset
                    _make("git@github.com:appsdave/ocha.git\n"),  # remote get-url
                    _make("abc123\n"),   # resolve_revision (after)
                    # summarize_revision_range returns [] (same rev)
                    # build_update_changelog returns empty (same rev)
                ]

                result = update_repo(target, bootstrap=False)

        self.assertEqual(result.action, "already-latest")
        self.assertFalse(result.changed)
        self.assertEqual(result.revision, "abc123")
        self.assertEqual(result.change_summary, [])
        self.assertIsNotNone(result.changelog)
        self.assertEqual(result.changelog.commits, [])
        self.assertEqual(
            [call.args[0] for call in run_git.call_args_list[:4]],
            [
                ["rev-parse", "HEAD"],
                ["fetch", "origin", "main"],
                ["checkout", "main"],
                ["reset", "--hard", "FETCH_HEAD"],
            ],
        )

    def test_update_repo_marks_updated_when_revision_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "checkout"
            (target / ".git").mkdir(parents=True)

            R = type("Result", (), {})

            def _make(stdout: str = ""):
                r = R()
                r.stdout = stdout
                return r

            with patch("app.install.run_git") as run_git:
                run_git.side_effect = [
                    _make("abc123\n"),   # resolve_revision (before)
                    None,                 # fetch
                    None,                 # checkout
                    None,                 # reset
                    _make("git@github.com:appsdave/ocha.git\n"),  # remote get-url
                    _make("def456\n"),   # resolve_revision (after)
                    # summarize_revision_range
                    _make("def456 Add task model\n987abc Show update summary\n"),
                    # build_update_changelog: log
                    _make("def456 Add task model\n987abc Show update summary\n"),
                    # build_update_changelog: diff --numstat
                    _make("10\t2\tocha/app/cli.py\n5\t0\tocha/app/new.py\n"),
                    # build_update_changelog: diff --name-status
                    _make("M\tocha/app/cli.py\nA\tocha/app/new.py\n"),
                ]

                result = update_repo(target, bootstrap=False)

        self.assertEqual(result.action, "updated")
        self.assertTrue(result.changed)
        self.assertEqual(result.revision, "def456")
        self.assertEqual(result.previous_revision, "abc123")
        self.assertEqual(result.change_summary, ["def456 Add task model", "987abc Show update summary"])
        self.assertIsNotNone(result.changelog)
        self.assertEqual(len(result.changelog.commits), 2)
        self.assertEqual(result.changelog.files_added, 1)
        self.assertEqual(result.changelog.files_modified, 1)
        self.assertEqual(result.changelog.total_insertions, 15)
        self.assertEqual(result.changelog.total_deletions, 2)
        self.assertEqual(
            [call.args[0] for call in run_git.call_args_list[:4]],
            [
                ["rev-parse", "HEAD"],
                ["fetch", "origin", "main"],
                ["checkout", "main"],
                ["reset", "--hard", "FETCH_HEAD"],
            ],
        )

    def test_clone_repo_uses_force_to_replace_existing_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "checkout"
            target.mkdir()
            (target / "old.txt").write_text("old")

            with patch("app.install.run_git") as run_git:
                with patch("app.install.ensure_bootstrap") as ensure_bootstrap:
                    run_git.side_effect = [
                        None,
                        type("Result", (), {"stdout": "abc123\n"})(),
                    ]

                    result = clone_repo(target, force=True)

            self.assertEqual(result.action, "downloaded")
            self.assertEqual(result.revision, "abc123")
            self.assertFalse((target / "old.txt").exists())
            ensure_bootstrap.assert_called_once_with(target)