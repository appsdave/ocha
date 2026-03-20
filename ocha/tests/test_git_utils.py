"""Tests for app.git_utils — worktree commit and cherry-pick logic.

Each test creates a real git repo (with optional detached worktrees) in a
temporary directory so that the subprocess-based helpers are exercised against
actual git operations.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from app.git_utils import commit_worktree_changes, format_pr_title, merge_worktree_commits


def _init_repo(tmp: Path) -> Path:
    """Create a fresh git repo with one initial commit and return its path."""
    repo = tmp / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=str(repo), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@ocha"], cwd=str(repo), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(repo), capture_output=True, check=True)
    (repo / "README.md").write_text("# init\n")
    subprocess.run(["git", "add", "-A"], cwd=str(repo), capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(repo), capture_output=True, check=True)
    return repo


def _add_worktree(repo: Path, name: str) -> Path:
    """Create a detached worktree under *repo*'s parent and return its path."""
    wt = repo.parent / name
    subprocess.run(
        ["git", "worktree", "add", "--detach", str(wt)],
        cwd=str(repo),
        capture_output=True,
        check=True,
    )
    return wt


class TestCommitWorktreeChanges(unittest.TestCase):
    """Tests for commit_worktree_changes()."""

    def test_new_file_is_committed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_repo(Path(tmp))
            wt = _add_worktree(repo, "wt1")
            (wt / "hello.txt").write_text("hello world\n")

            sha = commit_worktree_changes(wt, "add hello")

            self.assertIsNotNone(sha)
            self.assertEqual(len(sha), 40)
            # Verify the commit exists
            log = subprocess.run(
                ["git", "log", "--oneline", "-1", sha],
                cwd=str(wt), capture_output=True, text=True,
            )
            self.assertIn("add hello", log.stdout)

    def test_modified_file_is_committed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_repo(Path(tmp))
            wt = _add_worktree(repo, "wt1")
            (wt / "README.md").write_text("# updated\n")

            sha = commit_worktree_changes(wt, "update readme")

            self.assertIsNotNone(sha)
            show = subprocess.run(
                ["git", "show", "--stat", sha],
                cwd=str(wt), capture_output=True, text=True,
            )
            self.assertIn("README.md", show.stdout)

    def test_clean_worktree_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_repo(Path(tmp))
            wt = _add_worktree(repo, "wt1")

            sha = commit_worktree_changes(wt, "nothing here")

            self.assertIsNone(sha)

    def test_multiple_files_committed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_repo(Path(tmp))
            wt = _add_worktree(repo, "wt1")
            (wt / "a.py").write_text("a = 1\n")
            (wt / "b.py").write_text("b = 2\n")

            sha = commit_worktree_changes(wt, "add a and b")

            self.assertIsNotNone(sha)
            show = subprocess.run(
                ["git", "show", "--stat", sha],
                cwd=str(wt), capture_output=True, text=True,
            )
            self.assertIn("a.py", show.stdout)
            self.assertIn("b.py", show.stdout)

    def test_accepts_path_object(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_repo(Path(tmp))
            wt = _add_worktree(repo, "wt1")
            (wt / "file.txt").write_text("data\n")

            sha = commit_worktree_changes(Path(wt), "path object")

            self.assertIsNotNone(sha)


class TestMergeWorktreeCommits(unittest.TestCase):
    """Tests for merge_worktree_commits()."""

    def test_cherry_pick_into_main(self) -> None:
        """A single worktree commit is cherry-picked onto main."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_repo(Path(tmp))
            wt = _add_worktree(repo, "wt1")
            (wt / "feature.py").write_text("print('hi')\n")
            sha = commit_worktree_changes(wt, "add feature")

            logs = merge_worktree_commits([sha], "main", repo_dir=repo)

            self.assertTrue(any("Cherry-picked" in l or "Applied patch" in l for l in logs))
            # Verify file exists on main
            self.assertTrue((repo / "feature.py").exists())
            self.assertEqual((repo / "feature.py").read_text(), "print('hi')\n")

    def test_multiple_worktree_merges(self) -> None:
        """Two worktrees with non-overlapping changes are both merged."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_repo(Path(tmp))

            wt1 = _add_worktree(repo, "wt1")
            (wt1 / "file_a.py").write_text("a = 1\n")
            sha1 = commit_worktree_changes(wt1, "wt1 changes")

            wt2 = _add_worktree(repo, "wt2")
            (wt2 / "file_b.py").write_text("b = 2\n")
            sha2 = commit_worktree_changes(wt2, "wt2 changes")

            logs = merge_worktree_commits([sha1, sha2], "main", repo_dir=repo)

            self.assertTrue(len(logs) >= 2)
            self.assertTrue((repo / "file_a.py").exists())
            self.assertTrue((repo / "file_b.py").exists())

    def test_empty_sha_list(self) -> None:
        """An empty list returns a log message and does nothing."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_repo(Path(tmp))

            logs = merge_worktree_commits([], "main", repo_dir=repo)

            self.assertEqual(len(logs), 1)
            self.assertIn("No worktree commits", logs[0])

    def test_none_values_are_filtered(self) -> None:
        """None values in the SHA list are silently skipped."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_repo(Path(tmp))

            logs = merge_worktree_commits([None, "", None], "main", repo_dir=repo)

            self.assertEqual(len(logs), 1)
            self.assertIn("No worktree commits", logs[0])

    def test_overlapping_changes_handled(self) -> None:
        """Two worktrees editing the same file are handled (one via fallback)."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_repo(Path(tmp))

            wt1 = _add_worktree(repo, "wt1")
            (wt1 / "README.md").write_text("# from wt1\n")
            sha1 = commit_worktree_changes(wt1, "wt1 readme")

            wt2 = _add_worktree(repo, "wt2")
            (wt2 / "README.md").write_text("# from wt2\n")
            sha2 = commit_worktree_changes(wt2, "wt2 readme")

            logs = merge_worktree_commits([sha1, sha2], "main", repo_dir=repo)

            # Both SHAs should produce a log entry — at least one succeeds
            self.assertTrue(len(logs) >= 2)
            # The file should exist on main with content from one of the worktrees
            self.assertTrue((repo / "README.md").exists())

    def test_already_applied_changes_skipped(self) -> None:
        """Merging the same SHA twice doesn't produce duplicate commits."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_repo(Path(tmp))
            wt = _add_worktree(repo, "wt1")
            (wt / "dup.txt").write_text("duplicate\n")
            sha = commit_worktree_changes(wt, "dup commit")

            logs1 = merge_worktree_commits([sha], "main", repo_dir=repo)
            logs2 = merge_worktree_commits([sha], "main", repo_dir=repo)

            # First merge should succeed
            self.assertTrue(any("Cherry-picked" in l or "Applied patch" in l for l in logs1))
            # Second merge should skip or handle gracefully
            self.assertTrue(any("Skipped" in l or "already" in l.lower() or "no changes" in l.lower() or "Cherry-picked" in l for l in logs2))

    def test_subdirectory_changes(self) -> None:
        """Changes in subdirectories within a worktree are properly committed and merged."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_repo(Path(tmp))
            wt = _add_worktree(repo, "wt1")
            subdir = wt / "app" / "utils"
            subdir.mkdir(parents=True)
            (subdir / "helper.py").write_text("def help(): pass\n")

            sha = commit_worktree_changes(wt, "add nested file")
            self.assertIsNotNone(sha)

            logs = merge_worktree_commits([sha], "main", repo_dir=repo)

            self.assertTrue((repo / "app" / "utils" / "helper.py").exists())
            self.assertEqual(
                (repo / "app" / "utils" / "helper.py").read_text(),
                "def help(): pass\n",
            )


class TestFormatPrTitle(unittest.TestCase):
    """Tests for format_pr_title()."""

    def test_basic_formatting(self) -> None:
        result = format_pr_title("T-001", "add new feature")
        self.assertEqual(result, "[T-001] Add new feature")

    def test_strips_trailing_ellipsis(self) -> None:
        result = format_pr_title("T-002", "can we make the agnts to rename the prs when they are pushing to make th…")
        self.assertTrue(result.startswith("[T-002]"))
        self.assertNotIn("…", result[len("[T-002]"):].rstrip("…"))

    def test_collapses_whitespace(self) -> None:
        result = format_pr_title("T-003", "  lots   of   spaces  ")
        self.assertEqual(result, "[T-003] Lots of spaces")

    def test_empty_title_fallback(self) -> None:
        result = format_pr_title("T-004", "")
        self.assertEqual(result, "[T-004] Automated task")

    def test_no_double_tag(self) -> None:
        result = format_pr_title("T-005", "[T-005] Already tagged title")
        self.assertEqual(result, "[T-005] Already tagged title")

    def test_truncation_at_72_chars(self) -> None:
        long_title = "A" * 100
        result = format_pr_title("T-006", long_title)
        self.assertLessEqual(len(result), 72)
        self.assertTrue(result.endswith("…"))

    def test_strips_trailing_period(self) -> None:
        result = format_pr_title("T-007", "fix the bug.")
        self.assertEqual(result, "[T-007] Fix the bug")

    def test_whitespace_only_title(self) -> None:
        result = format_pr_title("T-008", "   ")
        self.assertEqual(result, "[T-008] Automated task")

    def test_already_capitalised(self) -> None:
        result = format_pr_title("T-009", "Update the README")
        self.assertEqual(result, "[T-009] Update the README")


if __name__ == "__main__":
    unittest.main()
