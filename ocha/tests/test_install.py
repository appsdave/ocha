from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.install import InstallError, clone_repo, default_install_dir, ensure_bootstrap, resolve_project_dir, update_repo


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