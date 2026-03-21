"""Tests for the file-lock registry and merge-conflict prevention system."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from app.file_lock import (
    FileLockEntry,
    LockConflict,
    _normalise,
    _pattern_matches,
    _patterns_overlap,
    acquire_lock,
    active_locks,
    cleanup_stale_locks,
    detect_conflicts,
    load_locks,
    release_all_for_task,
    release_inactive_locks,
    release_lock,
    save_locks,
    validate_commit_scope,
)


# ── Pattern matching ─────────────────────────────────────────────────


class TestNormalise:
    def test_strips_leading_dot_slash(self):
        assert _normalise("./docs/foo.md") == "docs/foo.md"

    def test_strips_leading_slash(self):
        assert _normalise("/docs/foo.md") == "docs/foo.md"

    def test_no_change_for_clean_path(self):
        assert _normalise("docs/foo.md") == "docs/foo.md"


class TestPatternMatches:
    def test_directory_owns_nested_file(self):
        assert _pattern_matches("docs/", "docs/foo.md")

    def test_directory_owns_deeply_nested(self):
        assert _pattern_matches("docs/", "docs/sub/deep/file.py")

    def test_directory_does_not_own_sibling(self):
        assert not _pattern_matches("docs/", "app/foo.py")

    def test_exact_match(self):
        assert _pattern_matches("ocha/app/state.py", "ocha/app/state.py")

    def test_exact_no_match(self):
        assert not _pattern_matches("ocha/app/state.py", "ocha/app/cli.py")

    def test_glob_star(self):
        assert _pattern_matches("*.md", "README.md")

    def test_glob_no_match(self):
        assert not _pattern_matches("*.md", "README.txt")

    def test_leading_dot_slash_stripped(self):
        assert _pattern_matches("./docs/", "./docs/foo.md")

    def test_directory_matches_directory_itself(self):
        assert _pattern_matches("docs/", "docs")


class TestPatternsOverlap:
    def test_same_directory(self):
        assert _patterns_overlap("docs/", "docs/")

    def test_parent_child_dirs(self):
        assert _patterns_overlap("app/", "app/sub/")

    def test_child_parent_dirs(self):
        assert _patterns_overlap("app/sub/", "app/")

    def test_disjoint_dirs(self):
        assert not _patterns_overlap("docs/", "app/")

    def test_file_inside_dir(self):
        assert _patterns_overlap("app/", "app/state.py")

    def test_exact_same_file(self):
        assert _patterns_overlap("app/state.py", "app/state.py")

    def test_different_files(self):
        assert not _patterns_overlap("app/state.py", "app/cli.py")


# ── Lock registry persistence ────────────────────────────────────────


class TestLoadSaveLocks:
    def test_roundtrip(self, tmp_path: Path):
        entry = FileLockEntry(
            session_id="S-001-01",
            task_id="T-001",
            role="coordinator",
            owned_patterns=["docs/"],
        )
        save_locks(tmp_path, [entry])
        loaded = load_locks(tmp_path)
        assert len(loaded) == 1
        assert loaded[0].session_id == "S-001-01"
        assert loaded[0].owned_patterns == ["docs/"]

    def test_load_empty_when_no_file(self, tmp_path: Path):
        assert load_locks(tmp_path) == []

    def test_load_empty_on_corrupt_json(self, tmp_path: Path):
        lock_file = tmp_path / ".ocha" / "locks.json"
        lock_file.parent.mkdir(parents=True)
        lock_file.write_text("NOT JSON", encoding="utf-8")
        assert load_locks(tmp_path) == []


class TestActiveLocks:
    def test_filters_released(self):
        locks = [
            FileLockEntry("s1", "t1", "coord", ["docs/"], released=False),
            FileLockEntry("s2", "t1", "lead", ["planning/"], released=True),
        ]
        result = active_locks(locks)
        assert len(result) == 1
        assert result[0].session_id == "s1"


# ── Conflict detection ───────────────────────────────────────────────


class TestDetectConflicts:
    def test_no_conflict_disjoint(self):
        locks = [
            FileLockEntry("s1", "t1", "coordinator", ["docs/"]),
        ]
        conflicts = detect_conflicts("s2", "builder", ["app/"], locks)
        assert conflicts == []

    def test_conflict_overlapping_dirs(self):
        locks = [
            FileLockEntry("s1", "t1", "builder", ["app/"]),
        ]
        conflicts = detect_conflicts("s2", "reviewer", ["app/"], locks)
        assert len(conflicts) == 1
        assert conflicts[0].holder_session_id == "s1"

    def test_no_self_conflict(self):
        locks = [
            FileLockEntry("s1", "t1", "builder", ["app/"]),
        ]
        conflicts = detect_conflicts("s1", "builder", ["app/"], locks)
        assert conflicts == []

    def test_released_lock_no_conflict(self):
        locks = [
            FileLockEntry("s1", "t1", "builder", ["app/"], released=True),
        ]
        conflicts = detect_conflicts("s2", "reviewer", ["app/"], locks)
        assert conflicts == []


# ── Acquire / Release ────────────────────────────────────────────────


class TestAcquireRelease:
    def test_acquire_creates_lock(self, tmp_path: Path):
        entry, conflicts = acquire_lock(tmp_path, "s1", "t1", "coord", ["docs/"])
        assert entry.session_id == "s1"
        assert conflicts == []
        locks = load_locks(tmp_path)
        assert len(locks) == 1

    def test_acquire_detects_conflict(self, tmp_path: Path):
        acquire_lock(tmp_path, "s1", "t1", "builder", ["app/"])
        _entry, conflicts = acquire_lock(tmp_path, "s2", "t1", "reviewer", ["app/"])
        assert len(conflicts) == 1

    def test_release_marks_released(self, tmp_path: Path):
        acquire_lock(tmp_path, "s1", "t1", "coord", ["docs/"])
        assert release_lock(tmp_path, "s1") is True
        locks = load_locks(tmp_path)
        assert locks[0].released is True

    def test_release_nonexistent_returns_false(self, tmp_path: Path):
        assert release_lock(tmp_path, "no-such-session") is False

    def test_release_all_for_task(self, tmp_path: Path):
        acquire_lock(tmp_path, "s1", "t1", "coord", ["docs/"])
        acquire_lock(tmp_path, "s2", "t1", "builder", ["app/"])
        acquire_lock(tmp_path, "s3", "t2", "coord", ["docs/"])
        count = release_all_for_task(tmp_path, "t1")
        assert count == 2
        locks = load_locks(tmp_path)
        assert sum(1 for l in locks if l.released) == 2
        assert not locks[2].released  # t2 untouched


class TestCleanupStaleLocks:
    def test_cleans_old_locks(self, tmp_path: Path):
        old_entry = FileLockEntry(
            session_id="s-old",
            task_id="t1",
            role="coord",
            owned_patterns=["docs/"],
            acquired_at=time.time() - 7200,  # 2 hours ago
        )
        save_locks(tmp_path, [old_entry])
        count = cleanup_stale_locks(tmp_path, max_age_seconds=3600)
        assert count == 1
        assert load_locks(tmp_path)[0].released is True

    def test_keeps_fresh_locks(self, tmp_path: Path):
        fresh = FileLockEntry(
            session_id="s-new",
            task_id="t1",
            role="coord",
            owned_patterns=["docs/"],
            acquired_at=time.time(),
        )
        save_locks(tmp_path, [fresh])
        count = cleanup_stale_locks(tmp_path, max_age_seconds=3600)
        assert count == 0


class TestReleaseInactiveLocks:
    def test_releases_untracked_sessions(self, tmp_path: Path):
        acquire_lock(tmp_path, "s1", "t1", "coord", ["docs/"])
        acquire_lock(tmp_path, "s2", "t1", "builder", ["app/"])
        count = release_inactive_locks(tmp_path, {"s2"})
        assert count == 1
        locks = load_locks(tmp_path)
        assert locks[0].released is True
        assert locks[1].released is False


# ── Commit scope validation ──────────────────────────────────────────


class TestValidateCommitScope:
    def test_all_in_scope(self):
        violations = validate_commit_scope(
            ["docs/arch.md", "docs/guide.md"],
            ["docs/"],
        )
        assert violations == []

    def test_out_of_scope(self):
        violations = validate_commit_scope(
            ["docs/arch.md", "ocha/app/state.py"],
            ["docs/"],
        )
        assert violations == ["ocha/app/state.py"]

    def test_multiple_patterns(self):
        violations = validate_commit_scope(
            ["docs/arch.md", "ocha/app/state.py", "README.md"],
            ["docs/", "ocha/app/"],
        )
        assert violations == ["README.md"]

    def test_empty_changes(self):
        assert validate_commit_scope([], ["docs/"]) == []


# ── FileLockEntry.owns ───────────────────────────────────────────────


class TestFileLockEntryOwns:
    def test_owns_file_in_dir(self):
        entry = FileLockEntry("s1", "t1", "coord", ["docs/"])
        assert entry.owns("docs/foo.md") is True

    def test_does_not_own_outside(self):
        entry = FileLockEntry("s1", "t1", "coord", ["docs/"])
        assert entry.owns("app/foo.py") is False
