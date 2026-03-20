"""Tests for the worktree manager module."""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.worktree_manager import (
    OCHA_BRANCH,
    cleanup_worktrees,
    ensure_worktree,
    remove_worktree,
)


class TestEnsureWorktree(unittest.TestCase):
    """Test ensure_worktree with mocked subprocess calls."""

    @patch("app.worktree_manager.subprocess.run")
    def test_creates_worktree_on_branch(self, mock_run: MagicMock, tmp_path: Path = None):
        """Successful creation on the target branch."""
        import tempfile
        tmp = Path(tempfile.mkdtemp())
        wt_path = tmp / "worktrees" / "t-001-builder"

        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

        ok, msg = ensure_worktree(wt_path, OCHA_BRANCH)
        self.assertTrue(ok)
        self.assertIn("Created worktree", msg)
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        self.assertIn("worktree", call_args)
        self.assertIn(str(wt_path), call_args)

    @patch("app.worktree_manager.subprocess.run")
    def test_falls_back_to_detach(self, mock_run: MagicMock):
        """When branch is already checked out, falls back to --detach."""
        import tempfile
        tmp = Path(tempfile.mkdtemp())
        wt_path = tmp / "worktrees" / "t-001-builder"

        # First call fails (branch checked out), second succeeds (detach)
        mock_run.side_effect = [
            MagicMock(returncode=1, stderr="already checked out", stdout=""),
            MagicMock(returncode=0, stderr="", stdout=""),
        ]

        ok, msg = ensure_worktree(wt_path)
        self.assertTrue(ok)
        self.assertIn("detached", msg)
        self.assertEqual(mock_run.call_count, 2)

    @patch("app.worktree_manager.subprocess.run")
    def test_returns_false_on_failure(self, mock_run: MagicMock):
        """When both attempts fail, returns (False, error message)."""
        import tempfile
        tmp = Path(tempfile.mkdtemp())
        wt_path = tmp / "worktrees" / "t-001-builder"

        mock_run.return_value = MagicMock(returncode=1, stderr="fatal error", stdout="")

        ok, msg = ensure_worktree(wt_path)
        self.assertFalse(ok)
        self.assertIn("failed", msg.lower())

    def test_existing_worktree_is_idempotent(self):
        """If the directory already has a .git, returns success immediately."""
        import tempfile
        tmp = Path(tempfile.mkdtemp())
        wt_path = tmp / "worktrees" / "t-001-builder"
        wt_path.mkdir(parents=True)
        (wt_path / ".git").touch()

        ok, msg = ensure_worktree(wt_path)
        self.assertTrue(ok)
        self.assertIn("already exists", msg)


class TestRemoveWorktree(unittest.TestCase):
    @patch("app.worktree_manager.subprocess.run")
    def test_removes_existing_worktree(self, mock_run: MagicMock):
        import tempfile
        tmp = Path(tempfile.mkdtemp())
        wt_path = tmp / "wt"
        wt_path.mkdir()

        mock_run.return_value = MagicMock(returncode=0)

        ok, msg = remove_worktree(wt_path)
        self.assertTrue(ok)
        self.assertIn("Removed", msg)

    def test_nonexistent_worktree_returns_success(self):
        ok, msg = remove_worktree("/nonexistent/path/wt-xyz")
        self.assertTrue(ok)
        self.assertIn("already gone", msg)


class TestCleanupWorktrees(unittest.TestCase):
    @patch("app.worktree_manager.subprocess.run")
    @patch("app.worktree_manager.remove_worktree")
    def test_cleans_existing_worktrees(self, mock_remove: MagicMock, mock_run: MagicMock):
        import tempfile
        tmp = Path(tempfile.mkdtemp())

        # Create fake worktree dirs
        wt1 = tmp / "wt1"
        wt1.mkdir()
        wt2 = tmp / "wt2"
        wt2.mkdir()

        workers = [
            SimpleNamespace(worktree_path=str(wt1)),
            SimpleNamespace(worktree_path=str(wt2)),
        ]
        mock_remove.return_value = (True, "Removed")
        mock_run.return_value = MagicMock(returncode=0)

        msgs = cleanup_worktrees(workers)
        self.assertEqual(mock_remove.call_count, 2)
        self.assertTrue(any("Pruned" in m for m in msgs))

    @patch("app.worktree_manager.subprocess.run")
    def test_empty_workers_just_prunes(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(returncode=0)
        msgs = cleanup_worktrees([])
        self.assertEqual(len(msgs), 1)
        self.assertIn("Pruned", msgs[0])
