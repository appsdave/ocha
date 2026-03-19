from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.install import InstallError, clone_repo, update_repo


class InstallTests(unittest.TestCase):
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
                run_git.side_effect = [
                    None,
                    type("Result", (), {"stdout": "abc123\n"})(),
                ]

                result = clone_repo(target, force=True)

            self.assertEqual(result.action, "downloaded")
            self.assertEqual(result.revision, "abc123")
            self.assertFalse((target / "old.txt").exists())