"""Tests for the worktree manager module."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

from app.worktree_manager import (
    DEFAULT_BRANCH,
    WorktreeResult,
    cleanup_worktrees,
    ensure_worktree,
    list_worktrees,
    remove_worktree,
)


class TestEnsureWorktree(unittest.TestCase):
    @patch("app.worktree_manager.subprocess.run")
    def test_creates_worktree_on_branch(self, mock_run: MagicMock):
        with tempfile.TemporaryDirectory() as tmp:
            wt_path = Path(tmp) / "worktrees" / "t-001-builder"
            mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

            result = ensure_worktree(wt_path, branch=DEFAULT_BRANCH)

            self.assertTrue(result.success)
            self.assertEqual(result.path, wt_path)
            self.assertIn("Created worktree", result.message)
            mock_run.assert_called_once_with(
                ["git", "worktree", "add", str(wt_path), DEFAULT_BRANCH],
                capture_output=True,
                text=True,
                timeout=30,
            )

    @patch("app.worktree_manager.subprocess.run")
    def test_falls_back_to_detach(self, mock_run: MagicMock):
        with tempfile.TemporaryDirectory() as tmp:
            wt_path = Path(tmp) / "worktrees" / "t-001-builder"
            mock_run.side_effect = [
                MagicMock(returncode=1, stderr="already checked out", stdout=""),
                MagicMock(returncode=0, stderr="", stdout=""),
            ]

            result = ensure_worktree(wt_path)

            self.assertTrue(result.success)
            self.assertIn("detached", result.message)
            self.assertEqual(mock_run.call_count, 2)

    @patch("app.worktree_manager.subprocess.run")
    def test_returns_failure_on_git_error(self, mock_run: MagicMock):
        with tempfile.TemporaryDirectory() as tmp:
            wt_path = Path(tmp) / "worktrees" / "t-001-builder"
            mock_run.return_value = MagicMock(returncode=1, stderr="fatal error", stdout="")

            result = ensure_worktree(wt_path)

            self.assertFalse(result.success)
            self.assertIn("failed", result.message.lower())

    @patch("app.worktree_manager.subprocess.run")
    def test_existing_worktree_is_idempotent(self, mock_run: MagicMock):
        with tempfile.TemporaryDirectory() as tmp:
            wt_path = Path(tmp) / "worktrees" / "t-001-builder"
            wt_path.mkdir(parents=True)

            result = ensure_worktree(wt_path)

            self.assertTrue(result.success)
            self.assertIn("already exists", result.message)
            mock_run.assert_not_called()


class TestRemoveWorktree(unittest.TestCase):
    @patch("app.worktree_manager.subprocess.run")
    def test_removes_existing_worktree(self, mock_run: MagicMock):
        with tempfile.TemporaryDirectory() as tmp:
            wt_path = Path(tmp) / "wt"
            wt_path.mkdir()
            mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

            result = remove_worktree(wt_path)

            self.assertTrue(result.success)
            self.assertIn("removed", result.message.lower())
            mock_run.assert_called_once_with(
                ["git", "worktree", "remove", "--force", str(wt_path)],
                capture_output=True,
                text=True,
                timeout=15,
            )

    @patch("app.worktree_manager.subprocess.run")
    def test_nonexistent_worktree_returns_success(self, mock_run: MagicMock):
        result = remove_worktree("/nonexistent/path/wt-xyz")
        self.assertTrue(result.success)
        self.assertIn("already removed", result.message)
        mock_run.assert_not_called()


class TestCleanupWorktrees(unittest.TestCase):
    @patch("app.worktree_manager.subprocess.run")
    @patch("app.worktree_manager.remove_worktree")
    def test_cleans_existing_worktrees(self, mock_remove: MagicMock, mock_run: MagicMock):
        with tempfile.TemporaryDirectory() as tmp:
            wt1 = Path(tmp) / "wt1"
            wt2 = Path(tmp) / "wt2"
            expected = [
                WorktreeResult(wt1, True, "Worktree removed."),
                WorktreeResult(wt2, True, "Worktree removed."),
            ]
            mock_remove.side_effect = expected
            mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

            results = cleanup_worktrees([wt1, wt2])

            self.assertEqual(results, expected)
            mock_remove.assert_has_calls([call(wt1, timeout=15), call(wt2, timeout=15)])
            mock_run.assert_called_once_with(
                ["git", "worktree", "prune"],
                capture_output=True,
                text=True,
                timeout=15,
            )

    @patch("app.worktree_manager.subprocess.run")
    @patch("app.worktree_manager.remove_worktree")
    def test_prune_can_be_disabled(self, mock_remove: MagicMock, mock_run: MagicMock):
        with tempfile.TemporaryDirectory() as tmp:
            wt_path = Path(tmp) / "wt1"
            result = WorktreeResult(wt_path, True, "Worktree removed.")
            mock_remove.return_value = result

            results = cleanup_worktrees([wt_path], prune=False)

            self.assertEqual(results, [result])
            mock_run.assert_not_called()


class TestListWorktrees(unittest.TestCase):
    @patch("app.worktree_manager.subprocess.run")
    def test_parses_porcelain_output(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=(
                "worktree /repo\n"
                "branch refs/heads/main\n\n"
                "worktree /repo/.worktrees/t-001\n"
                "detached\n\n"
            ),
            stderr="",
        )

        self.assertEqual(
            list_worktrees(),
            [
                {"path": "/repo", "branch": "refs/heads/main"},
                {"path": "/repo/.worktrees/t-001", "branch": "(detached)"},
            ],
        )

    @patch("app.worktree_manager.subprocess.run")
    def test_returns_empty_on_git_failure(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="fatal")
        self.assertEqual(list_worktrees(), [])
