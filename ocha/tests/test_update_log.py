from __future__ import annotations

import unittest

from app.install import FileChangeStat, UpdateChangelog, _classify_status, _parse_numstat_line
from app.update_log import (
    _MAX_FILES_SHOWN,
    _bar,
    _plural,
    _status_badge,
    format_update_log,
)


def _make_changelog(**overrides) -> UpdateChangelog:
    """Build a minimal UpdateChangelog, merging *overrides* on top of defaults."""
    defaults = dict(
        branch="main",
        previous_revision="aaa1111100000000",
        revision="bbb2222200000000",
        commits=["bbb22222 Fix widget layout"],
        file_stats=[FileChangeStat(path="app/cli.py", insertions=10, deletions=3, status="modified")],
        total_insertions=10,
        total_deletions=3,
        files_added=0,
        files_modified=1,
        files_deleted=0,
    )
    defaults.update(overrides)
    return UpdateChangelog(**defaults)


class PluralTests(unittest.TestCase):
    def test_singular(self) -> None:
        self.assertEqual(_plural(1, "file"), "1 file")

    def test_plural(self) -> None:
        self.assertEqual(_plural(3, "file"), "3 files")

    def test_zero(self) -> None:
        self.assertEqual(_plural(0, "commit"), "0 commits")


class StatusBadgeTests(unittest.TestCase):
    def test_added(self) -> None:
        self.assertIn("[+]", _status_badge("added"))

    def test_deleted(self) -> None:
        self.assertIn("[-]", _status_badge("deleted"))

    def test_modified(self) -> None:
        self.assertIn("[~]", _status_badge("modified"))

    def test_renamed(self) -> None:
        self.assertIn("[R]", _status_badge("renamed"))

    def test_unknown_falls_back_to_modified(self) -> None:
        self.assertIn("[~]", _status_badge("whatever"))


class BarTests(unittest.TestCase):
    def test_zero_total_returns_empty(self) -> None:
        self.assertEqual(_bar(0, 0), "")

    def test_only_insertions(self) -> None:
        bar = _bar(5, 0)
        self.assertIn("+", bar)
        self.assertNotIn("-", bar.replace("\033[31m", "").replace("\033[0m", ""))

    def test_only_deletions(self) -> None:
        bar = _bar(0, 5)
        self.assertIn("-", bar)

    def test_mixed(self) -> None:
        bar = _bar(3, 7)
        self.assertIn("+", bar)
        self.assertIn("-", bar)


class ParseNumstatLineTests(unittest.TestCase):
    def test_normal_line(self) -> None:
        self.assertEqual(_parse_numstat_line("10\t3\tapp/cli.py"), (10, 3, "app/cli.py"))

    def test_binary_line(self) -> None:
        self.assertEqual(_parse_numstat_line("-\t-\timage.png"), (0, 0, "image.png"))

    def test_malformed_line(self) -> None:
        ins, dels, path = _parse_numstat_line("broken")
        self.assertEqual(ins, 0)
        self.assertEqual(dels, 0)


class ClassifyStatusTests(unittest.TestCase):
    def test_added(self) -> None:
        self.assertEqual(_classify_status("A"), "added")

    def test_deleted(self) -> None:
        self.assertEqual(_classify_status("D"), "deleted")

    def test_modified(self) -> None:
        self.assertEqual(_classify_status("M"), "modified")

    def test_renamed(self) -> None:
        self.assertEqual(_classify_status("R100"), "renamed")

    def test_unknown(self) -> None:
        self.assertEqual(_classify_status("X"), "modified")


class FormatUpdateLogTests(unittest.TestCase):
    def test_none_changelog_returns_already_up_to_date(self) -> None:
        result = format_update_log(None)
        self.assertIn("Already up to date", result)

    def test_basic_changelog_contains_header(self) -> None:
        cl = _make_changelog()
        result = format_update_log(cl)
        self.assertIn("ocha updated successfully", result)
        self.assertIn("main", result)

    def test_shows_revision_range(self) -> None:
        cl = _make_changelog()
        result = format_update_log(cl)
        self.assertIn("aaa11111", result)
        self.assertIn("bbb22222", result)

    def test_shows_commits(self) -> None:
        cl = _make_changelog(commits=["abc123 First", "def456 Second"])
        result = format_update_log(cl)
        self.assertIn("Commits (2)", result)
        self.assertIn("abc123 First", result)
        self.assertIn("def456 Second", result)

    def test_shows_file_counts(self) -> None:
        cl = _make_changelog(files_added=2, files_modified=3, files_deleted=1)
        result = format_update_log(cl)
        self.assertIn("2 files added", result)
        self.assertIn("3 files modified", result)
        self.assertIn("1 file deleted", result)

    def test_shows_insertion_deletion_totals(self) -> None:
        cl = _make_changelog(total_insertions=42, total_deletions=7)
        result = format_update_log(cl)
        self.assertIn("+42", result)
        self.assertIn("-7", result)

    def test_shows_per_file_details(self) -> None:
        cl = _make_changelog(
            file_stats=[
                FileChangeStat(path="a.py", insertions=5, deletions=2, status="added"),
                FileChangeStat(path="b.py", insertions=0, deletions=10, status="deleted"),
            ]
        )
        result = format_update_log(cl)
        self.assertIn("a.py", result)
        self.assertIn("b.py", result)

    def test_truncates_file_list(self) -> None:
        stats = [
            FileChangeStat(path=f"file{i}.py", insertions=1, deletions=0, status="modified")
            for i in range(_MAX_FILES_SHOWN + 5)
        ]
        cl = _make_changelog(file_stats=stats)
        result = format_update_log(cl)
        self.assertIn("more file", result)

    def test_repo_url_shown_when_provided(self) -> None:
        cl = _make_changelog()
        result = format_update_log(cl, repo_url="https://github.com/appsdave/ocha.git")
        self.assertIn("https://github.com/appsdave/ocha.git", result)

    def test_no_commits_section_when_empty(self) -> None:
        cl = _make_changelog(commits=[])
        result = format_update_log(cl)
        self.assertNotIn("Commits", result)

    def test_no_file_count_lines_when_all_zero(self) -> None:
        cl = _make_changelog(files_added=0, files_modified=0, files_deleted=0)
        result = format_update_log(cl)
        self.assertNotIn("Files changed:", result)
