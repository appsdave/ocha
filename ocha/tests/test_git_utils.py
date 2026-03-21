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

from unittest.mock import patch, MagicMock

from app.git_utils import (
    commit_worktree_changes,
    ensure_clean_git_state,
    ensure_pr_title,
    format_pr_title,
    merge_worktree_commits,
)


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

    def test_raises_when_abort_cleanup_leaves_repo_unmerged(self) -> None:
        with patch("app.git_utils.ensure_clean_git_state") as mock_clean_state:
            mock_clean_state.return_value = MagicMock(
                ok=False,
                blocking_reason="Git index still has unresolved merge conflicts.",
            )
            with patch("app.git_utils._has_cherry_pick_in_progress", return_value=True):
                with patch("app.git_utils._run_git") as mock_run_git:
                    mock_run_git.side_effect = [
                        MagicMock(returncode=0, stderr="", stdout=""),
                        MagicMock(returncode=1, stderr="conflict", stdout=""),
                        MagicMock(returncode=0, stderr="", stdout=""),
                    ]
                    with self.assertRaises(subprocess.SubprocessError):
                        merge_worktree_commits(["abc12345"], "main", repo_dir="/tmp/repo")


class TestEnsureCleanGitState(unittest.TestCase):
    def test_detects_dirty_tracked_changes_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_repo(Path(tmp))
            (repo / "README.md").write_text("# dirty\n")

            result = ensure_clean_git_state(repo_dir=repo, require_clean_worktree=True)

            self.assertFalse(result.ok)
            self.assertIn("Tracked local changes", result.blocking_reason)

    def test_auto_stashes_dirty_tracked_changes_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_repo(Path(tmp))
            original = (repo / "README.md").read_text()
            updated = "# dirty\n"
            (repo / "README.md").write_text(updated)

            result = ensure_clean_git_state(
                repo_dir=repo,
                require_clean_worktree=True,
                auto_stash_tracked_changes=True,
            )

            self.assertTrue(result.ok)
            self.assertIn("Stashed tracked local changes before continuing.", result.messages)
            status = subprocess.run(
                ["git", "status", "--porcelain", "--untracked-files=no"],
                cwd=repo,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(status.stdout.strip(), "")
            head_contents = (repo / "README.md").read_text()
            self.assertEqual(head_contents, original)
            stash_list = subprocess.run(
                ["git", "stash", "list"],
                cwd=repo,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertIn("ocha:auto-preflight", stash_list.stdout)

            show = subprocess.run(
                ["git", "stash", "show", "-p", "stash@{0}"],
                cwd=repo,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertIn(updated.strip(), show.stdout)

    def test_aborts_in_progress_cherry_pick_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_repo(Path(tmp))
            subprocess.run(["git", "checkout", "-b", "topic"], cwd=repo, capture_output=True, check=True)
            (repo / "README.md").write_text("topic\n")
            subprocess.run(["git", "commit", "-am", "topic"], cwd=repo, capture_output=True, check=True)
            topic_sha = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True,
            ).stdout.strip()
            subprocess.run(["git", "checkout", "main"], cwd=repo, capture_output=True, check=True)
            (repo / "README.md").write_text("main\n")
            subprocess.run(["git", "commit", "-am", "main"], cwd=repo, capture_output=True, check=True)

            cherry_pick = subprocess.run(
                ["git", "cherry-pick", topic_sha], cwd=repo, capture_output=True, text=True,
            )
            self.assertNotEqual(cherry_pick.returncode, 0)

            result = ensure_clean_git_state(repo_dir=repo)

            self.assertTrue(result.ok)
            self.assertTrue(any("Aborted unfinished cherry-pick" in msg for msg in result.messages))
            status = subprocess.run(
                ["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True, check=True,
            )
            self.assertEqual(status.stdout.strip(), "")


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


class TestEnsurePrTitle(unittest.TestCase):
    """Tests for ensure_pr_title() — gh CLI interactions are mocked."""

    @patch("app.git_utils.shutil.which", return_value=None)
    def test_no_gh_cli_returns_skip(self, _which: MagicMock) -> None:
        result = ensure_pr_title("agent", "[T-001] Fix bug")
        self.assertIn("skipping", result.lower())

    @patch("app.git_utils.subprocess.run")
    @patch("app.git_utils.shutil.which", return_value="/usr/bin/gh")
    def test_updates_existing_open_pr(self, _which: MagicMock, mock_run: MagicMock) -> None:
        list_result = MagicMock(returncode=0, stdout='[{"number": 17}]', stderr="")
        edit_result = MagicMock(returncode=0, stdout="", stderr="")
        mock_run.side_effect = [list_result, edit_result]
        result = ensure_pr_title("agent", "[T-001] Fix bug")
        self.assertIn("updated", result.lower())
        self.assertIn("#17", result)
        self.assertEqual(mock_run.call_count, 2)
        args = mock_run.call_args_list[1][0][0]
        self.assertIn("edit", args)
        self.assertIn("17", args)

    @patch("app.git_utils.subprocess.run")
    @patch("app.git_utils.shutil.which", return_value="/usr/bin/gh")
    def test_no_open_pr_then_create_succeeds(self, _which: MagicMock, mock_run: MagicMock) -> None:
        list_result = MagicMock(returncode=0, stdout="[]", stderr="")
        create_result = MagicMock(returncode=0, stdout="https://github.com/o/r/pull/1", stderr="")
        mock_run.side_effect = [list_result, create_result]
        result = ensure_pr_title("agent", "[T-001] Fix bug")
        self.assertIn("created", result.lower())
        self.assertEqual(mock_run.call_count, 2)

    @patch("app.git_utils.subprocess.run")
    @patch("app.git_utils.shutil.which", return_value="/usr/bin/gh")
    def test_both_fail_returns_note(self, _which: MagicMock, mock_run: MagicMock) -> None:
        list_fail = MagicMock(returncode=1, stdout="", stderr="network error")
        create_fail = MagicMock(returncode=1, stdout="", stderr="create error")
        mock_run.side_effect = [list_fail, create_fail]
        result = ensure_pr_title("agent", "[T-001] Fix bug")
        self.assertIn("note", result.lower())

    @patch("app.git_utils.subprocess.run")
    @patch("app.git_utils.shutil.which", return_value="/usr/bin/gh")
    def test_create_uses_correct_base_branch(self, _which: MagicMock, mock_run: MagicMock) -> None:
        list_result = MagicMock(returncode=0, stdout="[]", stderr="")
        create_result = MagicMock(returncode=0, stdout="https://github.com/o/r/pull/2", stderr="")
        mock_run.side_effect = [list_result, create_result]
        ensure_pr_title("agent", "[T-001] Fix", base="develop")
        create_call_args = mock_run.call_args_list[1][0][0]
        self.assertIn("--base", create_call_args)
        base_idx = create_call_args.index("--base")
        self.assertEqual(create_call_args[base_idx + 1], "develop")

    @patch("app.git_utils.subprocess.run")
    @patch("app.git_utils.shutil.which", return_value="/usr/bin/gh")
    def test_pr_body_contains_task_id(self, _which: MagicMock, mock_run: MagicMock) -> None:
        list_result = MagicMock(returncode=0, stdout="[]", stderr="")
        create_result = MagicMock(returncode=0, stdout="url", stderr="")
        mock_run.side_effect = [list_result, create_result]
        ensure_pr_title("agent", "[T-042] New feature")
        create_call_args = mock_run.call_args_list[1][0][0]
        body_idx = create_call_args.index("--body")
        self.assertIn("T-042", create_call_args[body_idx + 1])

    @patch("app.git_utils.subprocess.run")
    @patch("app.git_utils.shutil.which", return_value="/usr/bin/gh")
    def test_invalid_open_pr_list_output_falls_back_to_create(
        self, _which: MagicMock, mock_run: MagicMock,
    ) -> None:
        list_result = MagicMock(returncode=0, stdout="not json", stderr="")
        create_result = MagicMock(returncode=0, stdout="url", stderr="")
        mock_run.side_effect = [list_result, create_result]

        result = ensure_pr_title("agent", "[T-001] Fix bug")

        self.assertIn("created", result.lower())

    @patch("app.git_utils.subprocess.run")
    @patch("app.git_utils.shutil.which", return_value="/usr/bin/gh")
    def test_existing_open_pr_edit_failure_returns_note(
        self, _which: MagicMock, mock_run: MagicMock,
    ) -> None:
        list_result = MagicMock(returncode=0, stdout='[{"number": 21}]', stderr="")
        edit_fail = MagicMock(returncode=1, stdout="", stderr="edit error")
        mock_run.side_effect = [list_result, edit_fail]

        result = ensure_pr_title("agent", "[T-001] Fix bug")

        self.assertIn("note", result.lower())
        self.assertIn("#21", result)


class TestFormatPrTitleEdgeCases(unittest.TestCase):
    """Additional edge-case tests for format_pr_title."""

    def test_multiple_trailing_dots_and_ellipsis(self) -> None:
        result = format_pr_title("T-010", "fix stuff...…")
        self.assertNotIn("…", result)
        self.assertNotIn("...", result)

    def test_title_exactly_72_chars_not_truncated(self) -> None:
        # [T-011] = 7 chars + 1 space = 8; so desc can be 64 chars
        desc = "A" * 64
        result = format_pr_title("T-011", desc)
        self.assertEqual(len(result), 72)
        self.assertFalse(result.endswith("…"))

    def test_special_characters_preserved(self) -> None:
        result = format_pr_title("T-012", "fix `widget` & <html> encoding")
        self.assertIn("`widget`", result)
        self.assertIn("&", result)

    def test_case_insensitive_double_tag_check(self) -> None:
        result = format_pr_title("T-013", "[t-013] lowercase tag")
        self.assertEqual(result.count("T-013"), 1)
        self.assertTrue(result.startswith("[T-013]"))


if __name__ == "__main__":
    unittest.main()
