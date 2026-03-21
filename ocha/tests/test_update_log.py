from __future__ import annotations

import unittest
from pathlib import Path

from app.install import (
    FileChangeStat,
    InstallResult,
    UpdateChangelog,
    _parse_name_status_line,
    _parse_numstat_line,
)
from app.update_log import format_update_log


class ParseNumstatLineTests(unittest.TestCase):
    def test_normal_line(self) -> None:
        self.assertEqual(_parse_numstat_line("10\t3\tpath/to/file.py"), (10, 3, "path/to/file.py"))

    def test_binary_file_dashes(self) -> None:
        self.assertEqual(_parse_numstat_line("-\t-\timage.png"), (0, 0, "image.png"))

    def test_malformed_line_returns_zero_counts(self) -> None:
        ins, dels, path = _parse_numstat_line("badline")
        self.assertEqual(ins, 0)
        self.assertEqual(dels, 0)


class ParseNameStatusLineTests(unittest.TestCase):
    def test_added(self) -> None:
        self.assertEqual(_parse_name_status_line("A\tnew_file.py"), ("A", "new_file.py"))

    def test_modified(self) -> None:
        self.assertEqual(_parse_name_status_line("M\texisting.py"), ("M", "existing.py"))

    def test_deleted(self) -> None:
        self.assertEqual(_parse_name_status_line("D\told.py"), ("D", "old.py"))

    def test_rename_normalised(self) -> None:
        status, path = _parse_name_status_line("R100\trenamed.py")
        self.assertEqual(status, "R")

    def test_malformed_defaults_to_modified(self) -> None:
        status, _ = _parse_name_status_line("weirdline")
        self.assertEqual(status, "M")


class FormatUpdateLogTests(unittest.TestCase):
    def _make_result(self, *, changed: bool = True, changelog: UpdateChangelog | None = None) -> InstallResult:
        return InstallResult(
            action="updated" if changed else "already-latest",
            target=Path("/tmp/ocha"),
            repo_url="https://github.com/appsdave/ocha.git",
            branch="main",
            revision="def456abcd",
            previous_revision="abc123abcd" if changed else "def456abcd",
            changed=changed,
            change_summary=["def456 Add feature"] if changed else [],
            changelog=changelog,
        )

    def test_already_up_to_date(self) -> None:
        result = self._make_result(changed=False)
        output = format_update_log(result)
        self.assertIn("up to date", output)
        self.assertIn("def456abcd", output)

    def test_updated_shows_header_and_revisions(self) -> None:
        changelog = UpdateChangelog(
            commits=["def456 Add feature"],
            file_stats=[FileChangeStat(path="app/cli.py", insertions=10, deletions=2, status="M")],
            files_added=0,
            files_modified=1,
            files_deleted=0,
            total_insertions=10,
            total_deletions=2,
        )
        result = self._make_result(changed=True, changelog=changelog)
        output = format_update_log(result)
        self.assertIn("updated successfully", output)
        self.assertIn("abc123abcd", output)
        self.assertIn("def456abcd", output)
        self.assertIn("Add feature", output)
        self.assertIn("cli.py", output)

    def test_updated_shows_file_counts(self) -> None:
        changelog = UpdateChangelog(
            commits=["aaa1111 Fix bug"],
            file_stats=[
                FileChangeStat(path="a.py", insertions=5, deletions=0, status="A"),
                FileChangeStat(path="b.py", insertions=0, deletions=10, status="D"),
            ],
            files_added=1,
            files_modified=0,
            files_deleted=1,
            total_insertions=5,
            total_deletions=10,
        )
        result = self._make_result(changed=True, changelog=changelog)
        output = format_update_log(result)
        self.assertIn("1 added", output)
        self.assertIn("1 deleted", output)
        self.assertIn("+5", output)
        self.assertIn("-10", output)

    def test_fallback_when_changelog_is_none(self) -> None:
        result = self._make_result(changed=True, changelog=None)
        output = format_update_log(result)
        self.assertIn("Add feature", output)

    def test_many_files_truncated(self) -> None:
        stats = [
            FileChangeStat(path=f"file{i}.py", insertions=1, deletions=0, status="M")
            for i in range(20)
        ]
        changelog = UpdateChangelog(
            commits=["aaa Fix"],
            file_stats=stats,
            files_added=0,
            files_modified=20,
            files_deleted=0,
            total_insertions=20,
            total_deletions=0,
        )
        result = self._make_result(changed=True, changelog=changelog)
        output = format_update_log(result)
        self.assertIn("5 more files", output)


if __name__ == "__main__":
    unittest.main()
